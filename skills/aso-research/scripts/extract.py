#!/usr/bin/env python3
"""Keyword extraction engine (slice 02 — real, no LLM).

Three deterministic layers per the PRD ("Keyword extraction"):

1. **Position-weighted single terms.** For every competitor document we
   record which field carries a term: Title (×5), Subtitle (×3),
   Description (×1). The per-field *hit counts* feed the scorer's
   Competition formula exactly; the weighted term frequency feeds
   candidate ranking and the ``min_freq`` gate.

2. **YAKE-style phrases.** A small, dependency-free YAKE ranks coherent
   multi-word candidates (n-grams, n=2..3) built from the high-signal
   fields (title + subtitle). Single words are weak for ASO; phrases are
   the gold. The YAKE score is used only to *select* a bounded set of
   phrases — the reported scores come from the Competition/Relevance
   engine in :mod:`score`.

3. **Search-Suggest enrichment.** Autocomplete terms are merged in as
   first-class candidates (the only free real-search-signal channel) so
   the scorer can apply its relevance boost.

Processing rules (PRD): DE + EN stopword lists, lowercasing, min
frequency >= 2, generics filter ("app", "iphone", "android", category
name), light morphology grouping (singular/plural/declension merged —
the most frequent original form is kept as the display term).

Everything is pure + deterministic: identical input -> identical output
(sorted everywhere, no dict iteration order leaking).
"""

from __future__ import annotations

import math
import re
from typing import Dict, Iterable, List, Mapping, Sequence

_MIN_TOKEN_LEN = 3
_MAX_PHRASE_LEN = 3  # YAKE candidate n-grams: bigrams + trigrams
# Alphanumeric incl. Latin-1 supplement (covers äöü à-ÿ) plus ß (U+00DF,
# which sits just below à and is not in the à-ÿ range). Apostrophes and
# hyphens are separators so contractions ("don't") and compounds
# ("gewohnheits-tracker") split deterministically into tokens.
_TOKEN_RE = re.compile(r"[0-9a-zßà-öø-ÿ]+")
_SENT_SPLIT_RE = re.compile(r"[.!?;\n]+")

# ---------------------------------------------------------------------------
# Stopwords + generics
# ---------------------------------------------------------------------------

STOPWORDS: set = {
    # EN
    "the", "and", "for", "with", "your", "you", "app", "apps", "all",
    "are", "new", "now", "from", "get", "has", "have", "this", "that",
    "its", "our", "was", "will", "can", "but", "not", "his", "her",
    "they", "them", "their", "who", "when", "how", "what", "best",
    "into", "over", "than", "then", "these", "those", "out", "about",
    "use", "using", "used", "one", "two", "make", "made", "more",
    "most", "very", "just", "like", "also", "only", "any", "some",
    # DE
    "und", "fur", "für", "der", "die", "das", "mit", "ist", "ein",
    "eine", "von", "dir", "ich", "sie", "nicht", "auch", "mehr", "noch",
    "aber", "den", "dem", "des", "im", "in", "an", "auf", "zu", "zur",
    "zum", "bei", "wir", "uns", "euch", "es", "sich", "wird", "werden",
    "wenn", "als", "wie", "warum", "was", "wer", "diese", "dieser",
    "dieses", "einer", "eines", "kein", "keine", "schon", "sein", "war",
    "hast", "haben", "kann", "knnen", "können", "sind", "ber", "über",
    "vom", "beim", "nach", "aus", "durch", "ohne", "statt", "neue",
    "neuen", "ganz", "ganze", "jede", "jeden", "alle", "allen",
}

# Platform / device generics dropped alongside the caller-supplied
# category name. "app" / "apps" already live in STOPWORDS; kept here too
# so callers can extend the block list symmetrically.
PLATFORM_GENERICS = {
    "app", "apps", "iphone", "ipad", "ios", "android", "phone",
    "mobile", "tablet", "smartphone", "store", "download",
}


def _raw_tokens(text: str) -> List[str]:
    """Lowercased alphanumeric tokens with NO filtering (for n-gram builds)."""
    if not text:
        return []
    return _TOKEN_RE.findall((text or "").lower())


