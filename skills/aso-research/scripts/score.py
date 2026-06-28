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
          **max-normalised** across the run (cosine / max_cosine × 100) so
          the most-relevant term reaches ~100 and the fixed thresholds
          (split ≥ 50, niche > 50) stay comparable; +15 if the term appears
          in Apple/Play Search-Suggest autocomplete; clamped to [0, 100].
          A single-term cosine reduces to the term's normalised TF-IDF
          weight in the seed profile. A **phrase**'s cosine is the mean of
          its component tokens' seed weights (the exact phrase string never
          occurs verbatim in the tokenised seed, so a naive lookup scored
          every phrase 0 — the bug this aggregation fixes).

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

# ---------------------------------------------------------------------------
# Per-platform slot-weighting (slice 04 — generalised, shared engine)
# ---------------------------------------------------------------------------
# The Competition/Relevance engine is **shared** across platforms. Each
# platform maps its own slots into the same Competition math via a
# slot->weight map. The hits live on the extracted record under
# ``<slot>_hits`` (built by :func:`extract.extract_keywords` from the same
# field tuple). Weights are documented per platform so the distinct ASO
# models are honoured (Apple weights its hidden Keyword Field + weakly-indexed
# description; Play weights the strong Short Description + fully-indexed Long).

# Apple (PRD verbatim): Title x5 · Subtitle x3 · Description x1 (sum 9).
# Apple's description is only *weakly* indexed -> weight 1.
APPLE_SLOT_WEIGHTS: Dict[str, int] = {
    "title": 5,
    "subtitle": 3,
    "description": 1,
}

# Play (slice 04 decision, documented under the issue's ``decisions:``):
# Title x5 (strongest, same as Apple) · Short Description x4 (a *strong*
# ranking factor in Play's model — weighted higher than Apple's Subtitle x3)
# · Long Description x2 (Play's long description is *fully* indexed, so it
# contributes meaningfully — double Apple's weakly-indexed description x1).
# Sum 11. Distinct from Apple's 5/3/1.
PLAY_SLOT_WEIGHTS: Dict[str, int] = {
    "title": 5,
    "short": 4,
    "long": 2,
}

# Backwards-compat module-level aliases for the Apple weights (PRD formula).
WEIGHT_TITLE = APPLE_SLOT_WEIGHTS["title"]
WEIGHT_SUBTITLE = APPLE_SLOT_WEIGHTS["subtitle"]
WEIGHT_DESC = APPLE_SLOT_WEIGHTS["description"]
_WEIGHT_SUM = sum(APPLE_SLOT_WEIGHTS.values())  # 9


def slot_weights_for(platform: str) -> Dict[str, int]:
    """Resolve the per-platform slot->weight map (Apple default)."""
    if platform == "play":
        return dict(PLAY_SLOT_WEIGHTS)
    return dict(APPLE_SLOT_WEIGHTS)


# ---------------------------------------------------------------------------
# Exact-boundary pure decisions (unit-tested with integers)
# ---------------------------------------------------------------------------

def competition_score_weighted(hits: Mapping[str, int], weights: Mapping[str, int], n_docs: int) -> int:
    """Position-weighted competition share for an arbitrary slot model, 0..100.

    Generalised core (slice 04): ``hits`` maps each slot name to its doc-hit
    count; ``weights`` maps each slot name to its TF-IDF position weight. The
    formula is the PRD Competition formula generalised over the slots::

        100 * sum(weights[slot] * (hits[slot] / n_docs)) / sum(weights)

    0 when ``n_docs <= 0``. Apple and Play both route through here with their
    own slot maps, so the engine is shared, not duplicated.
    """
    if n_docs <= 0:
        return 0
    weight_sum = sum(weights.values())
    if weight_sum <= 0:
        return 0
    total = 0.0
    for slot, weight in weights.items():
        share = int(hits.get(slot, 0)) / n_docs
        total += weight * share
    raw = 100.0 * total / weight_sum
    return max(0, min(100, int(round(raw))))


def competition_score(title_hits: int, subtitle_hits: int, description_hits: int, n_docs: int) -> int:
    """Position-weighted Apple competition share, 0..100. 0 when no documents.

    Backwards-compatible Apple entry point (slice 02 contract). Delegates to
    the generalised :func:`competition_score_weighted` with the Apple slot
    weights, so Apple's numeric outputs are **byte-identical** to slice 02.
    """
    return competition_score_weighted(
        {"title": title_hits, "subtitle": subtitle_hits, "description": description_hits},
        APPLE_SLOT_WEIGHTS,
        n_docs,
    )


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


