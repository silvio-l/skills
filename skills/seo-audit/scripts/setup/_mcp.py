#!/usr/bin/env python3
"""Thin wrapper around `claude mcp list` for the doctor check.

The real `subprocess.run` is wrapped in `default_runner`. Tests inject
a fake runner so we never shell out during unit tests. If `claude` is
not on PATH the wrapper returns a structured "not found" result rather
than raising — doctor renders that as a missing-tool row, not a crash.
"""

from __future__ import annotations

import subprocess
from typing import Callable, Dict


def default_runner(argv) -> Dict:  # pragma: no cover — exercised live only
    """Run `claude mcp list` and return a dict of {returncode, stdout, stderr}."""
    try:
        proc = subprocess.run(
            argv,
            capture_output=True, text=True, timeout=10,
        )
        return {
            "returncode": proc.returncode,
            "stdout": proc.stdout or "",
            "stderr": proc.stderr or "",
        }
    except FileNotFoundError:
        return {"returncode": 127, "stdout": "", "stderr": "claude: not found"}
    except subprocess.TimeoutExpired:
        return {"returncode": 124, "stdout": "", "stderr": "claude: timeout"}


def list_mcp_servers(runner: Callable = None) -> Dict:
    """Return `{"available": bool, "servers": list[str], "raw": str}`.

    A server name starting with `mcp__gsc__` indicates GSC integration.
    The output format of `claude mcp list` is line-oriented; we tolerate
    both JSON and plain-text outputs by greedy regex against the prefix.
    """
    run = runner or default_runner
    result = run(["claude", "mcp", "list"])
    if result.get("returncode") != 0:
        return {
            "available": False,
            "servers": [],
            "raw": result.get("stderr") or result.get("stdout") or "",
            "reason": "claude CLI unavailable or call failed",
        }
    raw = result.get("stdout") or ""
    # Heuristic: every token that starts with "mcp__" up to a whitespace
    # or punctuation boundary is a server name.
    import re
    servers = sorted(set(re.findall(r"mcp__[A-Za-z0-9_]+", raw)))
    return {
        "available": True,
        "servers": servers,
        "raw": raw,
        "reason": "",
    }


def has_gsc(mcp_result: Dict) -> bool:
    """True if any server in the result is prefixed with mcp__gsc__."""
    return any(s.startswith("mcp__gsc__") for s in mcp_result.get("servers", []))
