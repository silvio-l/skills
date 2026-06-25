#!/usr/bin/env python3
"""Keyword scoring engine (slice 02 — real Competition/Relevance proxy).

Implements the PRD "Scoring" formulas verbatim. Every number is an
explicit, deterministic **proxy signal** — *never* real search volume.
The report labels them "Competition/Relevance signal".

Formulas (all shares are 0..1, scores rounded to int 0..100):

    Competition (0..100)
        = round( 100 * (5*title_share + 3*sub_share + 1*desc_share) / 9 )
      where title_share = title_hits / n_docs, etc. 0 when n_docs == 0.

    Relevance (0..100)
        = cosine TF-IDF similarity of the term to the seed description,
          scaled to 100, +15 if the term appears in Apple Search-Suggest
          autocomplete, clamped to [0, 100]. Cosine for a single-term
          query reduces to the term's normalised TF-IDF weight inside the
          seed description's profile.

    Opportunity
        = round( Relevance * (100 - Competition) / 100 )
          +10 niche bonus if Competition < 20 AND Relevance > 50
          (strict thresholds).

    split
        "primary-candidate"   if Relevance >= 50  (core concept — fight)
        "long-tail-candidate" otherwise           (peripheral — win cheap)

    is_gap  (flag, not a score)
        True when competitors own the term in their Title (title_hits > 0)
        but the seed concept lacks it (term tokens absent from the seed
        description). Highlights coverage gaps.

The exact boundary decisions (niche bonus, split, opportunity) live in
small named pure functions so the strict thresholds can be unit-tested
directly with integers — no private-method mocking.

Output is sorted by ``(-opportunity, -relevance, term)`` so identical
input is byte-identical.
"""

from __future__ import annotations

import math
from typing import Dict, Iterable, List, Mapping, Sequence

# PRD constants — exact.
SUGGEST_BOOST = 15
NICHE_BONUS = 10
NICHE_COMPETITION_MAX = 20  # strict: Competition < 20
NICHE_RELEVANCE_MIN = 50   # strict: Relevance > 50
PRIMARY_RELEVANCE_MIN = 50  # split threshold: Relevance >= 50

WEIGHT_TITLE = 5
WEIGHT_SUBTITLE = 3
WEIGHT_DESC = 1
_WEIGHT_SUM = WEIGHT_TITLE + WEIGHT_SUBTITLE + WEIGHT_DESC  # 9


# ---------------------------------------------------------------------------
# Exact-boundary pure decisions (unit-tested with integers)
# ---------------------------------------------------------------------------

def competition_score(title_hits: int, subtitle_hits: int, description_hits: int, n_docs: int) -> int:
    """Position-weighted competition share, 0..100. 0 when no documents."""
    if n_docs <= 0:
        return 0
    title_share = title_hits / n_docs
    sub_share = subtitle_hits / n_docs
    desc_share = description_hits / n_docs
    raw = 100.0 * (
        WEIGHT_TITLE * title_share
        + WEIGHT_SUBTITLE * sub_share
        + WEIGHT_DESC * desc_share
    ) / _WEIGHT_SUM
    return max(0, min(100, int(round(raw))))


def niche_bonus_applies(competition: int, relevance: int) -> bool:
    """Strict PRD boundary: Competition < 20 AND Relevance > 50."""
    return competition < NICHE_COMPETITION_MAX and relevance > NICHE_RELEVANCE_MIN


def opportunity_score(competition: int, relevance: int) -> int:
    """Opportunity = round(Relevance*(100-Competition)/100) + niche bonus."""
    base = int(round(relevance * (100 - competition) / 100.0))
    if niche_bonus_applies(competition, relevance):
        base += NICHE_BONUS
    return max(0, min(100, base))


def split_label(relevance: int) -> str:
    """primary-candidate when Relevance >= 50, else long-tail-candidate."""
    return "primary-candidate" if relevance >= PRIMARY_RELEVANCE_MIN else "long-tail-candidate"