def _cosine_relevance(seed_profile: Mapping[str, float], term: str, *, is_phrase: bool = False) -> float:
    """Cosine similarity between a term and the seed profile.

    Single term: the term's own normalised TF-IDF weight in the seed. Phrase:
    the **mean of its component tokens'** seed weights — the verbatim phrase
    string never appears in the (single-token) seed profile, so a direct
    lookup scored every multi-word ASO phrase 0. Component tokens are the
    phrase's stopword-stripped tokens (``extract.tokenize``).
    """
    norm = math.sqrt(sum(v * v for v in seed_profile.values()))
    if norm <= 0.0:
        return 0.0
    if not is_phrase and " " not in term:
        return seed_profile.get(term, 0.0) / norm
    toks = _seed_term_tokens(term)
    if not toks:
        return seed_profile.get(term, 0.0) / norm
    agg = sum(seed_profile.get(t, 0.0) for t in toks) / len(toks)
    return agg / norm


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
    platform: str = "apple",
    slot_weights: Mapping[str, int] = None,
) -> List[Dict]:
    """Attach Competition/Relevance/Opportunity/split/is_gap to candidates.

    ``extracted`` are records from :func:`extract.extract_keywords`.
    ``n_docs`` normalises the shares (guard: 0 -> Competition 0).
    ``suggest_terms`` is the autocomplete set for the +15 relevance boost.

    Slice 04: the engine is shared across platforms via the per-platform
    ``slot_weights`` map (defaults to the platform's standard weights). Each
    emitted row is tagged ``platform`` (``"apple"`` or ``"play"``) so the
    unified score table (``keywords.json``) carries both verticals. The hit
    fields read are ``<slot>_hits`` for every slot in the weight map.
    """
    weights = dict(slot_weights) if slot_weights else slot_weights_for(platform)
    suggest = {s.lower().strip() for s in (suggest_terms or []) if s and s.strip()}
    seed_tokens = set(_description_tokens(seed_description))

    vocab = sorted({c["term"] for c in extracted})
    idf: Dict[str, float] = {}
    for c in extracted:
        df = c.get("doc_freq", 0)
        idf[c["term"]] = math.log((n_docs + 1) / (1 + df)) if n_docs > 0 else 0.0
    seed_profile = _seed_tfidf_profile(seed_description, vocab, idf)

    # Compute all raw cosine similarities first to enable max-normalisation
    # (per PRD §P1: Relevance = cosine / max_cosine × 100, so the most
    # relevant term reaches ~100 and fixed thresholds become comparable).
    raw_cos = {}
    max_cos = 0.0
    for c in extracted:
        term = c["term"]
        raw = _cosine_relevance(seed_profile, term, is_phrase=bool(c.get("is_phrase")))
        raw_cos[term] = raw
        if raw > max_cos:
            max_cos = raw

    scored: List[Dict] = []
    for c in extracted:
        term = c["term"]
        hits = {slot: int(c.get(slot + "_hits", 0)) for slot in weights}
        # is_gap is driven by the Title slot (present on every platform).
        title_hits = hits.get("title", int(c.get("title_hits", 0)))

        competition = competition_score_weighted(hits, weights, n_docs)
        raw = raw_cos[term]
        if max_cos > 0.0:
            relevance = int(round(raw / max_cos * 100.0))
        else:
            relevance = 0
        if term in suggest:
            relevance += SUGGEST_BOOST
        relevance = max(0, min(100, relevance))

        opportunity = opportunity_score(competition, relevance)
        is_gap = title_hits > 0 and not _term_in_seed(term, seed_tokens)

        row: Dict = {
            "term": term,
            "platform": platform,
            "is_phrase": bool(c.get("is_phrase", False)),
            "competition": competition,
            "relevance": relevance,
            "opportunity": opportunity,
            "niche_bonus": NICHE_BONUS if niche_bonus_applies(competition, relevance) else 0,
            "split": split_label(relevance),
            "is_gap": is_gap,
            "suggest": bool(c.get("suggest", False)) or term in suggest,
        }
        # carry the per-slot hit counts (platform-specific field names)
        for slot in weights:
            row[slot + "_hits"] = hits[slot]
        scored.append(row)

    # Total deterministic order across platforms: a term may appear once per
    # platform, so ``platform`` is the final tie-breaker (stable for an
    # Apple-only corpus since every row shares the same platform value).
    scored.sort(key=lambda e: (-e["opportunity"], -e["relevance"], e["term"], e["platform"]))
    return scored
