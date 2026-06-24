#!/usr/bin/env python3
"""Pure-logic synthesis layer for seo-audit.

Inputs: a flat list of finding dicts produced by any audit module
(brand_scan, inventory, eventually external-probes). Each finding may
carry `severity`, `user_impact`, `fix_effort`, `category`, `dimension`,
and `track`. Missing weights fall back to the documented defaults in
`synthesis.md`.

Outputs:
    {
        findings: [...sorted by score desc, then by tiebreaker...],
        groups: [{category, count}],
        headline_score: float,          # 0-100 weighted aggregate
        dimensions_breakdown: {dim: float},
    }

The constants live here so the skill is *versioned* — changing a weight
is a code change, reviewable in git history.
"""

from __future__ import annotations

import json
import sys
from typing import List, Dict

SEVERITY_WEIGHTS = {"high": 3, "med": 2, "medium": 2, "low": 1}
DEFAULT_SEVERITY = "med"
DEFAULT_USER_IMPACT = 2
DEFAULT_FIX_EFFORT = 2
DEFAULT_CATEGORY = "uncategorized"

# ----- Dimension / track defaults -------------------------------------------

DEFAULT_DIMENSION = "brand"
DEFAULT_TRACK = "technical"

# Dimension weights for the headline score (version: v1).
# Must sum to exactly 1.0.  Change this constant — and bump the version
# string in audit.py — whenever a weight is adjusted.
# "brand" carries anti-vocabulary signal; slices 02 (GEO) and 03 (Schema)
# populate the remaining dimensions.
DIMENSION_WEIGHTS_V1: Dict[str, float] = {
    "technical":   0.20,
    "schema":      0.15,
    "onpage":      0.15,
    "content":     0.15,
    "geo":         0.15,
    "performance": 0.10,
    "images":      0.05,
    "brand":       0.05,
}


def _severity_weight(sev) -> int:
    if isinstance(sev, (int, float)):
        return int(sev)
    return SEVERITY_WEIGHTS.get(str(sev).lower(), SEVERITY_WEIGHTS[DEFAULT_SEVERITY])


def score(finding: Dict) -> float:
    sev = _severity_weight(finding.get("severity", DEFAULT_SEVERITY))
    impact = int(finding.get("user_impact", DEFAULT_USER_IMPACT))
    effort = int(finding.get("fix_effort", DEFAULT_FIX_EFFORT))
    effort = max(effort, 1)  # never divide by zero
    return round(sev * impact / effort, 4)


def _dedup_key(finding: Dict):
    # `dimension` is included so two findings that differ only in dimension
    # are kept as distinct entries.  Old findings without `dimension` fall
    # back to DEFAULT_DIMENSION, preserving prior dedup behaviour.
    return (
        finding.get("file_path", ""),
        finding.get("line_number", 0),
        finding.get("match", ""),
        finding.get("category", DEFAULT_CATEGORY),
        finding.get("dimension", DEFAULT_DIMENSION),
    )


def _sort_key(finding: Dict):
    # Sort by score DESC, then file_path/line/match ASC for determinism.
    return (
        -finding.get("score", 0.0),
        finding.get("file_path", ""),
        finding.get("line_number", 0),
        str(finding.get("match", "")).lower(),
    )


def _compute_dimension_scores(findings: List[Dict]) -> Dict[str, float]:
    """Return a 0-100 score per dimension.

    Penalty for a dimension = sum of finding scores in that dimension.
    Dimension score = max(0, 100 - penalty), rounded to one decimal.
    Dimensions listed in DIMENSION_WEIGHTS_V1 but absent from findings
    default to 100.0 (no issues found → full marks).
    """
    penalties: Dict[str, float] = {}
    for f in findings:
        dim = f.get("dimension", DEFAULT_DIMENSION)
        penalties[dim] = penalties.get(dim, 0.0) + f.get("score", 0.0)

    scores: Dict[str, float] = {}
    for dim in DIMENSION_WEIGHTS_V1:
        penalty = penalties.get(dim, 0.0)
        scores[dim] = round(max(0.0, 100.0 - penalty), 1)
    return scores


def _compute_headline_score(dimension_scores: Dict[str, float]) -> float:
    """Weighted average of dimension scores → headline score 0-100."""
    total = sum(
        DIMENSION_WEIGHTS_V1[dim] * dimension_scores.get(dim, 100.0)
        for dim in DIMENSION_WEIGHTS_V1
    )
    return round(total, 1)


def synthesize(raw_findings: List[Dict]) -> Dict:
    """Dedup, score, sort, group, and compute headline score."""
    seen = {}
    for f in raw_findings:
        key = _dedup_key(f)
        if key not in seen:
            entry = dict(f)
            entry.setdefault("category", DEFAULT_CATEGORY)
            entry.setdefault("dimension", DEFAULT_DIMENSION)
            entry.setdefault("track", DEFAULT_TRACK)
            entry["score"] = score(entry)
            seen[key] = entry

    findings = sorted(seen.values(), key=_sort_key)

    counts: Dict[str, int] = {}
    for f in findings:
        counts[f["category"]] = counts.get(f["category"], 0) + 1
    groups = [
        {"category": cat, "count": cnt}
        for cat, cnt in sorted(counts.items())
    ]

    dim_scores = _compute_dimension_scores(findings)
    headline = _compute_headline_score(dim_scores)

    return {
        "findings": findings,
        "groups": groups,
        "headline_score": headline,
        "dimensions_breakdown": dim_scores,
    }


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] != "-":
        with open(sys.argv[1], "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.load(sys.stdin)
    result = synthesize(data)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
