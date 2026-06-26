#!/usr/bin/env python3
"""Unified category taxonomy + raw-iTunes→Core metadata mapping (slice 02).

The PRD defines a per-app schema split into **Core** (all stores) and
**Slots** (per-store). Slice 02 completes the Apple slots:

* ``description`` — taken from the iTunes ``description`` field (HTML
  stripped). The iTunes API *does* return it (unlike the subtitle).
* ``subtitle`` — left empty by :func:`map_itunes_to_core` because the
  iTunes API never returns it; the Playwright collector fills it via
  :func:`merge_apple_slots`.
* ``keyword_hints`` — inferred by *inversion*: the distinctive terms an
  app puts in its high-signal fields (title/subtitle) hint at the hidden
  100-char keyword field. We never read that hidden field — we infer.

Core keys: id, platform, store_url, title, developer, category,
rating_avg, rating_count, last_updated, price_model, screenshot_count.
Apple slot keys: subtitle, description, keyword_hints.
Discovery field: similar_app_ids[] (filled by the similar-apps collector).

The taxonomy below is deliberately small and explicit. Unknown iTunes
genres fall back to ``"other"`` rather than passing an unmapped string
through — a single, stable vocabulary downstream.
"""

from __future__ import annotations

import re
from typing import Dict, List

PLATFORM = "apple"
PLAY_PLATFORM = "play"
MS_PLATFORM = "ms"

# Discovery slot: populated by the similar-apps collector (slice 02).
_DEFAULT_CORE: Dict[str, object] = {
    "similar_app_ids": [],
}

# ---------------------------------------------------------------------------
# Unified category taxonomy (iTunes primaryGenreName → unified slug)
# ---------------------------------------------------------------------------

TAXONOMY: Dict[str, str] = {
    "music": "music",
    "productivity": "productivity",
    "health & fitness": "health_fitness",
    "fitness": "health_fitness",
    "games": "games",
    "lifestyle": "lifestyle",
    "business": "business",
    "education": "education",
    "finance": "finance",
    "social networking": "social",
    "photo & video": "photo_video",
    "photography": "photo_video",
    "video": "photo_video",
    "utilities": "utilities",
    "entertainment": "entertainment",
    "food & drink": "food_drink",
    "travel": "travel",
    "weather": "weather",
    "news": "news",
    "books": "books",
    "reference": "reference",
    "medical": "medical",
    "navigation": "navigation",
    "shopping": "shopping",
    "sports": "sports",
    "developer tools": "developer_tools",
    "graphics & design": "graphics_design",
    "newsstand": "news",
    "magazines & newspapers": "news",
}

DEFAULT_CATEGORY = "other"


def _normalize_genre(genre: str) -> str:
    return re.sub(r"\s+", " ", genre.strip().lower())


def map_category(genre: str) -> str:
    """Map a store genre name onto the unified taxonomy (fallback ``other``)."""
    if not genre:
        return DEFAULT_CATEGORY
    return TAXONOMY.get(_normalize_genre(genre), DEFAULT_CATEGORY)


# ---------------------------------------------------------------------------
# price model inference
# ---------------------------------------------------------------------------

_FREE_HINTS = ("gratis", "free", "kostenlos", "gratuit", "$0.00", "0,00 €", "0.00")


def infer_price_model(raw: dict) -> str:
    """Infer ``free`` / ``paid`` from the iTunes price + formattedPrice fields."""
    price = raw.get("price")
    if isinstance(price, (int, float)) and price > 0:
        return "paid"
    formatted = str(raw.get("formattedPrice") or "").strip().lower()
    if formatted and not any(hint in formatted for hint in _FREE_HINTS):
        return "paid"
    return "free"


# ---------------------------------------------------------------------------
# Core + empty-Slot mapping
# ---------------------------------------------------------------------------

def _screenshots(raw: dict) -> List[str]:
    return list(raw.get("screenshotUrls") or [])


_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")


def strip_html(text: str) -> str:
    """Collapse HTML tags and excess whitespace (iTunes descriptions carry HTML)."""
    if not text:
        return ""
    no_tags = _HTML_TAG_RE.sub(" ", str(text))
    return _WS_RE.sub(" ", no_tags).strip()


