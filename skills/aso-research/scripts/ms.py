#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["playwright>=1.40"]
# ///
"""Microsoft Store best-effort collector (Playwright, SPA-aware) — slice 05.

``apps.microsoft.com`` is a single-page app: a plain ``page.goto`` returns a
shell with no app data. This collector therefore drives Playwright with
``networkidle`` **plus** ``wait_for_selector`` (not a simple load) — the PRD
feasibility probe confirms this is required.

It collects **MS Core metadata + the ``description`` slot only** (PRD "MS
slots: description only"). There is no MS ASO slot model and no MS keyword
scoring — MS is a **qualitative-only** source that feeds S1 (Niche &
Positioning Analyst) as additional context. The structural isolation lives in
:func:`collect.collect_ms` / :func:`schema.map_ms_to_core`; this module only
extracts raw page data.

Runs under the **shared politeness rule-set** (:mod:`politeness`): realistic
UA + locale ``de-DE``, <= 1 req/s/domain + jitter, a 12h browser cache,
exponential backoff on 429/503 (max 3, then skip), robots.txt respected.
**No stealth plugins** (no playwright-stealth/Camoufox/fingerprint
spoof/proxy) — moderation over extraction. Playwright Chromium is already
installed at ``~/Library/Caches/ms-playwright``.

Playwright is imported lazily so this module is import-safe in plain
``python3`` (the offline tests never touch it). ``fetch_fn`` is injectable so
:func:`collect.collect_ms` can substitute a recorded scrape (fixture) without a
browser.

Never-blocking: a scrape failure returns an empty list and the caller marks
the source ``"unavailable"``.
"""

from __future__ import annotations

import json
import re
import urllib.parse
from typing import Callable, Dict, List, Optional

import cache as CACHE
import politeness as POLITE
from apple_browser import _ensure_chromium, _chromium_log

BROWSER_TTL = CACHE.BROWSER_TTL
# The SPA renders app cards once these anchors/titles exist. Tolerant: try
# several, take the first that matches (MS markup shifts over time).
_RESULT_READY_SELECTORS = (
    "[data-testid='searchPage']",
    "div[role='list']",
    "section[aria-label='Search results']",
    "a[href*='/detail/']",
)
# A detail-page description selector (used when a card carries it).
_DESC_SELECTORS = (
    "[data-testid='description']",
    "[id='description']",
    ".description",
)
# MS Store detail URLs look like /detail/<productId> or /store/detail/<productId>.
_DETAIL_ID_RE = re.compile(r"/detail/(?:xpfpz?tt|9[a-z0-9]+)/?([A-Za-z0-9]{6,})")
_DETAIL_HREF_RE = re.compile(r"/detail/[A-Za-z0-9]+")
_APP_CAP = 15  # deckel-limited best-effort; MS is the lowest-priority store


def _search_url(query: str, *, country: str, language: str) -> str:
    q = urllib.parse.quote(query)
    hl = "de-DE" if (language or "de").lower().startswith("de") else language or "en-US"
    gl = country or "de"
    return f"https://apps.microsoft.com/search?query={q}&hl={hl}&gl={gl}"


def _extract_id(href: str) -> str:
    """Best-effort product id from an MS detail href (last path segment)."""
    m = _DETAIL_ID_RE.search(href or "")
    if m:
        return m.group(1)
    if "/detail/" in (href or ""):
        tail = href.rstrip("/").rsplit("/", 1)[-1]
        if tail and "?" not in tail:
            return tail
    return ""