def tokenize(text: str) -> List[str]:
    """Split free text into lowercased, filtered tokens.

    Keeps tokens of length >= 3 that are neither stopwords nor platform
    generics. Deterministic. (Preserved from slice 01 for compatibility —
    the scorer uses it to tokenise the seed description.)
    """
    if not text:
        return []
    blocked = STOPWORDS | PLATFORM_GENERICS
    return [
        tok
        for tok in _TOKEN_RE.findall(text.lower())
        if len(tok) >= _MIN_TOKEN_LEN and tok not in blocked
    ]


# ---------------------------------------------------------------------------
# Light morphology grouping
# ---------------------------------------------------------------------------

# German umlaut -> base vowel, for grouping keys only (display form kept).
_UMLAUT_MAP = str.maketrans({"ä": "a", "ö": "o", "ü": "u", "ß": "ss"})
# Plural/declension endings stripped to build *variant* stems. A token
# generates the set {itself, itself-minus-each-matching-suffix}; the
# group key is the alphabetically smallest variant. Two tokens share a
# variant iff they share their smallest key, so this collapses the
# irregular German plurals (gewohnheit-en, routine-n, Mutter/Mütter) and
# English plurals (-s) without mangling roots like ``tracker``.
_GROUP_SUFFIXES = ("en", "er", "es", "e", "n", "s")


def _stem_variants(token: str) -> set:
    """Closure of plausible stems for ``token`` (recursive suffix stripping).

    Starts from the umlaut-normalised token and strips any matching
    plural/declension suffix repeatedly (each intermediate form is kept),
    so ``trackers`` reaches ``tracker`` *and* ``track``. Stripping stops
    once a stem would fall below the minimum token length.
    """
    base = token.translate(_UMLAUT_MAP)
    seen = {base}
    frontier = [base]
    while frontier:
        word = frontier.pop()
        for suf in _GROUP_SUFFIXES:
            if word.endswith(suf) and len(word) - len(suf) >= _MIN_TOKEN_LEN:
                nxt = word[: -len(suf)]
                if nxt not in seen:
                    seen.add(nxt)
                    frontier.append(nxt)
    return seen


def morph_key(token: str) -> str:
    """Grouping key that merges singular/plural/declension + umlaut variants.

    The original form is *not* lost — :func:`group_terms` keeps the most
    frequent original form as the display term. The key is the smallest
    stem variant, so surface forms sharing any stem collapse together
    (``tracker``/``trackers``; ``gewohnheit``/``gewohnheiten``;
    ``routine``/``routinen``; ``mutter``/``mütter``).
    """
    if not token:
        return token
    return min(_stem_variants(token))


# ---------------------------------------------------------------------------
# Per-field presence + weighted frequency
# ---------------------------------------------------------------------------

def _field_tokens(field_text: str) -> set:
    """Unique filtered tokens present in one field text (per-doc set)."""
    return set(tok for tok in tokenize(field_text or ""))


def _phrase_in_field(field_text: str, phrase_tokens: Sequence[str]) -> bool:
    """True when the phrase (contiguous, lowercased) occurs in the field text."""
    if not phrase_tokens or not field_text:
        return False
    toks = _raw_tokens(field_text)
    n, m = len(toks), len(phrase_tokens)
    if n < m:
        return False
    for i in range(n - m + 1):
        if toks[i : i + m] == list(phrase_tokens):
            return True
    return False


# ---------------------------------------------------------------------------
# YAKE-style phrase ranking (lightweight, dependency-free)
# ---------------------------------------------------------------------------

def _sentences(text: str) -> List[str]:
    return [s for s in _SENT_SPLIT_RE.split(text or "") if s.strip()]


def _candidate_phrases(field_text: str) -> Dict[tuple, int]:
    """Yield n-gram candidate phrases (n=2..3) -> occurrence count.

    Phrases are contiguous runs of *filtered* tokens (stopwords removed),
    so a phrase never spans a stopword. Repeated phrases within the field
    count once per occurrence (YAKE frequency signal).
    """
    phrases: Dict[tuple, int] = {}
    if not field_text:
        return phrases
    for sentence in _sentences(field_text):
        toks = tokenize(sentence)
        if len(toks) < 2:
            continue
        for n in range(2, _MAX_PHRASE_LEN + 1):
            for i in range(len(toks) - n + 1):
                gram = tuple(toks[i : i + n])
                phrases[gram] = phrases.get(gram, 0) + 1
    return phrases


