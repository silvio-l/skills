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

# ---------------------------------------------------------------------------
# Per-platform field tuples (slice 04 — shared, field-driven engine)
# ---------------------------------------------------------------------------
# Each platform declares its slots as ``(field_name, tf_idf_position_weight)``.
# The extraction engine is field-driven: it reads ``doc[field_name]``, records
# per-doc hits under ``<field>_docs``, and weights TF by the field weight.
# Output candidates carry ``<field>_hits`` for every field, so the (also
# shared) scorer can read the platform's hit counts with the platform's
# weights. Apple's default tuple reproduces slice 02 byte-for-byte.

APPLE_FIELDS: tuple = (("title", 5), ("subtitle", 3), ("description", 1))
# Play slots: Title x5 · Short x4 (strong ranking factor) · Long x2 (fully
# indexed). Mirrors score.PLAY_SLOT_WEIGHTS; kept here so extraction applies
# Play's TF-IDF position weighting, not Apple's.
PLAY_FIELDS: tuple = (("title", 5), ("short", 4), ("long", 2))


def fields_for(platform: str) -> tuple:
    """Resolve the per-platform ``(field, weight)`` tuple (Apple default)."""
    return PLAY_FIELDS if platform == "play" else APPLE_FIELDS


def _field_names(fields: Sequence) -> List[str]:
    return [f for f, _ in fields]


def _phrase_fields(fields: Sequence) -> List[tuple]:
    """The high-signal fields YAKE phrases are built from (top-2 by weight).

    For Apple that is Title + Subtitle (matches slice 02); for Play Title +
    Short. The long / weakly-indexed field is excluded — phrases there are
    noise for ASO. Sentence-base [0.0, 0.5] by rank is preserved.
    """
    ordered = sorted(enumerate(fields), key=lambda iw: (-iw[1][1], iw[0]))
    return [fw for _, fw in ordered[:2]]


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