def _scrape_search(page, query: str) -> List[Dict]:
    """Run the extraction JS inside an already-rendered Playwright search page.

    Returns raw MS app dicts (id/title/description/...) for the result cards.
    The MS SPA does not expose a tidy per-field DOM, so we harvest the detail
    anchors + their card's text; everything degrades safely — a card without a
    resolvable id is dropped, a missing field becomes empty.
    """
    cards: List[Dict] = []
    seen = set()
    try:
        hrefs = page.eval_on_selector_all(
            "a[href*='/detail/']",
            "els => els.map(e => ({href: e.getAttribute('href'), text: (e.innerText||'').trim()}))",
        )
    except Exception:
        hrefs = []

    for entry in hrefs or []:
        href = entry.get("href") if isinstance(entry, dict) else ""
        app_id = _extract_id(href or "")
        if not app_id or app_id in seen:
            continue
        seen.add(app_id)
        text = (entry.get("text") or "") if isinstance(entry, dict) else ""
        # the anchor text is usually the app title (sometimes title + a line).
        title = text.split("\n", 1)[0].strip() if text else ""
        cards.append({
            "id": app_id,
            "title": title,
            "description": "",  # filled from a card-level scrape if available
            "store_url": f"https://apps.microsoft.com/detail/{app_id}",
        })
        if len(cards) >= _APP_CAP:
            break

    # Best-effort description: harvest the card container text around each
    # anchor for a richer description slot. Tolerant — absent is fine.
    for card in cards:
        try:
            loc = page.query_selector(f"a[href*='/detail/{card['id']}']")
            if loc is not None:
                parent = loc.evaluate_handle("e => e.closest('div, section, article') || e.parentElement")
                if parent is not None:
                    block = parent.evaluate("e => (e.innerText||'').trim()")
                    if block:
                        # drop the title line, keep the rest as the description
                        parts = [p.strip() for p in block.split("\n") if p.strip()]
                        if parts and parts[0] == card.get("title"):
                            parts = parts[1:]
                        card["description"] = " ".join(parts)
        except Exception:
            continue
    return cards


def fetch_ms_search(
    query: str,
    *,
    country: str = "de",
    language: str = "de",
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = BROWSER_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
) -> List[Dict]:
    """Scrape one MS Store search for app cards (SPA-aware, cache-backed).

    Uses ``networkidle`` **+** ``wait_for_selector`` because apps.microsoft.com
    is a single-page app. Never raises — returns ``[]`` on any failure. The
    caller marks the source ``"unavailable"`` when nothing was collected.
    """
    import time as _time
    import random

    url = _search_url(query, country=country, language=language)
    key = CACHE.cache_key("BROWSER", url, {})
    path = CACHE.cache_path(cache_dir, key)
    now_ts = _time.time() if now is None else now

    if not fresh and CACHE.is_fresh(path, ttl, now_ts):
        cached = CACHE.read_cache(path)
        if cached is not None:
            try:
                return list(json.loads(cached.decode("utf-8")))
            except Exception:
                pass

    if not POLITE.robots_allows(url):
        return []

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        # Playwright unavailable -> never block; caller marks source unavailable.
        return []

    ok, reason = _ensure_chromium()
    if not ok:
        _chromium_log(f"browser blocked: {reason}")
        return []

    rng = random.Random()
    result: List[Dict] = []
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
            resp = None
            for attempt in range(POLITE.MAX_RETRIES):
                try:
                    resp = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    status = getattr(resp, "status", 200) if resp else 200
                    if status in POLITE.RETRY_STATUS:
                        page.wait_for_timeout(int(POLITE.backoff_delay(attempt, rng=rng) * 1000))
                        continue
                    break
                except Exception:
                    if attempt == POLITE.MAX_RETRIES - 1:
                        browser.close()
                        return []
            # SPA-aware: wait for the network to settle AND a results selector.
            try:
                page.wait_for_load_state("networkidle", timeout=20000)
            except Exception:
                pass
            ready = False
            for sel in _RESULT_READY_SELECTORS:
                try:
                    page.wait_for_selector(sel, timeout=12000)
                    ready = True
                    break
                except Exception:
                    continue
            if ready:
                result = _scrape_search(page, query)
            browser.close()
    except Exception:
        return []

    try:
        CACHE.write_cache(path, json.dumps(result).encode("utf-8"), now=now_ts)
    except Exception:
        pass
    return result


def search(
    query: str,
    *,
    country: str = "de",
    language: str = "de",
    cache_dir: str = "",
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., List[Dict]]] = None,
) -> List[Dict]:
    """Return the raw MS app cards for a ``query`` (SPA-aware, never-blocking).

    The injected ``fetch_fn`` (default :func:`fetch_ms_search`) lets the
    orchestration run offline with a recorded fixture.
    """
    do_fetch = fetch_fn or fetch_ms_search
    try:
        return list(do_fetch(
            query, country=country, language=language,
            cache_dir=cache_dir, fresh=fresh,
        ))
    except Exception:
        return []


if __name__ == "__main__":  # pragma: no cover — manual live-smoke entry
    import sys
    term = sys.argv[1] if len(sys.argv) > 1 else "habit tracker"
    print(json.dumps(search(term), indent=2, ensure_ascii=False))
