#!/usr/bin/env python3
"""Pure-logic synthesis layer for seo-audit.

Inputs: a flat list of finding dicts produced by any audit module
(brand_scan, inventory, eventually external-probes). Each finding may
carry `severity`, `user_impact`, `fix_effort`, and `category`. Missing
weights fall back to the documented defaults in `synthesis.md`.

Outputs: `{findings: [...sorted by score desc, then by tiebreaker...],
groups: [{category, count}]}`.

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
    return (
        finding.get("file_path", ""),
        finding.get("line_number", 0),
        finding.get("match", ""),
        finding.get("category", DEFAULT_CATEGORY),
    )


def _sort_key(finding: Dict):
    # Sort by score DESC, then file_path/line/match ASC for determinism.
    return (
        -finding.get("score", 0.0),
        finding.get("file_path", ""),
        finding.get("line_number", 0),
        str(finding.get("match", "")).lower(),
    )


def synthesize(raw_findings: List[Dict]) -> Dict:
    """Dedup, score, sort, group."""
    seen = {}
    for f in raw_findings:
        key = _dedup_key(f)
        if key not in seen:
            entry = dict(f)
            entry.setdefault("category", DEFAULT_CATEGORY)
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
    return {"findings": findings, "groups": groups}


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
