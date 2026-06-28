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

import plistlib
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

import cache as CACHE
import politeness as POLITE

# The real App Store autocomplete endpoint is MZSearchHints: it returns a
# **plist (XML)** ``hints`` array of what users actually type. The previous
# MZStore search URL returned an HTML interstitial (→ 0 terms every run).
SUGGEST_URL = "https://search.itunes.apple.com/WebObjects/MZSearchHints.woa/wa/hints"

# The ``X-Apple-Store-Front`` header is REQUIRED — without the country's
# Software storefront id the endpoint returns an empty hint list. Map the
# common App Store countries; unknown → no header (graceful empty result).
_STOREFRONTS: Dict[str, str] = {
    "us": "143441", "de": "143443", "gb": "143444", "uk": "143444",
    "fr": "143442", "it": "143450", "es": "143454", "at": "143445",
    "ch": "143459", "nl": "143452", "ca": "143455", "au": "143460",
    "br": "143503", "jp": "143462", "mx": "143468", "se": "143456",
    "no": "143457", "dk": "143458", "fi": "143447", "pl": "143478",
    "pt": "143453", "ie": "143449", "be": "143446", "ru": "143469",
    "in": "143467", "tr": "143480", "cz": "143489",
}

_RATE = POLITE.RateLimiter(seed=11)


def _storefront(country: str) -> Optional[str]:
    """Resolve the Software storefront id for a country code (None if unknown)."""
    sid = _STOREFRONTS.get((country or "").lower())
    return f"{sid}-1,29" if sid else None


def fetch_suggest(
    term: str,
    *,
    country: str = "de",
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = CACHE.HTTP_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
    rate_limiter: Optional[POLITE.RateLimiter] = None,
) -> List[str]:
    """One Apple autocomplete (MZSearchHints) call, cache-backed.

    Never raises — returns ``[]`` on any failure. The country is part of the
    cache key so DE and US hints cache separately.
    """
    params = {"clientApplication": "Software", "term": term}
    key = CACHE.cache_key("GET", SUGGEST_URL, {**params, "country": country})
    path = CACHE.cache_path(cache_dir, key)
    now_ts = time.time() if now is None else now

    if not fresh and CACHE.is_fresh(path, ttl, now_ts):
        cached = CACHE.read_cache(path)
        if cached is not None:
            return _parse_bytes(cached)

    url = SUGGEST_URL + "?" + urllib.parse.urlencode(params)
    # MZSearchHints is the App Store client's own autocomplete API — the same
    # "official Apple API" class as iTunes Search/Lookup (:mod:`itunes`, which
    # likewise does not gate on robots.txt). pipeline.md classifies these APIs
    # as the default channel; the robots gate stays on the genuine web-page
    # scrapers (apps.apple.com / MS), which are robots-ALLOW anyway. Politeness
    # (rate-limit + backoff + cache) is still fully enforced below.
    headers = POLITE.browser_headers()
    storefront = _storefront(country)
    if storefront:
        headers["X-Apple-Store-Front"] = storefront

    rl = rate_limiter or _RATE
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
                return []
            time.sleep(POLITE.backoff_delay(attempt, rng=rl._rng))

    if payload is None:
        return []
    CACHE.write_cache(path, payload, now=now_ts)
    return _parse_bytes(payload)


def _parse_bytes(raw: bytes) -> List[str]:
    """Extract suggestion strings from a MZSearchHints plist payload.

    Tolerant: parses the plist ``hints`` array; never raises ([] on any
    malformed/empty payload, e.g. an HTML interstitial).
    """
    try:
        parsed = plistlib.loads(raw)
    except Exception:
        return []
    hints = parsed.get("hints") if isinstance(parsed, dict) else None
    if not isinstance(hints, list):
        return []
    out: List[str] = []
    for h in hints:
        term = h.get("term") if isinstance(h, dict) else h
        term = (str(term) if term else "").strip()
        if term:
            out.append(term)
    return out


def collect(
    seed_terms: List[str],
    *,
    country: str = "de",
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., List[str]]] = None,
) -> List[str]:
    """Probe autocomplete for each seed term; merge + de-dupe suggestions.

    Never-blocking: any per-term failure is skipped (a single bad term never
    aborts the rest).
    """
    do_fetch = fetch_fn or fetch_suggest
    seen: set = set()
    out: List[str] = []
    for term in seed_terms:
        try:
            suggestions = do_fetch(term, country=country, cache_dir=cache_dir, fresh=fresh)
        except Exception:
            continue
        for s in suggestions:
            s = (s or "").strip()
            if s and s.lower() not in seen:
                seen.add(s.lower())
                out.append(s)
    return out
