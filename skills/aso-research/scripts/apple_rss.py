#!/usr/bin/env python3
"""Apple RSS Marketing-Tools charts collector (slice 02).

The Apple RSS feed (``rss.applemarketingtools.com``) serves the category
top-charts after a 301 redirect. Public, no auth, no Playwright. Used as
a deckel-limited chart source alongside iTunes Search.

Split like :mod:`itunes`:

* :func:`fetch_chart` — live HTTP via urllib + cache + politeness. **Not
  unit-tested** (external; format would rot). Verified by a manual
  live-smoke run.
* :func:`parse_chart` — pure transform from raw RSS JSON -> list of app
  ids (the chart entries). Offline-testable shape (kept intentionally
  tolerant; no assertions on live values in tests).
* :func:`collect` — orchestrator with an injectable ``fetch_fn`` so the
  pipeline can substitute a recorded fixture.

Never-blocking: a fetch failure returns ``[]`` and the caller marks the
source "unavailable".
"""

from __future__ import annotations

import json
import re
import time
import urllib.request
from typing import Callable, Dict, List, Optional

import cache as CACHE
import politeness as POLITE
from schema import PLATFORM

# Apple Marketing Tools RSS. The feed is **path-style**: the limit is a path
# segment and the resource is ``apps.json`` — the legacy ``?limit=&category=``
# query form 404s. This endpoint serves the *overall* top-free chart (no genre
# scoping at this v2 path; the genre-scoped legacy ``/rss/`` feed is robots-
# disallowed), so the caller post-filters chart apps to the seed category to
# keep the keyword corpus on-topic.
DEFAULT_LIMIT = 25  # deckel: keep charts bounded

_RATE = POLITE.RateLimiter(seed=42)

_DIGITS_RE = re.compile(r"\d+")


def _chart_url(category: str, limit: int, country: str) -> str:
    # category is intentionally unused: the v2 marketing-tools feed has no
    # genre path; charts are overall top-free and category-filtered downstream.
    return (
        f"https://rss.marketingtools.apple.com/api/v2/{country}"
        f"/apps/top-free/{int(limit)}/apps.json"
    )


def fetch_chart(
    category: str,
    *,
    country: str = "de",
    limit: int = DEFAULT_LIMIT,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = CACHE.HTTP_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
    rate_limiter: Optional[POLITE.RateLimiter] = None,
) -> Dict:
    """Fetch one Apple RSS category chart, cache-backed. Never raises.

    Returns the parsed RSS JSON, or ``{"feed": {"results": []}}`` on
    failure (caller marks the source unavailable).
    """
    url = _chart_url(category, limit, country)
    key = CACHE.cache_key("GET", url, {})
    path = CACHE.cache_path(cache_dir, key)
    now_ts = time.time() if now is None else now

    if not fresh and CACHE.is_fresh(path, ttl, now_ts):
        cached = CACHE.read_cache(path)
        if cached is not None:
            return json.loads(cached.decode("utf-8"))

    if not POLITE.robots_allows(url):
        return {"feed": {"results": []}}

    rl = rate_limiter or _RATE
    payload = None
    for attempt in range(POLITE.MAX_RETRIES):
        try:
            rl.wait(url)
            req = urllib.request.Request(url, headers=POLITE.browser_headers())
            with urllib.request.urlopen(req, timeout=30) as resp:
                status = getattr(resp, "status", resp.getcode())
                raw = resp.read()
            if status in POLITE.RETRY_STATUS:
                time.sleep(POLITE.backoff_delay(attempt, rng=rl._rng))
                continue
            payload = raw
            break
        except Exception:
            if attempt == POLITE.MAX_RETRIES - 1:
                return {"feed": {"results": []}}
            time.sleep(POLITE.backoff_delay(attempt, rng=rl._rng))

    if payload is None:
        return {"feed": {"results": []}}
    CACHE.write_cache(path, payload, now=now_ts)
    return json.loads(payload.decode("utf-8"))


def parse_chart(raw: Dict) -> List[str]:
    """Extract app ids (top-chart entry ids) from a raw RSS chart payload."""
    if not raw:
        return []
    results = (raw.get("feed") or {}).get("results") or []
    ids = []
    for entry in results:
        # entry id may be a bare numeric string or a URL like
        # .../app/id324684580?mt=8 — extract the leading digit run either way
        # (a trailing query string must not leak into the id).
        eid = str(entry.get("id") or "")
        if "/id" in eid:
            eid = eid.rsplit("/id", 1)[-1]
        m = _DIGITS_RE.match(eid)
        if m:
            ids.append(m.group())
    return ids


def collect(
    category: str,
    *,
    country: str = "de",
    limit: int = DEFAULT_LIMIT,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., Dict]] = None,
) -> List[str]:
    """Collect a category chart's app ids. Never-blocking; [] on failure."""
    do_fetch = fetch_fn or fetch_chart
    try:
        raw = do_fetch(category, country=country, limit=limit, cache_dir=cache_dir, fresh=fresh)
    except Exception:
        return []
    return parse_chart(raw)
