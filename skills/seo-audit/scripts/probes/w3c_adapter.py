#!/usr/bin/env python3
"""W3C Nu validator adapter — normaliser + thin shell-out.

Shell-out: `curl -sS -X POST -H 'Content-Type: text/html; charset=utf-8'
            --data-binary @<html> 'https://validator.w3.org/nu/?out=json'`
The shell-out is not unit-tested; the live whispaste.de smoke command
exercises it.
"""

from __future__ import annotations

import json
import subprocess
from typing import Dict, List, Optional


def _severity(msg: Dict) -> str:
    t = msg.get("type")
    if t == "error":
        return "high"
    sub = msg.get("subType")
    if t == "info" and sub == "warning":
        return "med"
    return "low"


def _match(msg: Dict) -> str:
    text = msg.get("message", "") or ""
    # Concise rule-ish identifier — first 60 chars, stripped.
    snippet = text.strip().split("\n", 1)[0]
    return snippet[:60].rstrip()


def normalise(raw, url: str) -> List[Dict]:
    if not raw:
        return []
    messages = raw.get("messages") if isinstance(raw, dict) else None
    if not messages:
        return []
    out: List[Dict] = []
    for msg in messages:
        out.append({
            "category":    "html",
            "severity":    _severity(msg),
            "user_impact": 2,
            "fix_effort":  1,
            "file_path":   url,
            "line_number": int(msg.get("lastLine") or 0),
            "match":       _match(msg),
            "rationale":   (msg.get("message", "") or "").strip(),
            "suggested_replacement": (msg.get("extract", "") or "").strip(),
        })
    return out


# ---------------------------------------------------------------------------
# Thin shell-out (NOT unit-tested).
# ---------------------------------------------------------------------------

def shell_out(url: str, timeout: int = 30) -> Optional[Dict]:
    """Fetch HTML then POST it to the W3C Nu validator API."""
    try:
        fetch = subprocess.run(
            ["curl", "-sSL", "--max-time", str(timeout), url],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        if fetch.returncode != 0 or not fetch.stdout:
            return None
        proc = subprocess.run(
            ["curl", "-sS", "-X", "POST",
             "--max-time", str(timeout),
             "-H", "Content-Type: text/html; charset=utf-8",
             "--data-binary", "@-",
             "https://validator.w3.org/nu/?out=json"],
            input=fetch.stdout, capture_output=True, text=True,
            timeout=timeout + 5,
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