def _yake_score(
    gram: tuple,
    *,
    freq: int,
    total_phrases: int,
    sentence_index: float,
) -> float:
    """Compact YAKE-style rank score (higher = better keyword).

    Blends frequency, early position (first sentences score higher) and a
    normalised frequency share. Used only to *order* phrase candidates for
    the bounded inclusion — never reported to the user.
    """
    position = 1.0 / (1.0 + sentence_index)  # earlier => higher
    share = freq / total_phrases if total_phrases else 0.0
    length_boost = math.log(1 + len(gram))  # prefer longer phrases slightly
    return (freq * position + share) * length_boost


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def group_terms(
    term_records: Mapping[str, dict],
) -> List[dict]:
    """Merge term records by :func:`morph_key`, keeping the display form.

    ``term_records`` maps an original surface term -> a partial record
    (carrying per-field hit sets / counts). The merged record keeps the
    *most frequent* original surface form as ``term`` and lists every
    surface variant under ``variants`` (sorted, unique). Hit sets and
    weighted frequencies are unioned/summed across the group.
    """
    groups: Dict[str, dict] = {}
    for surface, rec in term_records.items():
        key = morph_key(surface)
        bucket = groups.setdefault(
            key,
            {
                "variants": set(),
                "title_docs": set(),
                "subtitle_docs": set(),
                "description_docs": set(),
                "tf_weighted": 0,
                "occurrences": 0,
            },
        )
        bucket["variants"].add(surface)
        bucket["title_docs"] |= rec.get("title_docs", set())
        bucket["subtitle_docs"] |= rec.get("subtitle_docs", set())
        bucket["description_docs"] |= rec.get("description_docs", set())
        bucket["tf_weighted"] += rec.get("tf_weighted", 0)
        bucket["occurrences"] += rec.get("occurrences", 0)

    merged: List[dict] = []
    for key, bucket in groups.items():
        variants = sorted(bucket["variants"])
        # Display form: the most frequent variant; tie-break alphabetical.
        variant_freq = {
            v: term_records[v].get("occurrences", 0) for v in variants
        }
        display = max(variants, key=lambda v: (variant_freq[v], -ord(v[0])))
        merged.append(
            {
                "term": display,
                "variants": variants,
                "title_docs": bucket["title_docs"],
                "subtitle_docs": bucket["subtitle_docs"],
                "description_docs": bucket["description_docs"],
                "tf_weighted": bucket["tf_weighted"],
                "occurrences": bucket["occurrences"],
            }
        )
    return merged


