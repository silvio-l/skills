#!/usr/bin/env python3
"""Apple Search-Suggest autocomplete collector (slice 02).

The App Store's autocomplete endpoint is the only free *real-search-signal*
channel: it returns what users actually type. We probe it with the seed
keywords (+ the app name) and collect the suggestion terms, which feed
both keyword extraction (enrichment) and the scorer's +15 relevance boost.

Never-blocking: any failure returns ``[]`` and the caller marks the source
"unavailable". Public endpoint, no auth, no Playwright.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

_HTML_SNIFF = b"<html"

import cache as CACHE
import politeness as POLITE

# App Store search-suggest endpoint (returns JSON list of suggestion strings).
SUGGEST_URL = "https://search.itunes.apple.com/WebObjects/MZStore.woa/wa/search"

_RATE = POLITE.RateLimiter(seed=11)


def fetch_suggest(
    term: str,
    *,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = CACHE.HTTP_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
    rate_limiter: Optional[POLITE.RateLimiter] = None,
) -> List[str]:
    """One Apple autocomplete call, cache-backed. Never raises; [] on failure."""
    params = {"term": term, "media": "software", "limit": "10"}
    key = CACHE.cache_key("GET", SUGGEST_URL, params)
    path = CACHE.cache_path(cache_dir, key)
    now_ts = time.time() if now is None else now

    if not fresh and CACHE.is_fresh(path, ttl, now_ts):
        cached = CACHE.read_cache(path)
        if cached is not None:
            return _parse(json.loads(cached.decode("utf-8")))

    url = SUGGEST_URL + "?" + urllib.parse.urlencode(params)
    if not POLITE.robots_allows(url):
        return []

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
                return []
            time.sleep(POLITE.backoff_delay(attempt, rng=rl._rng))

    if payload is None:
        return []
    CACHE.write_cache(path, payload, now=now_ts)
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except json.JSONDecodeError:
        if payload.lower().startswith(_HTML_SNIFF):
            raise ValueError("non-JSON response: HTML interstitial from Apple Search-Suggest")
        raise
    return _parse(parsed)


def _parse(raw) -> List[str]:
    """Tolerantly extract suggestion strings from a suggest payload.

    The endpoint historically returns either a bare JSON list of strings
    or an object wrapping a list. We handle both and never raise.
    """
    if isinstance(raw, list):
        return [str(s).strip() for s in raw if isinstance(s, str) and s.strip()]
    if isinstance(raw, dict):
        for k in ("suggestions", "terms", "results"):
            v = raw.get(k)
            if isinstance(v, list):
                return [
                    (s if isinstance(s, str) else str(s.get("term") or s.get("title") or "")).strip()
                    for s in v
                    if s
                ]
    return []


def collect(
    seed_terms: List[str],
    *,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., List[str]]] = None,
) -> List[str]:
    """Probe autocomplete for each seed term; merge + de-dupe suggestions.

    Never-blocking: any per-term failure is skipped.
    """
    do_fetch = fetch_fn or fetch_suggest
    seen: set = set()
    out: List[str] = []
    for term in seed_terms:
        try:
            suggestions = do_fetch(term, cache_dir=cache_dir, fresh=fresh)
        except ValueError:
            raise
        except Exception:
            continue
        for s in suggestions:
            s = (s or "").strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
    return out
