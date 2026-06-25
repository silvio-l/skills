#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.40"]
# ///
"""Apple product-page browser collector (Playwright) — slice 02.

Scrapes the two things the iTunes API genuinely does not return:

* the Apple **subtitle** (the 30-char line under the title), and
* the **similar-apps** graph ("You might also like", 1 hop) — the
  niche-competitor gold channel.

Runs under the shared politeness rule-set (:mod:`politeness`): realistic
UA + locale ``de-DE``, <= 1 req/s/domain + jitter, a 12h browser cache,
exponential backoff on 429/503 (max 3, then skip), robots.txt respected.
**No stealth plugins** (no playwright-stealth/Camoufox/fingerprint
spoof/proxy) — moderation over extraction. Playwright Chromium is already
installed at ``~/Library/Caches/ms-playwright``.

Playwright is imported lazily so this module is import-safe in plain
``python3`` (the offline tests never touch it). ``fetch_fn`` is injectable
so the pipeline can substitute a recorded scrape (fixture) without a
browser.

Never-blocking: a scrape failure returns empty results and the caller
marks the source "unavailable".
"""

from __future__ import annotations

import json
import re
from typing import Callable, Dict, List, Optional

import cache as CACHE
import politeness as POLITE

BROWSER_TTL = CACHE.BROWSER_TTL
# Tolerant subtitle selectors (Apple markup shifts; try several, take first).
_SUBTITLE_SELECTORS = (
    "h2.product-header__subtitle",
    "header.product-app__app__subtitle",
    "h2.app-header__subtitle",
    "[data-test-id='app-subtitle']",
)
_APP_ID_RE = re.compile(r"/app/(?:[^/]+/)?id(\d+)")


def _product_url(app_id: str, country: str) -> str:
    return f"https://apps.apple.com/{country}/app/id{app_id}"


def _scrape_page(page, app_id: str) -> Dict:
    """Run the extraction JS inside an already-navigated Playwright page."""
    # subtitle: try the known selectors, fall back to nothing.
    subtitle = ""
    for sel in _SUBTITLE_SELECTORS:
        try:
            el = page.query_selector(sel)
        except Exception:
            el = None
        if el is not None:
            subtitle = (el.inner_text() or "").strip()
            if subtitle:
                break

    # similar-apps: every anchor whose href carries an /app/.../id<digits>.
    similar: List[str] = []
    try:
        links = page.eval_on_selector_all(
            "a[href*='/app/']",
            "els => els.map(e => e.getAttribute('href'))",
        )
    except Exception:
        links = []
    seen = set()
    for href in links or []:
        m = _APP_ID_RE.search(href or "")
        if not m:
            continue
        cid = m.group(1)
        if cid == str(app_id) or cid in seen:
            continue
        seen.add(cid)
        similar.append(cid)
    return {"subtitle": subtitle, "similar_app_ids": similar[:15]}


def fetch_apple_app(
    app_id: str,
    *,
    country: str = "de",
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = BROWSER_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
) -> Dict:
    """Scrape one Apple product page for subtitle + similar-app ids.

    Cache-backed (browser TTL 12h). Never raises — returns
    ``{"subtitle": "", "similar_app_ids": []}`` on any failure.
    """
    import time as _time

    url = _product_url(app_id, country)
    key = CACHE.cache_key("BROWSER", url, {})
    path = CACHE.cache_path(cache_dir, key)
    now_ts = _time.time() if now is None else now

    if not fresh and CACHE.is_fresh(path, ttl, now_ts):
        cached = CACHE.read_cache(path)
        if cached is not None:
            try:
                return json.loads(cached.decode("utf-8"))
            except Exception:
                pass

    if not POLITE.robots_allows(url):
        return {"subtitle": "", "similar_app_ids": []}

    empty = {"subtitle": "", "similar_app_ids": []}
    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        # Playwright unavailable -> never block; caller marks source unavailable.
        return empty

    result = empty
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                locale=POLITE.LOCALE,
                user_agent=POLITE.USER_AGENT,
                extra_http_headers={"Accept-Language": POLITE.ACCEPT_LANGUAGE},
            )
            page = context.new_page()
            # politeness: <= 1 req/s + jitter before the live navigation
            POLITE.RateLimiter().wait(url)
            for attempt in range(POLITE.MAX_RETRIES):
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    status = getattr(resp, "status", 200) if resp else 200
                    if status in POLITE.RETRY_STATUS:
                        page.wait_for_timeout(int(POLITE.backoff_delay(attempt, rng=__import__("random").Random())) * 1000)
                        continue
                    break
                except Exception:
                    if attempt == POLITE.MAX_RETRIES - 1:
                        browser.close()
                        return empty
            try:
                page.wait_for_load_state("networkidle", timeout=15000)
            except Exception:
                pass
            result = _scrape_page(page, app_id)
            browser.close()
    except Exception:
        return empty

    try:
        CACHE.write_cache(path, json.dumps(result).encode("utf-8"), now=now_ts)
    except Exception:
        pass
    return result


def collect_subtitle(
    app_id: str,
    *,
    country: str = "de",
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., Dict]] = None,
) -> str:
    """Return the Apple subtitle for ``app_id`` (cache-backed, never-blocking)."""
    do_fetch = fetch_fn or fetch_apple_app
    try:
        return do_fetch(app_id, country=country, cache_dir=cache_dir, fresh=fresh).get("subtitle", "")
    except Exception:
        return ""


def collect_similar(
    app_id: str,
    *,
    country: str = "de",
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., Dict]] = None,
) -> List[str]:
    """Return the similar-app ids for ``app_id`` (1 hop, never-blocking)."""
    do_fetch = fetch_fn or fetch_apple_app
    try:
        return list(do_fetch(app_id, country=country, cache_dir=cache_dir, fresh=fresh).get("similar_app_ids", []))
    except Exception:
        return []
