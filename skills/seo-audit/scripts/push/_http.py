#!/usr/bin/env python3
"""Real HTTP client used by the push adapters.

Pure stdlib (urllib.request) — no third-party deps. Not unit-tested:
the adapters are tested with injected fake clients, and this client
is exercised only by the live-smoke procedure documented in
`skills/seo-audit/push.md` §Live-Smoke.

Signature contract (shared by all adapters):
    client(method, url, headers, body) -> (status, text)

* `method`  — "POST" / "GET" / etc.
* `url`     — full URL including query string.
* `headers` — dict[str, str].
* `body`    — str (already serialised); pass "" for GET.

Returns a tuple `(status: int, text: str)`. Network errors are caught
and surfaced as `(0, "<error>")` so the caller can render them without
crashing the audit.
"""

from __future__ import annotations

import urllib.error
import urllib.request
from typing import Dict, Tuple


def real_client(
    method: str,
    url: str,
    headers: Dict[str, str],
    body: str,
    timeout: int = 30,
) -> Tuple[int, str]:  # pragma: no cover — exercised live only
    data = body.encode("utf-8") if body else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8", errors="replace")
            return (resp.status, text)
    except urllib.error.HTTPError as exc:
        try:
            text = exc.read().decode("utf-8", errors="replace")
        except Exception:
            text = str(exc)
        return (exc.code, text)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return (0, f"network error: {exc}")