# ---------------------------------------------------------------------------
# Cosine relevance
# ---------------------------------------------------------------------------

def _description_tokens(description: str) -> List[str]:
    import extract  # type: ignore

    return extract.tokenize(description or "")


def _seed_tfidf_profile(
    seed_description: str,
    vocabulary: Sequence[str],
    idf: Mapping[str, float],
) -> Dict[str, float]:
    """TF-IDF weight of each vocab term inside the seed description."""
    toks = _description_tokens(seed_description)
    if not toks:
        return {t: 0.0 for t in vocabulary}
    tf: Dict[str, int] = {}
    for t in toks:
        tf[t] = tf.get(t, 0) + 1
    return {t: (tf.get(t, 0) * idf.get(t, 0.0)) for t in vocabulary}


def _cosine_relevance(seed_profile: Mapping[str, float], term: str) -> float:
    """Cosine similarity between a single-term query and the seed profile."""
    norm = math.sqrt(sum(v * v for v in seed_profile.values()))
    if norm <= 0.0:
        return 0.0
    return seed_profile.get(term, 0.0) / norm


def _seed_term_tokens(term: str) -> set:
    import extract  # type: ignore

    return set(extract.tokenize(term))


def _term_in_seed(term: str, seed_tokens: set) -> bool:
    """True when every token of the term appears in the seed description."""
    toks = _seed_term_tokens(term)
    if not toks:
        return False
    return toks.issubset(seed_tokens)


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def score_keywords(
    extracted: List[Mapping],
    *,
    seed_description: str,
    suggest_terms: Iterable[str] = (),
    n_docs: int,
) -> List[Dict]:
    """Attach Competition/Relevance/Opportunity/split/is_gap to candidates.

    ``extracted`` are records from :func:`extract.extract_keywords`.
    ``n_docs`` normalises the shares (guard: 0 -> Competition 0).
    ``suggest_terms`` is the autocomplete set for the +15 relevance boost.
    """
    suggest = {s.lower().strip() for s in (suggest_terms or []) if s and s.strip()}
    seed_tokens = set(_description_tokens(seed_description))

    vocab = sorted({c["term"] for c in extracted})
    idf: Dict[str, float] = {}
    for c in extracted:
        df = c.get("doc_freq", 0)
        idf[c["term"]] = math.log((n_docs + 1) / (1 + df)) if n_docs > 0 else 0.0
    seed_profile = _seed_tfidf_profile(seed_description, vocab, idf)

    scored: List[Dict] = []
    for c in extracted:
        term = c["term"]
        title_hits = int(c.get("title_hits", 0))
        subtitle_hits = int(c.get("subtitle_hits", 0))
        description_hits = int(c.get("description_hits", 0))

        competition = competition_score(title_hits, subtitle_hits, description_hits, n_docs)
        relevance = int(round(_cosine_relevance(seed_profile, term) * 100.0))
        if term in suggest:
            relevance += SUGGEST_BOOST
        relevance = max(0, min(100, relevance))

        opportunity = opportunity_score(competition, relevance)
        is_gap = title_hits > 0 and not _term_in_seed(term, seed_tokens)

        scored.append(
            {
                "term": term,
                "is_phrase": bool(c.get("is_phrase", False)),
                "competition": competition,
                "relevance": relevance,
                "opportunity": opportunity,
                "niche_bonus": NICHE_BONUS if niche_bonus_applies(competition, relevance) else 0,
                "split": split_label(relevance),
                "is_gap": is_gap,
                "title_hits": title_hits,
                "subtitle_hits": subtitle_hits,
                "description_hits": description_hits,
                "suggest": bool(c.get("suggest", False)) or term in suggest,
            }
        )

    scored.sort(key=lambda e: (-e["opportunity"], -e["relevance"], e["term"]))
    return scored