def extract_keywords(
    documents: Iterable[Mapping[str, str]],
    *,
    generics: Iterable[str] = (),
    seed_description: str = "",
    suggest_terms: Iterable[str] = (),
    min_freq: int = 2,
    max_phrases: int = 40,
) -> List[Dict]:
    """Extract scored-candidate keyword records from competitor documents.

    Each ``document`` is a mapping with ``title``, ``subtitle``,
    ``description`` (any may be missing/empty). Returns one record per
    candidate term, carrying the per-field doc-hit sets the scorer needs:

        {
          "term", "variants", "is_phrase",
          "title_hits", "subtitle_hits", "description_hits",
          "tf_weighted", "doc_freq", "occurrences",
          "suggest",
        }

    Output is sorted by ``(-occurrences, -tf_weighted, term)`` so two
    identical runs are byte-identical. The ``generics`` block list
    (category name + platform words) and the builtin stopwords are
    dropped. Candidates below ``min_freq`` weighted occurrences are
    removed. ``suggest_terms`` are merged in as candidates.
    """
    docs = list(documents)
    generic = {g.lower() for g in generics if g} | PLATFORM_GENERICS
    blocked = STOPWORDS | generic
    suggest = {s.lower().strip() for s in suggest_terms if s and s.strip()}

    # ---- single-term pass (position-weighted) ----
    single: Dict[str, dict] = {}
    # ---- phrase pass (YAKE) ----
    phrase_freq: Dict[tuple, int] = {}
    phrase_sent_index: Dict[tuple, float] = {}

    for idx, doc in enumerate(docs):
        title = doc.get("title", "") or ""
        subtitle = doc.get("subtitle", "") or ""
        description = doc.get("description", "") or ""

        for weight, field in ((5, title), (3, subtitle), (1, description)):
            field_unique = set()
            for tok in _raw_tokens(field):
                if len(tok) < _MIN_TOKEN_LEN or tok in blocked:
                    continue
                field_unique.add(tok)
            for tok in field_unique:
                rec = single.setdefault(
                    tok,
                    {
                        "title_docs": set(),
                        "subtitle_docs": set(),
                        "description_docs": set(),
                        "tf_weighted": 0,
                        "occurrences": 0,
                    },
                )
                if weight == 5:
                    rec["title_docs"].add(idx)
                elif weight == 3:
                    rec["subtitle_docs"].add(idx)
                else:
                    rec["description_docs"].add(idx)
                rec["tf_weighted"] += weight
                rec["occurrences"] += 1

        # YAKE phrases from title + subtitle (high-signal fields).
        for field_text, sentence_base in ((title, 0.0), (subtitle, 0.5)):
            grams = _candidate_phrases(field_text)
            for gram, freq in grams.items():
                # drop phrases whose every token is generic/stopword-ish
                if all(g in blocked for g in gram):
                    continue
                phrase_freq[gram] = phrase_freq.get(gram, 0) + freq
                # earliest sentence index seen (deterministic: min)
                idx_seen = sentence_base
                prev = phrase_sent_index.get(gram)
                if prev is None or idx_seen < prev:
                    phrase_sent_index[gram] = idx_seen

    # ---- group single terms morphologically ----
    grouped_single = group_terms(single)

    # ---- rank + bound phrases (YAKE) ----
    total_phrases = sum(phrase_freq.values())
    ranked_phrases = sorted(
        phrase_freq.items(),
        key=lambda kv: (
            -_yake_score(
                kv[0],
                freq=kv[1],
                total_phrases=total_phrases,
                sentence_index=phrase_sent_index.get(kv[0], 0.0),
            ),
            kv[0],
        ),
    )

    candidates: List[dict] = []

    for rec in grouped_single:
        # frequency gate (weighted occurrences across the corpus)
        if rec["occurrences"] < min_freq:
            continue
        surface = rec["term"]
        candidates.append(
            {
                "term": surface,
                "variants": rec["variants"],
                "is_phrase": False,
                "title_hits": len(rec["title_docs"]),
                "subtitle_hits": len(rec["subtitle_docs"]),
                "description_hits": len(rec["description_docs"]),
                "tf_weighted": rec["tf_weighted"],
                "doc_freq": len(
                    rec["title_docs"]
                    | rec["subtitle_docs"]
                    | rec["description_docs"]
                ),
                "occurrences": rec["occurrences"],
                "suggest": surface in suggest,
            }
        )

    # phrase candidates (bounded) -> recompute per-doc field hits
    for gram, freq in ranked_phrases[:max_phrases]:
        if freq < min_freq:
            continue
        phrase_str = " ".join(gram)
        title_docs = set()
        sub_docs = set()
        desc_docs = set()
        tf_weighted = 0
        for idx, doc in enumerate(docs):
            in_t = _phrase_in_field(doc.get("title", "") or "", gram)
            in_s = _phrase_in_field(doc.get("subtitle", "") or "", gram)
            in_d = _phrase_in_field(doc.get("description", "") or "", gram)
            if in_t:
                title_docs.add(idx)
                tf_weighted += 5
            if in_s:
                sub_docs.add(idx)
                tf_weighted += 3
            if in_d:
                desc_docs.add(idx)
                tf_weighted += 1
        candidates.append(
            {
                "term": phrase_str,
                "variants": [phrase_str],
                "is_phrase": True,
                "title_hits": len(title_docs),
                "subtitle_hits": len(sub_docs),
                "description_hits": len(desc_docs),
                "tf_weighted": tf_weighted,
                "doc_freq": len(title_docs | sub_docs | desc_docs),
                "occurrences": freq,
                "suggest": phrase_str in suggest,
            }
        )

    # ---- Search-Suggest enrichment: add terms not already present ----
    existing = {c["term"] for c in candidates}
    for s in sorted(suggest):
        toks = [t for t in tokenize(s) if t]
        if not toks:
            continue
        if s in existing:
            continue
        candidates.append(
            {
                "term": s,
                "variants": [s],
                "is_phrase": len(toks) > 1,
                "title_hits": 0,
                "subtitle_hits": 0,
                "description_hits": 0,
                "tf_weighted": 0,
                "doc_freq": 0,
                "occurrences": 0,
                "suggest": True,
            }
        )

    candidates.sort(
        key=lambda c: (-c["occurrences"], -c["tf_weighted"], c["term"])
    )
    return candidates
