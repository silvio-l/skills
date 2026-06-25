#!/usr/bin/env python3
"""Trivial keyword extraction for the skeleton slice.

This is deliberately minimal — title tokens only — just enough to prove
the artefact flow (``keywords.json`` populated end to end). The real
engine (YAKE phrases + TF-IDF position weighting + Search-Suggest)
lands in slice 02. Do not mistake these numbers for quality.

A token is a lowercased alphanumeric run of length >= 3 that is not a
stopword and not a generic term. Extraction is deterministic: output is
sorted by ``(-title_hits, term)`` so identical input yields identical
output.
"""

from __future__ import annotations

import re
from typing import Dict, Iterable, List

_MIN_TOKEN_LEN = 3
_TOKEN_RE = re.compile(r"[0-9a-zà-öø-ÿ]+")

# Minimal DE + EN stopword / generic filter (the full lists arrive with
# the real engine in slice 02). Category-name generics are added by the
# caller via :func:`extract_keywords`.
STOPWORDS = {
    # EN
    "the", "and", "for", "with", "your", "you", "app", "apps", "all",
    "are", "new", "now", "from", "get", "has", "have", "this", "that",
    # DE
    "und", "fur", "für", "der", "die", "das", "mit", "ist", "ein",
    "eine", "app", "apps", "von", "dir", "ich", "sie", "nicht", "auch",
    "mehr", "noch", "aber",
}


def tokenize(text: str) -> List[str]:
    """Split free text into lowercased, filtered tokens."""
    if not text:
        return []
    return [
        tok
        for tok in _TOKEN_RE.findall(text.lower())
        if len(tok) >= _MIN_TOKEN_LEN and tok not in STOPWORDS
    ]


def extract_keywords(
    titles: Iterable[str],
    generics: Iterable[str] = (),
) -> List[Dict]:
    """Extract title-token keywords across competitor titles.

    Returns ``[{"term", "title_hits"}, ...]`` sorted by
    ``(-title_hits, term)``. ``generics`` (typically the category name
    and platform words) are dropped alongside the builtin stopwords.
    """
    generic = {g.lower() for g in generics if g}
    blocked = STOPWORDS | generic
    hits: Dict[str, int] = {}
    # Per-title sets so a term repeated within one title counts once.
    for title in titles:
        seen = set()
        for tok in _TOKEN_RE.findall((title or "").lower()):
            if len(tok) < _MIN_TOKEN_LEN or tok in blocked:
                continue
            seen.add(tok)
        for tok in seen:
            hits[tok] = hits.get(tok, 0) + 1
    extracted = [{"term": term, "title_hits": n} for term, n in hits.items()]
    extracted.sort(key=lambda e: (-e["title_hits"], e["term"]))
    return extracted