# Inline fallback set — only used when neither stopwordsiso nor spaCy
# import. Kept as a last-resort fallback per the PRD.
_FALLBACK_STOPWORDS: set = {
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

# ASO-valuable terms that general NLP stop-word lists wrongly kill.
# Carved out after the curated union is built (per PRD §P1).
_ASO_CARVEOUT = {
    "best", "free", "app", "pro", "kostenlos", "neu", "new",
    "text", "top", "work", "open",
}

# German subordinating conjunctions missing even from the stopwordsiso +
# spaCy union — these leak persistently and must be explicitly added.
_MANUAL_DE_CONJUNCTIONS = {
    "sodass", "damit", "obwohl", "während", "weil",
}

# Domain-noise: app/corpus-specific junk, separate from linguistic
# stop-words. Callers extend it via the existing ``generics`` argument.
DOMAIN_NOISE = {
    "anbieter", "fenster",
}

# Verb forms that leak through NLP stop-word lists (POS-dependent —
# ``spacy`` tags them as VERB, not stopword). Deferred to P6 for proper
# POS lemmatisation; here we keep a small explicit block.
_VERB_LEAKS = {
    "verlassen", "läuft",
}


def _build_stopwords() -> set:
    """Build a curated DE+EN stop-word set from stopwordsiso and spaCy.

    Merges both permissive-licence (MIT) pure-Python sources, adds
    missing German subordinating conjunctions, and carves out ASO-valuable
    terms that general NLP lists wrongly kill. Falls back to
    ``_FALLBACK_STOPWORDS`` if neither package imports.
    """
    iso = set()
    try:
        import stopwordsiso  # noqa: F811
        iso = set(stopwordsiso.stopwords("de")) | set(stopwordsiso.stopwords("en"))
    except Exception:
        pass

    spacy = set()
    try:
        import spacy.lang.de.stop_words  # noqa: F811
        import spacy.lang.en.stop_words  # noqa: F811
        spacy = (set(spacy.lang.de.stop_words.STOP_WORDS)
                 | set(spacy.lang.en.stop_words.STOP_WORDS))
    except Exception:
        pass

    union = iso | spacy
    if not union:
        union = _FALLBACK_STOPWORDS.copy()
    union |= _MANUAL_DE_CONJUNCTIONS
    union |= _VERB_LEAKS
    union -= _ASO_CARVEOUT
    return union


STOPWORDS: set = _build_stopwords()

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
        if len(tok) >= _MIN_TOKEN_LEN and tok not in blocked and not tok.isdigit()
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
# irregular German plurals (gewohnheit-en, routine-n) and English plurals
# (-s) without mangling roots.
#
# ``er`` (and the redundant genitive ``es``) are deliberately EXCLUDED:
# stripping ``-er`` wrongly merges agent/root nouns that are distinct ASO
# niches — ``poster``→``post``, ``tracker``→``track``, ``master``→``mast``,
# ``planner``→``plan``, ``center``→``cent``, ``folder``→``fold`` — inflating
# both terms' competition with each other's hit sets. ``e``/``en``/``n``/``s``
# carry the real singular/plural grouping (``routine``/``routinen``,
# ``gewohnheit``/``gewohnheiten``, ``tracker``/``trackers``).
_GROUP_SUFFIXES = ("en", "e", "n", "s")


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


def _candidate_phrases(
    field_text: str, stopwords: set = None,
) -> Dict[tuple, int]:
    """Yield n-gram candidate phrases (n=2..3) -> occurrence count.

    Phrases are built from *raw* tokens (no pre-stripping of stopwords)
    so multi-word phrases like ``sprache zu text`` survive. YAKE-style
    edge filtering drops candidates that start or end with a stopword,
    but keeps those whose stop-word sits only in the middle. Repeated
    phrases within the field count once per occurrence.
    """
    if stopwords is None:
        stopwords = STOPWORDS
    phrases: Dict[tuple, int] = {}
    if not field_text:
        return phrases
    for sentence in _sentences(field_text):
        toks = _raw_tokens(sentence)
        if len(toks) < 2:
            continue
        for n in range(2, _MAX_PHRASE_LEN + 1):
            for i in range(len(toks) - n + 1):
                gram = tuple(toks[i : i + n])
                if gram[0] in stopwords or gram[-1] in stopwords:
                    continue
                # drop phrases with a pure-number edge ("4000 zeichen",
                # "top 100") — numeric edges are ASO noise, not keywords.
                if gram[0].isdigit() or gram[-1].isdigit():
                    continue
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

    Slice 04: the field set is discovered dynamically (every ``<field>_docs``
    key present on the records), so the same function serves Apple
    (``title_docs``/``subtitle_docs``/``description_docs``) and Play
    (``title_docs``/``short_docs``/``long_docs``) without branching.
    """
    fields = sorted({
        k[: -len("_docs")]
        for rec in term_records.values()
        for k in rec
        if k.endswith("_docs")
    })
    groups: Dict[str, dict] = {}
    for surface, rec in term_records.items():
        key = morph_key(surface)
        bucket = groups.setdefault(
            key,
            {
                "variants": set(),
                "tf_weighted": 0,
                "occurrences": 0,
                **{f + "_docs": set() for f in fields},
            },
        )
        bucket["variants"].add(surface)
        for f in fields:
            bucket[f + "_docs"] |= rec.get(f + "_docs", set())
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
        rec = {
            "term": display,
            "variants": variants,
            "tf_weighted": bucket["tf_weighted"],
            "occurrences": bucket["occurrences"],
        }
        for f in fields:
            rec[f + "_docs"] = bucket[f + "_docs"]
        merged.append(rec)
    return merged


def extract_keywords(
    documents: Iterable[Mapping[str, str]],
    *,
    generics: Iterable[str] = (),
    seed_description: str = "",
    suggest_terms: Iterable[str] = (),
    min_freq: int = 2,
    max_phrases: int = 40,
    fields: Sequence = None,
) -> List[Dict]:
    """Extract scored-candidate keyword records from competitor documents.

    Each ``document`` is a mapping carrying the slot fields declared by
    ``fields`` (default Apple: ``title``/``subtitle``/``description``; Play:
    ``title``/``short``/``long``). Returns one record per candidate term,
    carrying the per-field doc-hit counts (``<field>_hits``) the scorer needs:

        {
          "term", "variants", "is_phrase",
          "<field>_hits" for each field,
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
    field_defs = tuple(fields) if fields is not None else APPLE_FIELDS
    field_names = _field_names(field_defs)
    phrase_field_defs = _phrase_fields(field_defs)
    generic = {g.lower() for g in generics if g} | PLATFORM_GENERICS
    blocked = STOPWORDS | generic | DOMAIN_NOISE
    suggest = {s.lower().strip() for s in suggest_terms if s and s.strip()}

    # ---- single-term pass (position-weighted) ----
    single: Dict[str, dict] = {}
    # ---- phrase pass (YAKE) ----
    phrase_freq: Dict[tuple, int] = {}
    phrase_sent_index: Dict[tuple, float] = {}

    for idx, doc in enumerate(docs):
        for fname, weight in field_defs:
            field_text = doc.get(fname, "") or ""
            field_unique = set()
            for tok in _raw_tokens(field_text):
                if len(tok) < _MIN_TOKEN_LEN or tok in blocked or tok.isdigit():
                    continue
                field_unique.add(tok)
            for tok in field_unique:
                rec = single.get(tok)
                if rec is None:
                    rec = {"tf_weighted": 0, "occurrences": 0}
                    for fn in field_names:
                        rec[fn + "_docs"] = set()
                    single[tok] = rec
                rec[fname + "_docs"].add(idx)
                rec["tf_weighted"] += weight
                rec["occurrences"] += 1

        # YAKE phrases from the high-signal fields (top-2 by weight).
        for rank, (fname, _w) in enumerate(phrase_field_defs):
            field_text = doc.get(fname, "") or ""
            sentence_base = float(rank) * 0.5  # 0.0 then 0.5
            grams = _candidate_phrases(field_text, stopwords=blocked)
            for gram, freq in grams.items():
                # drop phrases whose every token is generic/stopword-ish
                if all(g in blocked for g in gram):
                    continue
                phrase_freq[gram] = phrase_freq.get(gram, 0) + freq
                # earliest sentence index seen (deterministic: min)
                prev = phrase_sent_index.get(gram)
                if prev is None or sentence_base < prev:
                    phrase_sent_index[gram] = sentence_base

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
        cand = {
            "term": surface,
            "variants": rec["variants"],
            "is_phrase": False,
            "tf_weighted": rec["tf_weighted"],
            "occurrences": rec["occurrences"],
        }
        all_docs: set = set()
        for fn in field_names:
            docs_set = rec.get(fn + "_docs", set())
            cand[fn + "_hits"] = len(docs_set)
            all_docs |= docs_set
        cand["doc_freq"] = len(all_docs)
        cand["suggest"] = surface in suggest
        candidates.append(cand)

    # phrase candidates (bounded) -> recompute per-doc field hits
    for gram, freq in ranked_phrases[:max_phrases]:
        if freq < min_freq:
            continue
        phrase_str = " ".join(gram)
        per_field_docs = {fn: set() for fn in field_names}
        tf_weighted = 0
        for idx, doc in enumerate(docs):
            for fname, weight in field_defs:
                if _phrase_in_field(doc.get(fname, "") or "", gram):
                    per_field_docs[fname].add(idx)
                    tf_weighted += weight
        all_docs = set()
        for fn in field_names:
            all_docs |= per_field_docs[fn]
        cand = {
            "term": phrase_str,
            "variants": [phrase_str],
            "is_phrase": True,
            "tf_weighted": tf_weighted,
            "doc_freq": len(all_docs),
            "occurrences": freq,
            "suggest": phrase_str in suggest,
        }
        for fn in field_names:
            cand[fn + "_hits"] = len(per_field_docs[fn])
        candidates.append(cand)

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
                "tf_weighted": 0,
                "doc_freq": 0,
                "occurrences": 0,
                "suggest": True,
                **{fn + "_hits": 0 for fn in field_names},
            }
        )

    candidates.sort(
        key=lambda c: (-c["occurrences"], -c["tf_weighted"], c["term"])
    )
    return candidates
