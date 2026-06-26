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
    "a[href*='/detail/']",
    "[data-testid='searchPage']",
    "div[role='list']",
    "section[aria-label='Search results']",
)
# A detail-page description selector (used when a card carries it).
_DESC_SELECTORS = (
    "[data-testid='description']",
    "[id='description']",
    ".description",
)
# MS Store detail URLs look like /detail/<productId> or /store/detail/<productId>.
# The full product ID (e.g. 9n7wbb04192f) is the complete path segment after /detail/.
_DETAIL_ID_RE = re.compile(r"/(?:store/)?detail/([A-Za-z0-9]{8,})")
_DETAIL_HREF_RE = re.compile(r"/detail/[A-Za-z0-9]+")
_APP_CAP = 15  # deckel-limited best-effort; MS is the lowest-priority store
_DETAIL_CAP = 15  # per-run cap on detail page fetches

# Detail-page selectors — tolerant: try several, take the first that matches.
_DETAIL_DESC_SELECTORS = (
    "[data-testid='description']",
    "[id='description']",
    ".description",
    "section[aria-label*='description' i]",
    "section[aria-label*='Description']",
    "[data-testid='productDescription']",
    "div[class*='description']",
    "div[class*='product-description']",
    "div[id='product-description']",
    "[aria-label*='Übersicht' i]",
    "[aria-label*='overview' i]",
)
_DETAIL_RATING_SELECTORS = (
    "[data-testid='rating']",
    "[aria-label*='rated' i]",
    "[aria-label*='star' i]",
    "div[class*='rating'] [class*='number']",
    "[data-testid='ratingValue']",
    ".c-rating",
    "span[class*='rating-value']",
    "[data-testid='reviewRating']",
    "meta[itemprop='ratingValue']",
)
_DETAIL_RATING_COUNT_SELECTORS = (
    "[data-testid='ratingCount']",
    "[aria-label*='rating' i]",
    "[aria-label*='ratings' i]",
    "[data-testid='totalRatings']",
    ".c-rating + span",
    "[data-testid='reviewCount']",
    "meta[itemprop='ratingCount']",
    "meta[itemprop='reviewCount']",
)
_DETAIL_REVIEW_SELECTORS = (
    "[data-testid='review']",
    "[data-testid='reviewText']",
    ".review-text",
    ".review-content",
    "div[class*='review'] p",
    "p[class*='review']",
    "[data-testid='userReview']",
    "section[aria-label*='review' i] p",
    "section[aria-label*='Bewertung' i] p",
)


def _resolve_hl(language: str) -> str:
    lang = (language or "de").lower()
    if lang.startswith("de"):
        return "de-DE"
    if lang.startswith("en"):
        return "en-US"
    if lang.startswith("fr"):
        return "fr-FR"
    if lang.startswith("es"):
        return "es-ES"
    if lang.startswith("it"):
        return "it-IT"
    return "en-US"


def _search_url(query: str, *, country: str, language: str) -> str:
    q = urllib.parse.quote(query)
    hl = _resolve_hl(language)
    gl = (country or "de").upper()
    return f"https://apps.microsoft.com/search?query={q}&hl={hl}&gl={gl}"


def _extract_id(href: str) -> str:
    """Best-effort product id from an MS detail href (last path segment).

    Returns the full product ID (e.g. ``9n7wbb04192f``) for both
    ``/detail/<id>`` and ``/store/detail/<id>`` shapes. The fallback
    rejects fragments shorter than 6 chars to avoid capturing path
    components like ``detail``.
    """
    m = _DETAIL_ID_RE.search(href or "")
    if m:
        return m.group(1)
    if "/detail/" in (href or ""):
        tail = href.rstrip("/").rsplit("/", 1)[-1]
        if tail and len(tail) >= 8 and "?" not in tail:
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


