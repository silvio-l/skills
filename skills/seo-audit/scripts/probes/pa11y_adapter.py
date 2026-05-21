#!/usr/bin/env python3
"""pa11y (axe-runner) adapter — normaliser + thin shell-out.

Shell-out: `npx pa11y <url> --runner axe --reporter json`.
The shell-out is not unit-tested; the live whispaste.de smoke command
exercises it.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Dict, List, Optional


# axe impact → Finding severity.
IMPACT_SEVERITY = {
    "critical": "high",
    "serious":  "high",
    "moderate": "med",
    "minor":    "low",
}

# pa11y type → fallback severity when axe impact missing.
TYPE_SEVERITY = {
    "error":   "high",
    "warning": "med",
    "notice":  "low",
}


def _severity(issue: Dict) -> str:
    impact = (issue.get("runnerExtras") or {}).get("impact")
    if impact in IMPACT_SEVERITY:
        return IMPACT_SEVERITY[impact]
    return TYPE_SEVERITY.get(issue.get("type"), "med")


def normalise(raw, url: str) -> List[Dict]:
    """pa11y JSON array → list of Finding-shaped dicts."""
    if not raw:
        return []
    out: List[Dict] = []
    for issue in raw:
        code = issue.get("code", "") or "unknown"
        message = issue.get("message", "") or ""
        selector = issue.get("selector", "") or ""
        out.append({
            "category":    "a11y",
            "severity":    _severity(issue),
            "user_impact": 3,
            "fix_effort":  2,
            "file_path":   url,
            "line_number": 0,
            "match":       code,
            "rationale":   f"{message} (selector: {selector})".strip(),
            "suggested_replacement": "",
        })
    return sorted(out, key=lambda f: f["match"])


# ---------------------------------------------------------------------------
# Thin shell-out (NOT unit-tested).
# ---------------------------------------------------------------------------

def shell_out(url: str, timeout: int = 60) -> Optional[list]:
    try:
        proc = subprocess.run(
            ["npx", "--yes", "pa11y", url,
             "--runner", "axe", "--reporter", "json"],
            capture_output=True, text=True, timeout=timeout,
            env=dict(os.environ),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    # pa11y exits non-zero when issues are found — that is normal.
    if not proc.stdout:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def run(url: str, timeout: int = 60) -> List[Dict]:
    raw = shell_out(url, timeout=timeout)
    if raw is None:
        return []
    return normalise(raw, url=url)
