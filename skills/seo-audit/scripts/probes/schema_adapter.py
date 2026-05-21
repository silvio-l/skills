#!/usr/bin/env python3
"""Schema.org validator adapter — normaliser + thin shell-out.

Shell-out: `curl` against `validator.schema.org`. Since the public API
contract for validator.schema.org is unstable, the live smoke command
documents the current invocation; the normaliser only depends on the
trimmed shape we control via the fixture.
"""

from __future__ import annotations

import json
import subprocess
from typing import Dict, List, Optional


SEVERITY_MAP = {
    "error":   "high",
    "warning": "med",
    "info":    "low",
}


def _type_name(node) -> str:
    if isinstance(node, dict):
        return node.get("typeName") or ""
    return ""


def normalise(raw, url: str) -> List[Dict]:
    if not raw or not isinstance(raw, dict):
        return []
    groups = raw.get("tripleGroups") or []
    out: List[Dict] = []
    for group in groups:
        nodes = group.get("nodes") or []
        type_name = _type_name(nodes[0]) if nodes else "Unknown"
        for err in group.get("errors") or []:
            sev = SEVERITY_MAP.get(
                str(err.get("severity", "")).lower(), "med"
            )
            description = (err.get("description") or "").strip()
            match = f"{type_name}: {description}"[:60]
            out.append({
                "category":    "schema",
                "severity":    sev,
                "user_impact": 2,
                "fix_effort":  1,
                "file_path":   url,
                "line_number": 0,
                "match":       match,
                "rationale":   f"{type_name} — {description}",
                "suggested_replacement": err.get("path", "") or "",
            })
    return out


# ---------------------------------------------------------------------------
# Thin shell-out (NOT unit-tested).
# ---------------------------------------------------------------------------

def shell_out(url: str, timeout: int = 30) -> Optional[Dict]:
    try:
        proc = subprocess.run(
            ["curl", "-sSL", "--max-time", str(timeout),
             "-G", "https://validator.schema.org/validate",
             "--data-urlencode", f"url={url}"],
            capture_output=True, text=True, timeout=timeout + 5,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def run(url: str, timeout: int = 30) -> List[Dict]:
    raw = shell_out(url, timeout=timeout)
    if raw is None:
        return []
    return normalise(raw, url=url)
