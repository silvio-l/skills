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
import os
import re
import subprocess
import sys
from typing import Callable, Dict, List, Optional, Tuple

import cache as CACHE
import politeness as POLITE

BROWSER_TTL = CACHE.BROWSER_TTL

# Chromium bootstrap — idempotent per-process probe + install.
_ensure_chromium_done = False
_ensure_chromium_result: Optional[Tuple[bool, Optional[str]]] = None


def _chromium_log(msg: str, *, log_file=None) -> None:
    """Emit an observable [chromium] log line to the supplied file or stderr."""
    target = log_file if log_file is not None else sys.stderr
    print(f"[chromium] {msg}", file=target)


def _ensure_chromium(
    probe_fn=None,
    install_fn=None,
    *,
    log_file=None,
) -> Tuple[bool, Optional[str]]:
    """Ensure Playwright's Chromium binary is present; install if missing.

    Idempotent — the probe runs at most once per process. Returns
    ``(available: bool, reason: str | None)``. A ``False`` return is a
    never-blocking degradation: the caller skips browser work and reports
    the reason upstream.

    Both ``probe_fn() -> bool`` and ``install_fn() -> bool | (bool, str)``
    are injectable so tests can simulate every state without a real browser.
    """
    global _ensure_chromium_done, _ensure_chromium_result
    if _ensure_chromium_done:
        _chromium_log("(cached) skip probe — already ran this process", log_file=log_file)
        assert _ensure_chromium_result is not None
        return _ensure_chromium_result

    _ensure_chromium_done = True

    if probe_fn is None:
        def _default_probe() -> bool:
            try:
                from playwright.sync_api import sync_playwright
            except Exception:
                return False
            try:
                with sync_playwright() as pw:
                    exe = pw.chromium.executable_path
                    return bool(exe and os.path.exists(exe))
            except Exception:
                return False
        probe_fn = _default_probe

    try:
        present = probe_fn()
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        _chromium_log(f"probe error: {reason}", log_file=log_file)
        _ensure_chromium_result = (False, reason)
        return _ensure_chromium_result

    if present:
        _chromium_log("probe: present -> skip install", log_file=log_file)
        _ensure_chromium_result = (True, None)
        return _ensure_chromium_result

    _chromium_log("probe: absent -> installing chromium...", log_file=log_file)

    if install_fn is None:
        def _default_install():
            result = subprocess.run(
                [sys.executable, "-m", "playwright", "install", "chromium"],
                capture_output=True,
                text=True,
                timeout=120,
            )
            return result.returncode == 0, result.stderr.strip() or result.stdout.strip()
        install_fn = _default_install

    try:
        install_result = install_fn()
    except Exception as exc:
        reason = f"{type(exc).__name__}: {exc}"
        _chromium_log(f"install error: {reason}", log_file=log_file)
        _ensure_chromium_result = (False, reason)
        return _ensure_chromium_result

    if isinstance(install_result, bool):
        ok, output = install_result, ""
    else:
        ok, output = install_result

    if ok:
        _chromium_log("install: ok", log_file=log_file)
        _ensure_chromium_result = (True, None)
    else:
        reason = (output or "install failed").split("\n")[0].strip()[:120]
        _chromium_log(f"install: failed — {reason}", log_file=log_file)
        _ensure_chromium_result = (False, reason)

    return _ensure_chromium_result
# Tolerant subtitle selectors (Apple markup shifts; try several, take first).
# Current (2026) apps.apple.com is a Svelte SPA: the subtitle is a
# ``<p class="subtitle">`` sibling right after the ``<h1>`` title. The older
# ``product-header__subtitle`` classes are kept as fallbacks for cached/older
# markup; the broad ``[class*='subtitle']`` is the last-resort net.
_SUBTITLE_SELECTORS = (
    "p.subtitle",
    "section > h1 + p.subtitle",
    "h2.product-header__subtitle",
    ".product-header__subtitle",
    "[data-test-id='app-subtitle']",
    "[class*='subtitle']",
)
_APP_ID_RE = re.compile(r"/app/(?:[^/]+/)?id(\d+)")

# Module-level rate limiter: ONE instance so the >=1 req/s/domain interval is
# enforced ACROSS product-page fetches. A fresh limiter per call (the previous
# bug) reset the per-host clock every time, so ~10 rapid fetches tripped
# Apple's 429 throttle — the real cause of empty subtitle/similar runs.
_RATE = POLITE.RateLimiter(seed=7)


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

    result = {"subtitle": subtitle, "similar_app_ids": similar[:15]}
    # LLM-selector fallback: if every deterministic subtitle selector missed,
    # capture a bounded snippet of the title's container so the agent can
    # extract the subtitle from the raw HTML (self-heals when Apple shifts its
    # markup). Bounded to ~4 KB and only on a miss → cheap, no PII.
    if not subtitle:
        try:
            h1 = page.query_selector("h1")
            html = h1.evaluate(
                "e => { const s = e.closest('section,header,main') || e.parentElement;"
                " return s ? s.outerHTML.slice(0, 4000) : ''; }"
            ) if h1 else ""
            if html:
                result["subtitle_html"] = html
        except Exception:
            pass
    return result


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

    ok, reason = _ensure_chromium()
    if not ok:
        _chromium_log(f"browser blocked: {reason}")
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
            # (module-level limiter so the interval holds across fetches)
            _RATE.wait(url)
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


def collect_subtitle_fallback(
    app_id: str,
    *,
    country: str = "de",
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    fresh: bool = False,
    fetch_fn: Optional[Callable[..., Dict]] = None,
) -> str:
    """Return the captured header HTML snippet when subtitle selectors missed.

    Empty string when the subtitle was found (no fallback needed) or no snippet
    was captured. Reads the same cache-backed fetch as :func:`collect_subtitle`,
    so it adds no extra page load.
    """
    do_fetch = fetch_fn or fetch_apple_app
    try:
        res = do_fetch(app_id, country=country, cache_dir=cache_dir, fresh=fresh)
        return res.get("subtitle_html", "") if not res.get("subtitle") else ""
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
