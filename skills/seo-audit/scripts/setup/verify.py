#!/usr/bin/env python3
"""Verify mode — one minimal probe call per configured tool.

Quota-aware. IndexNow does NOT submit a URL — it HEADs the public
key-file URL instead, so live verify has zero index-side-effects.

Each probe is injectable: tests pass a `clients` dict; production wires
the real urllib client from `_http.py` (or, for IndexNow, a HEAD probe
against the key file location).
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from . import diagnoses as DIAG
from . import urls as URLS


TOOLS = ("indexnow", "pagespeed", "bing", "gsc")


def _status_label(status: int) -> str:
    if status == 0:
        return "network-error"
    if 200 <= status < 300:
        return "OK"
    if status == 401:
        return "401 unauthorized"
    if status == 403:
        return "403 forbidden"
    if status == 404:
        return "404 not found"
    if status == 429:
        return "429 rate-limited"
    if 500 <= status < 600:
        return f"{status} server error"
    return f"{status} unexpected"


def _result(tool: str, configured: bool, status: int,
            note: str = "") -> Dict:
    return {
        "tool":       tool,
        "configured": configured,
        "status":     status,
        "label":      _status_label(status),
        "diagnose":   DIAG.diagnose(tool, status) if configured else note,
        "note":       note,
    }


def verify_pagespeed(env: Dict, *, client: Optional[Callable] = None) -> Dict:
    """Smallest PageSpeed call: example.com, mobile, no extra categories."""
    key = env.get("PAGESPEED_API_KEY") or ""
    if not key:
        return _result("pagespeed", False, 0,
                       note="PAGESPEED_API_KEY not set — skipping.")
    if client is None:
        return _result("pagespeed", True, 0,
                       note="no HTTP client provided")
    url = (
        f"{URLS.PAGESPEED_API_ENDPOINT}"
        f"?url=https://example.com&key={key}&strategy=mobile"
    )
    status, _body = client("GET", url, {}, "")
    return _result("pagespeed", True, status)


def verify_bing(env: Dict, *, client: Optional[Callable] = None) -> Dict:
    """Smallest Bing call: GetUrlInfo for example.com."""
    key = env.get("BING_WEBMASTER_API_KEY") or ""
    if not key:
        return _result("bing", False, 0,
                       note="BING_WEBMASTER_API_KEY not set — skipping.")
    if client is None:
        return _result("bing", True, 0, note="no HTTP client provided")
    url = (
        f"{URLS.BING_WEBMASTER_API_ENDPOINT}"
        f"?apikey={key}&siteUrl=https%3A%2F%2Fwww.example.com&url="
        "https%3A%2F%2Fwww.example.com%2F"
    )
    status, _body = client("GET", url, {}, "")
    return _result("bing", True, status)


def verify_indexnow(
    env: Dict,
    *,
    public_host: str = "",
    client: Optional[Callable] = None,
) -> Dict:
    """HEAD the public key file URL — never submit a real URL.

    The key file URL is `https://<host>/<key>.txt`. If we don't know
    the host (no --url passed), the verification is "configured: false"
    with a hint, NOT a network error.
    """
    key = env.get("INDEXNOW_KEY") or ""
    if not key:
        return _result("indexnow", False, 0,
                       note="INDEXNOW_KEY not set — skipping.")
    if not public_host:
        return _result("indexnow", False, 0,
                       note="No public host given; pass --url to verify.")
    if client is None:
        return _result("indexnow", True, 0, note="no HTTP client provided")
    url = f"https://{public_host}/{key}.txt"
    status, _body = client("HEAD", url, {}, "")
    return _result("indexnow", True, status)


def verify_gsc(*, mcp_client: Optional[Callable] = None) -> Dict:
    """Smallest GSC call: list properties (read-only).

    `mcp_client` returns `{"status": int, "body": Any}` to match the
    HTTP shape used by the other tools — tests use this contract.
    """
    if mcp_client is None:
        return _result("gsc", False, 0,
                       note="GSC MCP client not wired in.")
    result = mcp_client("mcp__gsc__list_properties")
    status = int(result.get("status", 0))
    out = _result("gsc", True, status)
    return out


def run(
    env: Dict,
    *,
    public_host: str = "",
    clients: Optional[Dict[str, Callable]] = None,
) -> List[Dict]:
    """Run one probe per tool. Returns results in stable order."""
    clients = clients or {}
    out: List[Dict] = []
    out.append(verify_indexnow(
        env, public_host=public_host, client=clients.get("indexnow")))
    out.append(verify_pagespeed(env, client=clients.get("pagespeed")))
    out.append(verify_bing(env, client=clients.get("bing")))
    out.append(verify_gsc(mcp_client=clients.get("gsc")))
    return out


def render(results: List[Dict]) -> str:
    """Render verify results as Markdown."""
    lines = ["# seo-audit verify", ""]
    lines.append("| Tool | Status | Diagnose |")
    lines.append("| ---- | ------ | -------- |")
    for r in results:
        if not r["configured"]:
            lines.append(f"| {r['tool']} | _skipped_ | {r.get('note', '')} |")
            continue
        lines.append(f"| {r['tool']} | {r['label']} · {r['status']} | "
                     f"{r['diagnose']} |")
    return "\n".join(lines) + "\n"