def infer_keyword_hints(title: str, subtitle: str, description: str, *, limit: int = 10) -> List[str]:
    """Infer Apple keyword-field hints by inversion (never read the hidden field).

    The terms an app emphasises in its high-signal fields (title, then
    subtitle) are the strongest signal of what hidden keywords it targets.
    We tokenise title+subtitle (then description as a fallback) with the
    extraction filter (stopwords/generics removed), de-duplicate, and keep
    the ``limit`` most title-weighted. Deterministic.
    """
    import extract  # type: ignore

    title_toks = extract.tokenize(title or "")
    sub_toks = extract.tokenize(subtitle or "")
    desc_toks = extract.tokenize(description or "")

    # weight: title tokens rank above subtitle above description
    ranked: Dict[str, int] = {}
    for tok in title_toks:
        ranked[tok] = max(ranked.get(tok, 0), 3)
    for tok in sub_toks:
        ranked[tok] = max(ranked.get(tok, 0), 2)
    for tok in desc_toks:
        ranked[tok] = max(ranked.get(tok, 0), 1)

    ordered = sorted(ranked.items(), key=lambda kv: (-kv[1], kv[0]))
    return [term for term, _w in ordered[:limit]]


def map_itunes_to_core(raw: dict) -> dict:
    """Map one raw iTunes ``software`` result onto the Core+Slots schema.

    The Apple ``description`` slot is populated (HTML stripped) from the
    iTunes ``description`` field. The ``subtitle`` slot stays empty — the
    iTunes API never returns it; the Playwright collector fills it via
    :func:`merge_apple_slots`. Missing Core fields degrade to safe
    defaults rather than raising, so one oddly-shaped result cannot abort
    a whole discovery pass.
    """
    track_id = raw.get("trackId")
    title = raw.get("trackName") or ""
    description = strip_html(raw.get("description") or "")
    hints = infer_keyword_hints(title, "", description)
    return {
        # --- Core ---
        "id": str(track_id) if track_id is not None else "",
        "platform": PLATFORM,
        "store_url": raw.get("trackViewUrl") or "",
        "title": title,
        "developer": raw.get("artistName") or raw.get("sellerName") or "",
        "category": map_category(raw.get("primaryGenreName") or ""),
        "rating_avg": raw.get("averageUserRating"),
        "rating_count": raw.get("userRatingCount", 0) or 0,
        "last_updated": raw.get("currentVersionReleaseDate") or "",
        "price_model": infer_price_model(raw),
        "screenshot_count": len(_screenshots(raw)),
        # --- Apple slots ---
        "subtitle": "",
        "description": description,
        "keyword_hints": hints,
        # --- Discovery slot ---
        "similar_app_ids": [],
    }


def merge_apple_slots(
    core: dict,
    *,
    subtitle: str = "",
    similar_app_ids: List[str] = None,
) -> dict:
    """Fill Apple slot/discovery fields collected only via the browser.

    Returns a new dict (does not mutate the caller's record). ``subtitle``
    comes from the Playwright product-page scrape; ``similar_app_ids``
    from the "You might also like" hop. Keyword hints are re-inferred once
    the subtitle is known (it is a high-signal field).
    """
    merged = dict(core)
    if subtitle:
        merged["subtitle"] = strip_html(subtitle)
        merged["keyword_hints"] = infer_keyword_hints(
            merged.get("title", ""), merged["subtitle"], merged.get("description", "")
        )
    if similar_app_ids is not None:
        # de-duped, order-preserved, str-coerced
        seen = set()
        clean = []
        for sid in similar_app_ids:
            s = str(sid).strip()
            if s and s not in seen:
                seen.add(s)
                clean.append(s)
        merged["similar_app_ids"] = clean
    return merged


# ---------------------------------------------------------------------------
# Google Play Core + Slots mapping (slice 04)
# ---------------------------------------------------------------------------

def infer_play_price_model(raw: dict) -> str:
    """Infer ``free`` / ``paid`` from the google-play-scraper price fields.

    The library returns ``free`` (bool) and/or ``price`` (number, 0 for free)
    and ``priceText``. We prefer the explicit boolean, then the numeric price.
    """
    if "free" in raw and raw["free"] is not None:
        return "free" if bool(raw["free"]) else "paid"
    price = raw.get("price")
    if isinstance(price, (int, float)) and price > 0:
        return "paid"
    return "free"