def _scrape_detail(page, app_id: str) -> Dict:
    """Run the extraction JS inside an already-rendered Playwright detail page.

    Returns a dict with description, rating_avg, rating_count, and up to 3
    review snippets. Every field degrades safely — a missing selector produces
    an empty default rather than an error. Also tries meta tags and full-page
    text as fallback strategies.
    """
    result: Dict = {
        "id": app_id,
        "description": "",
        "rating_avg": None,
        "rating_count": 0,
        "reviews_sample": [],
    }

    try:
        desc_texts = []
        for sel in _DETAIL_DESC_SELECTORS:
            try:
                els = page.query_selector_all(sel)
                texts = []
                for el in els:
                    t = el.evaluate("e => (e.innerText||'').trim()")
                    if t:
                        texts.append(t)
                if texts:
                    desc_texts = texts
                    break
            except Exception:
                continue
        if not desc_texts:
            try:
                meta = page.query_selector("meta[property='og:description']")
                if meta is not None:
                    content = meta.get_attribute("content")
                    if content and content.strip():
                        desc_texts = [content.strip()]
            except Exception:
                pass
        if not desc_texts:
            try:
                meta = page.query_selector("meta[name='description']")
                if meta is not None:
                    content = meta.get_attribute("content")
                    if content and content.strip():
                        desc_texts = [content.strip()]
            except Exception:
                pass
        if desc_texts:
            result["description"] = " ".join(desc_texts)
    except Exception:
        pass

    try:
        for sel in _DETAIL_RATING_SELECTORS:
            try:
                el = page.query_selector(sel)
                if el is not None:
                    text = el.evaluate("e => (e.innerText||'').trim()") or el.get_attribute("content") or ""
                    if text:
                        val = text.replace(",", ".").replace("(", "").replace(")", "").strip()
                        try:
                            result["rating_avg"] = float(val)
                            break
                        except (ValueError, TypeError):
                            pass
                if sel.startswith("meta"):
                    content = el.get_attribute("content") if el else None
                    if content:
                        try:
                            result["rating_avg"] = float(content.strip())
                            break
                        except (ValueError, TypeError):
                            pass
            except Exception:
                continue
    except Exception:
        pass

    try:
        for sel in _DETAIL_RATING_COUNT_SELECTORS:
            try:
                el = page.query_selector(sel)
                if el is not None:
                    text = el.evaluate("e => (e.innerText||'').trim()")
                    if text:
                        nums = re.findall(r"(\d[\d.,]*)", text)
                        if nums:
                            clean = nums[0].replace(",", "").replace(".", "")
                            try:
                                result["rating_count"] = int(clean)
                                break
                            except (ValueError, TypeError):
                                continue
            except Exception:
                continue
    except Exception:
        pass

    try:
        reviews: List[str] = []
        for sel in _DETAIL_REVIEW_SELECTORS:
            try:
                els = page.query_selector_all(sel)
                for el in els[:3]:
                    t = el.evaluate("e => (e.innerText||'').trim()")
                    if t and len(t) > 10:
                        reviews.append(t[:500])
                if reviews:
                    break
            except Exception:
                continue
        result["reviews_sample"] = reviews[:3]
    except Exception:
        pass

    return result


def _detail_url(app_id: str, *, country: str = "de", language: str = "de") -> str:
    hl = _resolve_hl(language)
    gl = (country or "de").upper()
    return f"https://apps.microsoft.com/detail/{app_id}?hl={hl}&gl={gl}"


