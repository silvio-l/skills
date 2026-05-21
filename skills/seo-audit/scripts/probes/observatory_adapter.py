#!/usr/bin/env python3
"""Mozilla HTTP Observatory adapter — normaliser + thin shell-out.

Shell-out: POST to start the scan, then GET the results — both at
`https://http-observatory.security.mozilla.org/api/v1/`. The shell-out
is not unit-tested.
"""

from __future__ import annotations

import json
import subprocess
import time
from typing import Dict, List, Optional


def _severity_for_modifier(mod) -> str:
    try:
        magnitude = abs(int(mod))
    except (TypeError, ValueError):
        magnitude = 0
    if magnitude >= 20:
        return "high"
    if magnitude >= 5:
        return "med"
    return "low"


def _grade_severity(grade: str) -> Optional[str]:
    if not grade:
        return None
    letter = grade[0].upper()
    if letter in ("A",):
        return None
    if letter == "B":
        return "low"
    if letter == "C":
        return "med"
    return "high"  # D, E, F


def normalise(raw, url: str) -> List[Dict]:
    if not raw or not isinstance(raw, dict):
        return []
    out: List[Dict] = []

    tests = raw.get("tests") or {}
    for name in sorted(tests):
        spec = tests[name] or {}
        if spec.get("pass"):
            continue
        out.append({
            "category":    "security",
            "severity":    _severity_for_modifier(spec.get("score_modifier")),
            "user_impact": 2,
            "fix_effort":  1,
            "file_path":   url,
            "line_number": 0,
            "match":       name,
            "rationale":   spec.get("score_description", "") or name,
            "suggested_replacement": "",
        })

    grade_sev = _grade_severity(raw.get("grade", "") or "")
    if grade_sev is not None:
        out.append({
            "category":    "security",
            "severity":    grade_sev,
            "user_impact": 2,
            "fix_effort":  2,
            "file_path":   url,
            "line_number": 0,
            "match":       "observatory:grade",
            "rationale":   (
                f"Mozilla Observatory grade: {raw.get('grade')} "
                f"(score {raw.get('score')})"
            ),
            "suggested_replacement": "",
        })
    return out


# ---------------------------------------------------------------------------
# Thin shell-out (NOT unit-tested).
# ---------------------------------------------------------------------------

API = "https://http-observatory.security.mozilla.org/api/v1"


def _host_from_url(url: str) -> str:
    rest = url.split("://", 1)[-1]
    return rest.split("/", 1)[0]


def shell_out(url: str, timeout: int = 60) -> Optional[Dict]:
    host = _host_from_url(url)
    try:
        # Start (or fetch cached) scan.
        start = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout),
             "-X", "POST", f"{API}/analyze?host={host}"],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        if start.returncode != 0 or not start.stdout:
            return None
        summary = json.loads(start.stdout)
        scan_id = summary.get("scan_id")
        grade = summary.get("grade")
        score = summary.get("score")

        # Poll for completion (Observatory scans usually finish in seconds).
        deadline = time.time() + timeout
        while summary.get("state") not in (None, "FINISHED") and time.time() < deadline:
            time.sleep(2)
            poll = subprocess.run(
                ["curl", "-sS", "--max-time", str(timeout),
                 f"{API}/analyze?host={host}"],
                capture_output=True, text=True, timeout=timeout + 5,
            )
            if poll.returncode != 0:
                break
            summary = json.loads(poll.stdout)
            scan_id = summary.get("scan_id") or scan_id
            grade = summary.get("grade") or grade
            score = summary.get("score") if summary.get("score") is not None else score

        if not scan_id:
            return None
        res = subprocess.run(
            ["curl", "-sS", "--max-time", str(timeout),
             f"{API}/getScanResults?scan={scan_id}"],
            capture_output=True, text=True, timeout=timeout + 5,
        )
        if res.returncode != 0 or not res.stdout:
            return None
        tests = json.loads(res.stdout)
        return {"host": host, "grade": grade, "score": score, "tests": tests}
    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError):
        return None


def run(url: str, timeout: int = 60) -> List[Dict]:
    raw = shell_out(url, timeout=timeout)
    if raw is None:
        return []
    return normalise(raw, url=url)
