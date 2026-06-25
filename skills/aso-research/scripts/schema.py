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