def map_play_to_core(raw: dict) -> dict:
    """Map one raw google-play-scraper ``app()`` result onto Core + Play slots.

    Play slots (PRD): ``short_description`` (80 chars, strong ranking factor)
    and ``full_description`` (4000 chars, fully indexed). The library exposes
    the short text as ``summary`` and the long text as ``description`` — both
    are HTML-stripped here for consistency with the Apple path.

    **``tags`` are deliberately NOT collected** (PRD + slice 04 decision): they
    are not reliably extractable from the public listing, verified in the
    feasibility probe. The record therefore carries no ``tags`` key at all.

    Missing Core fields degrade to safe defaults rather than raising, so one
    oddly-shaped result cannot abort a whole Play discovery pass.
    """
    app_id = raw.get("appId") or raw.get("id") or ""
    title = raw.get("title") or ""
    short = strip_html(raw.get("summary") or raw.get("shortDescription") or "")
    full = strip_html(raw.get("description") or raw.get("fullDescription") or "")
    genre = raw.get("genre") or raw.get("primaryGenre") or raw.get("genreId") or ""
    screenshots = raw.get("screenshots") or []
    return {
        # --- Core ---
        "id": str(app_id) if app_id != "" else "",
        "platform": PLAY_PLATFORM,
        "store_url": raw.get("url") or "",
        "title": title,
        "developer": raw.get("developer") or "",
        "category": map_category(genre) if not genre.isdigit() else DEFAULT_CATEGORY,
        "rating_avg": raw.get("score"),
        "rating_count": raw.get("ratings") or 0,
        "last_updated": raw.get("updated") or raw.get("released") or "",
        "price_model": infer_play_price_model(raw),
        "screenshot_count": len(screenshots),
        # --- Play slots (tags dropped by decision) ---
        "short_description": short,
        "full_description": full,
        # --- Discovery slot ---
        "similar_app_ids": [],
    }


def merge_play_slots(
    core: dict,
    *,
    similar_app_ids: List[str] = None,
) -> dict:
    """Fill the Play discovery slot collected from the similar-apps hop.

    Returns a new dict (does not mutate the caller's record). Mirrors
    :func:`merge_apple_slots` for the platform-agnostic discovery field.
    Play has no browser-only slot (short/full description come straight from
    the library), so only ``similar_app_ids`` is filled here.
    """
    merged = dict(core)
    if similar_app_ids is not None:
        seen = set()
        clean = []
        for sid in similar_app_ids:
            s = str(sid).strip()
            if s and s not in seen:
                seen.add(s)
                clean.append(s)
        merged["similar_app_ids"] = clean
    return merged


# ---------------------------------------------------------------------------
# Microsoft Store Core + description mapping (slice 05 — qualitative-only)
# ---------------------------------------------------------------------------

def infer_ms_price_model(raw: dict) -> str:
    """Infer ``free`` / ``paid`` from the MS Store price fields.

    MS Store scraping exposes a ``free`` boolean and/or a numeric ``price``;
    we prefer the explicit boolean, then the numeric price. Mirrors the Play
    inference shape.
    """
    if "free" in raw and raw["free"] is not None:
        return "free" if bool(raw["free"]) else "paid"
    price = raw.get("price")
    if isinstance(price, (int, float)) and price > 0:
        return "paid"
    return "free"


def map_ms_to_core(raw: dict) -> dict:
    """Map one raw Microsoft Store app record onto MS Core + ``description``.

    MS is a **qualitative-only** source (PRD "MS slots: description only"):
    there is NO MS ASO slot model, so this record carries exactly one slot —
    ``description`` — plus the Core fields and the discovery field. It is
    structurally isolated from scoring: the dispatcher keeps MS entries out of
    the extraction/scoring corpus and feeds them to S1 as qualitative context.

    The raw dict is whatever the SPA-aware MS collector extracts from
    ``apps.microsoft.com`` (id, title, description, publisher, category,
    ratings, price, last update, screenshots). Missing fields degrade to safe
    defaults rather than raising, so one oddly-shaped result cannot abort the
    best-effort pass. The record intentionally carries NO Apple/Play slot keys.
    """
    app_id = raw.get("id") or raw.get("productId") or ""
    title = raw.get("title") or raw.get("name") or ""
    description = strip_html(raw.get("description") or "")
    category = raw.get("category") or raw.get("primaryCategory") or raw.get("genre") or ""
    screenshots = raw.get("screenshots") or raw.get("screenshotUrls") or []
    rating_avg = raw.get("averageRating")
    if rating_avg is None:
        rating_avg = raw.get("rating_avg")
    reviews_sample = raw.get("reviews_sample") or raw.get("reviewsSample") or []
    return {
        # --- Core ---
        "id": str(app_id) if app_id != "" else "",
        "platform": MS_PLATFORM,
        "store_url": raw.get("store_url") or raw.get("url") or "",
        "title": title,
        "developer": raw.get("publisher") or raw.get("developer") or "",
        "category": map_category(category),
        "rating_avg": rating_avg,
        "rating_count": raw.get("ratingCount") or raw.get("rating_count") or 0,
        "last_updated": raw.get("lastUpdateDate") or raw.get("last_updated") or "",
        "price_model": infer_ms_price_model(raw),
        "screenshot_count": len(screenshots),
        # --- MS slot (description only — NO other slot model) ---
        "description": description,
        # --- Discovery slot ---
        "similar_app_ids": [],
        # --- Optional qualitative slots ---
        "reviews_sample": list(reviews_sample)[:3],
    }
