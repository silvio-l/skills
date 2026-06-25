#!/usr/bin/env python3
"""Reddit ``.json`` collector (slice 02).

Reddit's official ``.json`` endpoint (~60/min, no Playwright) yields
qualitative signals + competitor names. We search a few targeted queries
derived from the seed and the app name, then pull thread titles + the
leading comment text as qualitative material for the report.

Never-blocking: any fetch failure returns ``[]`` and the caller marks the
source "unavailable". Politeness: realistic UA, <= 1 req/s + jitter, the
shared HTTP cache, exponential backoff on 429/503 (max 3, then skip).
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

import cache as CACHE
import politeness as POLITE

SEARCH_URL = "https://www.reddit.com/search.json"
DEFAULT_LIMIT = 25  # threads per query
MAX_QUERIES = 5  # deckel

_RATE = POLITE.RateLimiter(seed=7)


def fetch_search(
    query: str,
    *,
    limit: int = DEFAULT_LIMIT,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = CACHE.HTTP_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
    rate_limiter: Optional[POLITE.RateLimiter] = None,
) -> Dict:
    """One Reddit search.json call, cache-backed. Never raises."""
    params = {"q": query, "limit": str(limit), "sort": "relevance", "t": "year"}
    key = CACHE.cache_key("GET", SEARCH_URL, params)
    path = CACHE.cache_path(cache_dir, key)
    now_ts = time.time() if now is None else now

    if not fresh and CACHE.is_fresh(path, ttl, now_ts):
        cached = CACHE.read_cache(path)
        if cached is not None:
            return json.loads(cached.decode("utf-8"))

    url = SEARCH_URL + "?" + urllib.parse.urlencode(params)
    if not POLITE.robots_allows(url):
        return {"data": {"children": []}}

    rl = rate_limiter or _RATE
    headers = POLITE.browser_headers()
    payload = None
    for attempt in range(POLITE.MAX_RETRIES):
        try:
            rl.wait(url)
            req = urllib.request.Request(url, headers=headers)
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
                return {"data": {"children": []}}
            time.sleep(POLITE.backoff_delay(attempt, rng=rl._rng))

    if payload is None:
        return {"data": {"children": []}}
    CACHE.write_cache(path, payload, now=now_ts)
    return json.loads(payload.decode("utf-8"))


def parse_threads(raw: Dict) -> List[Dict]:
    """Pull lightweight qualitative records from a Reddit search payload."""
    out: List[Dict] = []
    children = (raw.get("data") or {}).get("children") or []
    for ch in children:
        d = ch.get("data") or {}
        out.append(
            {
                "title": d.get("title") or "",
                "subreddit": d.get("subreddit") or "",
                "score": d.get("score") or 0,
                "url": d.get("url") or "",
                "selftext": (d.get("selftext") or "")[:500],
            }
        )
    return out


def collect(
    queries: List[str],
    *,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., Dict]] = None,
    max_queries: int = MAX_QUERIES,
) -> List[Dict]:
    """Run up to ``max_queries`` Reddit searches, merge + de-dupe threads."""
    do_fetch = fetch_fn or fetch_search
    seen: set = set()
    merged: List[Dict] = []
    for q in queries[:max_queries]:
        try:
            raw = do_fetch(q, cache_dir=cache_dir, fresh=fresh)
        except Exception:
            continue
        for t in parse_threads(raw):
            key = (t.get("subreddit"), t.get("title"))
            if key in seen:
                continue
            seen.add(key)
            merged.append(t)
    return merged
