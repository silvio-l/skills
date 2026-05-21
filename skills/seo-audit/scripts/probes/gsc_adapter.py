#!/usr/bin/env python3
"""Google Search Console (GSC) adapter — normaliser + injectable client.

Runtime: this adapter consumes the `mcp__gsc__*` MCP tools. The live
wiring composes three calls (`get_performance_overview`,
`check_indexing_issues`, `get_search_by_page_query`) into a single
composite dict — that is the shape the normaliser expects.

The worker cannot call MCP tools at unit-test time, so `run()` accepts
an injected `gsc_client` callable. The live wiring is documented in
skills/seo-audit/probes.md.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional


CTR_LOW_THRESHOLD = 0.01      # per-page CTR considered "low"
CTR_AVG_LOW_THRESHOLD = 0.02  # average site CTR considered "low"
IMPRESSIONS_RELEVANCE = 1000  # ignore noise from low-impression queries


def normalise(raw, url: str) -> List[Dict]:
    if not raw or not isinstance(raw, dict):
        return []
    out: List[Dict] = []

    # 1. Indexing issues.
    issues = ((raw.get("indexing") or {}).get("issues") or [])
    for issue in issues:
        page = issue.get("url") or url
        status = issue.get("status") or "indexing issue"
        out.append({
            "category":    "indexing",
            "severity":    "high",
            "user_impact": 3,
            "fix_effort":  2,
            "file_path":   page,
            "line_number": 0,
            "match":       f"indexing:{status}"[:60],
            "rationale":   f"GSC: {status} for {page}",
            "suggested_replacement": "",
        })

    # 2. Low-CTR pages (only when impressions clear the noise threshold).
    for entry in raw.get("low_ctr_pages") or []:
        ctr = float(entry.get("ctr") or 0.0)
        impressions = int(entry.get("impressions") or 0)
        if ctr >= CTR_LOW_THRESHOLD or impressions < IMPRESSIONS_RELEVANCE:
            continue
        page = entry.get("page") or url
        query = entry.get("query") or ""
        out.append({
            "category":    "gsc",
            "severity":    "med",
            "user_impact": 2,
            "fix_effort":  2,
            "file_path":   page,
            "line_number": 0,
            "match":       f"ctr:{query}"[:60],
            "rationale": (
                f"Page CTR {ctr:.4f} for query \"{query}\" "
                f"({impressions} impressions, position "
                f"{entry.get('position', '?')})"
            ),
            "suggested_replacement": "Sharpen the title/meta-description.",
        })

    # 3. Performance summary — average CTR too low.
    perf = raw.get("performance") or {}
    avg_ctr = float(perf.get("avg_ctr") or 0.0)
    if avg_ctr and avg_ctr < CTR_AVG_LOW_THRESHOLD:
        out.append({
            "category":    "gsc",
            "severity":    "med",
            "user_impact": 3,
            "fix_effort":  3,
            "file_path":   perf.get("site") or url,
            "line_number": 0,
            "match":       "gsc:avg-ctr-low",
            "rationale": (
                f"Average CTR {avg_ctr:.4f} "
                f"(impressions {perf.get('total_impressions')}, "
                f"avg position {perf.get('avg_position')})"
            ),
            "suggested_replacement": "",
        })
    return out


# ---------------------------------------------------------------------------
# Injectable client.
# ---------------------------------------------------------------------------

def _default_gsc_client(site: str):  # pragma: no cover — MCP wiring, live only
    """Real MCP wiring; documented in probes.md, not unit-tested."""
    return None


def run(url: str, gsc_client: Optional[Callable[[str], Optional[Dict]]] = None) -> List[Dict]:
    client = gsc_client or _default_gsc_client
    composite = client(url)
    if composite is None:
        return []
    return normalise(composite, url=url)