def fetch_ms_detail(
    app_ids: List[str],
    *,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = BROWSER_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
    cap: int = _DETAIL_CAP,
    country: str = "de",
    language: str = "de",
) -> Dict[str, Dict]:
    """Scrape MS Store detail pages for a list of app IDs (SPA-aware, cache-backed).

    Uses ``networkidle`` **+** ``wait_for_selector`` because apps.microsoft.com
    is a single-page app. Per-run cap limits total detail fetches. Never raises —
    returns a dict mapping app_id -> enriched fields; a missing entry means the
    detail page could not be scraped.
    """
    import time as _time
    import random

    result: Dict[str, Dict] = {}
    if not app_ids:
        return result

    now_ts = _time.time() if now is None else now
    capped = list(app_ids)[:cap]

    fresh_ids: List[str] = []
    for app_id in capped:
        url = _detail_url(app_id, country=country, language=language)
        key = CACHE.cache_key("BROWSER", url, {})
        path = CACHE.cache_path(cache_dir, key)
        if not fresh and CACHE.is_fresh(path, ttl, now_ts):
            cached = CACHE.read_cache(path)
            if cached is not None:
                try:
                    result[app_id] = json.loads(cached.decode("utf-8"))
                    continue
                except Exception:
                    pass
        fresh_ids.append(app_id)

    if not fresh_ids:
        return result

    for app_id in fresh_ids:
        url = _detail_url(app_id, country=country, language=language)
        if not POLITE.robots_allows(url):
            continue

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        return result

    ok, reason = _ensure_chromium()
    if not ok:
        _chromium_log(f"browser blocked: {reason}")
        return result

    rng = random.Random()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                locale=POLITE.LOCALE,
                user_agent=POLITE.USER_AGENT,
                extra_http_headers={"Accept-Language": POLITE.ACCEPT_LANGUAGE},
            )
            page = context.new_page()
            for app_id in fresh_ids:
                url = _detail_url(app_id, country=country, language=language)
                detail: Optional[Dict] = None
                try:
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
                                break
                    try:
                        page.wait_for_load_state("networkidle", timeout=25000)
                    except Exception:
                        pass
                    ready = False
                    detail_ready_selectors = (
                        "[data-testid='productDetails']",
                        "[data-testid='ProductDescription']",
                        "h1",
                        "section[aria-label*='description' i]",
                        "section[aria-label*='Description' i]",
                        "main[role='main']",
                        "div[id='product-description']",
                        "div[class*='description']",
                        "div[class*='product-description']",
                        "[data-testid='reviewRating']",
                        ".c-rating-stars",
                        ".rating-stars",
                        "meta[property='og:title']",
                    )
                    for sel in detail_ready_selectors:
                        try:
                            page.wait_for_selector(sel, timeout=15000)
                            ready = True
                            break
                        except Exception:
                            continue
                    if not ready:
                        try:
                            page.wait_for_timeout(5000)
                            title = page.title()
                            if title and title.strip() and "404" not in title.lower():
                                ready = True
                        except Exception:
                            pass
                    if ready:
                        detail = _scrape_detail(page, app_id)
                except Exception:
                    pass

                if detail is not None:
                    result[app_id] = detail
                    try:
                        key = CACHE.cache_key("BROWSER", url, {})
                        path = CACHE.cache_path(cache_dir, key)
                        CACHE.write_cache(path, json.dumps(detail).encode("utf-8"), now=now_ts)
                    except Exception:
                        pass
            browser.close()
    except Exception:
        pass

    return result


def enrich(
    app_ids: List[str],
    *,
    cache_dir: str = "",
    fresh: bool = False,
    country: str = "de",
    language: str = "de",
    detail_fn: Optional[Callable[..., Dict[str, Dict]]] = None,
) -> Dict[str, Dict]:
    """Return enriched data for a list of MS app IDs (SPA-aware, never-blocking).

    The injected ``detail_fn`` (default :func:`fetch_ms_detail`) lets the
    orchestration run offline with a recorded fixture.
    """
    do_fetch = detail_fn or fetch_ms_detail
    try:
        return do_fetch(
            app_ids, cache_dir=cache_dir, fresh=fresh,
            country=country, language=language,
        )
    except Exception:
        return {}


if __name__ == "__main__":  # pragma: no cover — manual live-smoke entry
    import sys
    term = sys.argv[1] if len(sys.argv) > 1 else "habit tracker"
    print(json.dumps(search(term), indent=2, ensure_ascii=False))
