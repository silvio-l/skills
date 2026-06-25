#!/usr/bin/env python3
"""Unified category taxonomy + raw-iTunes→Core metadata mapping.

The PRD defines a per-app schema split into **Core** (all stores) and
**Slots** (per-store). This slice collects Apple **Core** only and
leaves the Apple slot fields empty (the subtitle needs Playwright →
slice 02; the description is a slot too). Slot keys are still emitted
so slice 02 fills them in place rather than reshaping the artefact.

Core keys (this slice populates):
    id, platform, store_url, title, developer, category,
    rating_avg, rating_count, last_updated, price_model, screenshot_count

Apple slot keys (left empty by this slice):
    subtitle, description, keyword_hints

The taxonomy below is deliberately small and explicit. Unknown iTunes
genres fall back to ``"other"`` rather than passing an unmapped string
through — a single, stable vocabulary downstream.
"""

from __future__ import annotations

import re
from typing import Dict, List

PLATFORM = "apple"

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


def map_itunes_to_core(raw: dict) -> dict:
    """Map one raw iTunes ``software`` result onto the Core+Slots schema.

    Slot fields are emitted empty by this slice (see module docstring).
    Missing Core fields degrade to safe defaults rather than raising, so
    one oddly-shaped result cannot abort a whole discovery pass.
    """
    track_id = raw.get("trackId")
    return {
        # --- Core (this slice) ---
        "id": str(track_id) if track_id is not None else "",
        "platform": PLATFORM,
        "store_url": raw.get("trackViewUrl") or "",
        "title": raw.get("trackName") or "",
        "developer": raw.get("artistName") or raw.get("sellerName") or "",
        "category": map_category(raw.get("primaryGenreName") or ""),
        "rating_avg": raw.get("averageUserRating"),
        "rating_count": raw.get("userRatingCount", 0) or 0,
        "last_updated": raw.get("currentVersionReleaseDate") or "",
        "price_model": infer_price_model(raw),
        "screenshot_count": len(_screenshots(raw)),
        # --- Apple slots (empty by this slice; slice 02 fills) ---
        "subtitle": "",
        "description": "",
        "keyword_hints": [],
    }
