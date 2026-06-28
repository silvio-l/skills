#!/usr/bin/env python3
"""Politeness rule-set shared by every Playwright/HTTP collector (slice 02).

Establishes the single, repo-wide rule-set the PRD mandates:

* realistic UA + locale ``de-DE``;
* <= 1 request/sec/domain + random jitter 0.5-2s;
* HTTP/browser response cache (TTLs live in :mod:`cache`);
* exponential backoff on 429/503 (max 3 retries, then skip);
* ``robots.txt`` respected;
* retry-budget then **never-blocking** (a failing source is marked
  "unavailable" upstream and the pipeline continues).

NO stealth plugins, NO fingerprint spoof, NO proxy rotation (PRD
"Bot-detection & rate-limit policy"). Moderation over extraction.
"""

from __future__ import annotations

import random
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, Optional

# Realistic desktop Chromium UA (de-DE). Not spoofed — a normal browser
# string so Apple serves the de-DE listing we research.
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0.0.0 Safari/537.36"
)
LOCALE = "de-DE"
ACCEPT_LANGUAGE = "de-DE,de;q=0.9,en;q=0.5"

# <= 1 req/s/domain + 0.5-2s jitter.
MIN_INTERVAL = 1.0
JITTER_MIN = 0.5
JITTER_MAX = 2.0

# Exponential backoff on 429/503: max 3 attempts, then skip (never block).
MAX_RETRIES = 3
BACKOFF_BASE = 2.0  # seconds; delay = BACKOFF_BASE * 2**attempt + jitter

RETRY_STATUS = {429, 503}


def browser_headers() -> Dict[str, str]:
    """Headers every browser-style request carries (UA + locale)."""
    return {
        "User-Agent": USER_AGENT,
        "Accept-Language": ACCEPT_LANGUAGE,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    }


def jittered_sleep(
    *,
    rng: random.Random,
    sleep: Callable[[float], None] = time.sleep,
) -> None:
    """Sleep MIN_INTERVAL + a random jitter (0.5-2s). Injectable for tests."""
    delay = MIN_INTERVAL + rng.uniform(JITTER_MIN, JITTER_MAX)
    sleep(delay)


def backoff_delay(attempt: int, *, rng: random.Random) -> float:
    """Exponential backoff seconds for the given (0-based) attempt + jitter."""
    base = BACKOFF_BASE * (2 ** attempt)
    return base + rng.uniform(0.0, JITTER_MAX)


class RateLimiter:
    """Per-domain <= 1 req/s + jitter, injected ``now``/``sleep`` for tests."""

    def __init__(
        self,
        *,
        now: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        seed: Optional[int] = None,
    ):
        self._now = now
        self._sleep = sleep
        self._rng = random.Random(seed)
        self._last: Dict[str, float] = {}

    def wait(self, url: str) -> None:
        """Block until at least MIN_INTERVAL (+ jitter) since the last call."""
        host = urllib.parse.urlparse(url).netloc
        ts = self._now()
        elapsed = ts - self._last.get(host, 0.0)
        delay = MIN_INTERVAL - elapsed
        if delay > 0:
            self._sleep(delay)
        jittered_sleep(rng=self._rng, sleep=self._sleep)
        self._last[host] = self._now()


# ---------------------------------------------------------------------------
# robots.txt (best-effort, never blocks)
# ---------------------------------------------------------------------------

_ROBOTS_CACHE: Dict[str, "object"] = {}


def _robots_txt_url(url: str) -> str:
    parts = urllib.parse.urlparse(url)
    return f"{parts.scheme}://{parts.netloc}/robots.txt"


def robots_allows(
    url: str,
    *,
    user_agent: str = "*",
    fetch=None,
) -> bool:
    """Best-effort robots.txt check. Failures default to ALLOW + never block.

    A fetch function ``(robots_url) -> (status, text)`` is injectable; the
    default fetches once per host and caches the parsed rules. Network or
    parse errors degrade to "allowed" (we never block on robots failure).
    """
    try:
        from urllib.robotparser import RobotFileParser  # stdlib
    except Exception:  # pragma: no cover - stdlib always present
        return True

    host = urllib.parse.urlparse(url).netloc
    if host not in _ROBOTS_CACHE:
        rp = RobotFileParser()
        try:
            if fetch is None:
                robots_url = _robots_txt_url(url)
                req = urllib.request.Request(robots_url, headers={"User-Agent": USER_AGENT})
                with urllib.request.urlopen(req, timeout=15) as resp:
                    rp.parse(resp.read().decode("utf-8", "replace").splitlines())
            else:
                _status, text = fetch(_robots_txt_url(url))
                rp.parse((text or "").splitlines())
        except Exception:
            rp = None  # tolerate failure -> allow
        _ROBOTS_CACHE[host] = rp
    rp = _ROBOTS_CACHE[host]
    if rp is None:
        return True
    try:
        return rp.can_fetch(user_agent, url)
    except Exception:
        return True
