#!/usr/bin/env python3
"""Placeholder keyword scoring for the skeleton slice.

A deliberately coarse signal — *not* the PRD's real Competition/Relevance
formula (that is slice 02). This exists only to populate
``keywords.json`` deterministically so the artefact flow is provable.

Signals:
    competition (0-100) — placeholder title-share: what fraction of the
        discovered competitors carry the term in their title.
    relevance   (0-100) — placeholder bias: 100 when the term is one of
        the seed keywords, 60 when it appears in the seed description,
        else a flat 30 baseline.

Output is sorted by ``(-relevance, -competition, term)`` so identical
input is byte-identical. Guarded against division-by-zero when no
competitors were discovered.
"""

from __future__ import annotations

from typing import Dict, List

# Placeholder relevance constants (deliberately arbitrary; slice 02
# replaces them with TF-IDF cosine similarity + Search-Suggest boost).
REL_SEED = 100
REL_DESCRIPTION = 60
REL_BASELINE = 30


def _description_terms(description: str) -> set:
    # Reuse extract.tokenize's filtering so "description" relevance uses
    # the same notion of a token as extraction. Imported lazily to avoid
    # a hard import cycle in tools that only want the constants.
    import extract  # type: ignore

    return set(extract.tokenize(description))


def score_keywords(
    extracted: List[Dict],
    seed_keywords: List[str],
    description: str,
    n_competitors: int,
) -> List[Dict]:
    """Attach placeholder competition/relevance to extracted keywords."""
    seeds_lower = {s.lower() for s in (seed_keywords or [])}
    desc_terms = _description_terms(description or "")
    denom = n_competitors if n_competitors and n_competitors > 0 else 0

    scored: List[Dict] = []
    for entry in extracted:
        term = entry["term"]
        title_hits = entry.get("title_hits", 0)
        competition = round(100 * title_hits / denom) if denom else 0
        if term in seeds_lower:
            relevance = REL_SEED
        elif term in desc_terms:
            relevance = REL_DESCRIPTION
        else:
            relevance = REL_BASELINE
        scored.append(
            {
                "term": term,
                "competition": competition,
                "relevance": relevance,
                "title_hits": title_hits,
            }
        )

    scored.sort(key=lambda e: (-e["relevance"], -e["competition"], e["term"]))
    return scored
