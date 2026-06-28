#!/usr/bin/env python3
"""Keyword clustering + target-set recommendation (deterministic, no LLM).

Turns the long scored keyword table into something actionable:

* :func:`cluster_keywords` groups related keywords into a handful of **themes**
  by shared morphological token (greedy set-cover: the token covering the most
  still-unassigned keywords anchors the next cluster), so "transkription /
  transkriptor / transkribieren" land together, distinct from "spracheingabe /
  sprache / sprechen".
* :func:`recommend_target_set` picks a concrete **keyword target set** per
  store slot (Apple Title 30 / Subtitle 30 / hidden Keyword-Field 100), drawing
  the strongest term from *distinct* themes so the listing covers the niche
  rather than repeating one idea — grounding the LLM Listing Strategist.

Pure + deterministic: identical input → identical output (every tie broken by a
stable key). ``extract`` is imported for the same tokeniser/morphology the
scorer uses, so clusters align with the scored vocabulary.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

# Apple slot char budgets (the canonical target). Play/MS reuse Title/“long”.
TITLE_MAX = 30
SUBTITLE_MAX = 30
KEYWORD_FIELD_MAX = 100


def _kw_tokens(term: str) -> List[str]:
    """Morphological tokens of a keyword (same tokeniser the scorer uses)."""
    import extract  # type: ignore

    return sorted({extract.morph_key(t) for t in extract.tokenize(term)})


def _rank(k: Mapping) -> tuple:
    """Stable ranking key: app-type-weighted rank, then opportunity, then term."""
    return (
        -float(k.get("rank_score", k.get("opportunity", 0))),
        -int(k.get("opportunity", 0)),
        str(k.get("term", "")),
    )


def cluster_keywords(
    keywords: Sequence[Mapping],
    *,
    max_clusters: int = 6,
    min_cluster: int = 2,
    pool: int = 120,
) -> List[Dict]:
    """Group keywords into up to ``max_clusters`` themes by shared token.

    Only keywords with ``opportunity > 0`` are clustered, capped at ``pool``
    (ranked). Returns a list of ``{"head", "label", "terms", "opportunity",
    "size"}`` sorted by aggregate opportunity. Keywords sharing no qualifying
    theme are left out of the clusters (they still live in the full table).
    """
    items = [k for k in keywords if int(k.get("opportunity", 0)) > 0]
    items = sorted(items, key=_rank)[:pool]
    if not items:
        return []

    tokens_per = [_kw_tokens(k.get("term", "")) for k in items]
    tok_index: Dict[str, set] = {}
    for i, toks in enumerate(tokens_per):
        for t in toks:
            tok_index.setdefault(t, set()).add(i)

    assigned: set = set()
    clusters: List[Dict] = []
    while len(clusters) < max_clusters:
        best_tok = None
        best_cov: set = set()
        # deterministic: most coverage, tie broken by token string
        for tok in sorted(tok_index):
            cov = tok_index[tok] - assigned
            if len(cov) > len(best_cov) or (len(cov) == len(best_cov) and best_tok is None):
                if len(cov) > len(best_cov):
                    best_tok, best_cov = tok, cov
        if not best_tok or len(best_cov) < min_cluster:
            break
        members = sorted((items[i] for i in best_cov), key=_rank)
        assigned |= best_cov
        clusters.append({
            "head": best_tok,
            "label": str(members[0].get("term", "")),
            "terms": [str(m.get("term", "")) for m in members],
            "opportunity": sum(int(m.get("opportunity", 0)) for m in members),
            "size": len(members),
        })
    clusters.sort(key=lambda c: (-c["opportunity"], c["label"]))
    return clusters


def _pack(terms: Sequence[str], budget: int, *, sep: str = " ") -> List[str]:
    """Greedily take terms (in order) that fit within ``budget`` chars joined by sep."""
    out: List[str] = []
    used = 0
    for t in terms:
        add = len(t) + (len(sep) if out else 0)
        if used + add <= budget:
            out.append(t)
            used += add
    return out


def recommend_target_set(
    keywords: Sequence[Mapping],
    clusters: Sequence[Mapping] = None,
    *,
    platform: str = "apple",
) -> Dict:
    """Recommend which keywords to target per slot (data-driven, deterministic).

    Strategy: take the strongest keyword from each *distinct* theme for the
    visible slots (Title then Subtitle) so they cover different concepts, then
    pack the remaining strong terms into the hidden Keyword-Field. Returns
    ``{"title": [...], "subtitle": [...], "keyword_field": [...]}`` (lists of
    terms). The LLM Listing Strategist turns these into human copy.
    """
    if clusters is None:
        clusters = cluster_keywords(keywords)
    ranked = sorted(
        (k for k in keywords if int(k.get("opportunity", 0)) > 0), key=_rank
    )
    # one representative (highest-rank) term per theme, themes by strength
    theme_terms: List[str] = []
    seen_terms: set = set()
    for c in clusters:
        for t in c.get("terms", []):
            if t not in seen_terms:
                theme_terms.append(t)
                seen_terms.add(t)
                break
    # fall back to plain ranking if clustering produced nothing
    if not theme_terms:
        theme_terms = [str(k.get("term", "")) for k in ranked]

    title = _pack(theme_terms, TITLE_MAX)
    rest = [t for t in theme_terms if t not in set(title)]
    subtitle = _pack(rest, SUBTITLE_MAX)

    # Keyword-Field: distinct, comma-joined, not already in title/subtitle,
    # high-opportunity first; tokens not whole phrases keep it dense.
    used = set(title) | set(subtitle)
    field_pool = [str(k.get("term", "")) for k in ranked if str(k.get("term", "")) not in used]
    keyword_field = _pack(field_pool, KEYWORD_FIELD_MAX, sep=",")
    return {"title": title, "subtitle": subtitle, "keyword_field": keyword_field}


def build_strategy(keywords: Sequence[Mapping], *, platform: str = "apple") -> Dict:
    """Clusters + target set in one call (what the dispatcher serialises)."""
    cl = cluster_keywords(keywords)
    return {
        "clusters": cl,
        "target_set": recommend_target_set(keywords, cl, platform=platform),
    }
