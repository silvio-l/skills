#!/usr/bin/env python3
"""PageSpeed Insights API adapter — normaliser + injectable fetcher.

Shell-out: `curl https://www.googleapis.com/pagespeedonline/v5/runPagespeed?
url=<url>&key=$PAGESPEED_API_KEY`. The shell-out is not unit-tested; the
fetcher is injected during tests.

Skip rule (AC5): if `PAGESPEED_API_KEY` is absent from the environment,
`run()` logs a skip on stderr and returns an empty list. No exception,
no failure.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from typing import Callable, Dict, List, Optional


CRUX_SEVERITY = {
    "FAST":    None,
    "AVERAGE": "med",
    "SLOW":    "high",
}

CATEGORY_GOOD_THRESHOLD = 0.9
CATEGORY_POOR_THRESHOLD = 0.5


def _severity_for_category_score(score) -> str:
    if score is None:
        return "low"
    if score < CATEGORY_POOR_THRESHOLD:
        return "high"
    if score < CATEGORY_GOOD_THRESHOLD:
        return "med"
    return "low"


def normalise(raw, url: str) -> List[Dict]:
    if not raw or not isinstance(raw, dict):
        return []
    out: List[Dict] = []

    # 1. CrUX field-data metrics.
    metrics = ((raw.get("loadingExperience") or {}).get("metrics") or {})
    for name in sorted(metrics):
        spec = metrics[name] or {}
        sev = CRUX_SEVERITY.get(spec.get("category"))
        if sev is None:
            continue
        out.append({
            "category":    "performance",
            "severity":    sev,
            "user_impact": 3,
            "fix_effort":  3,
            "file_path":   url,
            "line_number": 0,
            "match":       f"crux:{name}",
            "rationale": (
                f"CrUX {name} percentile {spec.get('percentile')}, "
                f"category {spec.get('category')}"
            ),
            "suggested_replacement": "",
        })

    # 2. Lighthouse categories embedded in PSI.
    cats = ((raw.get("lighthouseResult") or {}).get("categories") or {})
    for cat_id in sorted(cats):
        meta = cats[cat_id] or {}
        score = meta.get("score")
        if score is None or score >= CATEGORY_GOOD_THRESHOLD:
            continue
        out.append({
            "category":    cat_id if cat_id != "best-practices" else "best-practices",
            "severity":    _severity_for_category_score(score),
            "user_impact": 3,
            "fix_effort":  3,
            "file_path":   url,
            "line_number": 0,
            "match":       f"category:{cat_id}",
            "rationale": (
                f"PageSpeed {meta.get('title', cat_id)} score: "
                f"{round(score, 2)} (target ≥ 0.9)"
            ),
            "suggested_replacement": "",
        })

    return out


# ---------------------------------------------------------------------------
# Injectable fetcher + thin shell-out.
# ---------------------------------------------------------------------------

PSI_ENDPOINT = (
    "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
)


def _curl_fetcher(api_url: str) -> Optional[Dict]:  # pragma: no cover — live only
    try:
        proc = subprocess.run(
            ["curl", "-sSL", "--max-time", "60", api_url],
            capture_output=True, text=True, timeout=65,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def run(
    url: str,
    env: Optional[Dict[str, str]] = None,
    fetcher: Optional[Callable[[str], Optional[Dict]]] = None,
) -> List[Dict]:
    env = env if env is not None else os.environ
    key = env.get("PAGESPEED_API_KEY")
    if not key:
        print(
            "pagespeed_adapter: PAGESPEED_API_KEY not set — skipping.",
            file=sys.stderr,
        )
        return []
    api_url = f"{PSI_ENDPOINT}?url={url}&key={key}"
    fetch = fetcher or _curl_fetcher
    raw = fetch(api_url)
    if raw is None:
        return []
    return normalise(raw, url=url)
