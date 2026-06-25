#!/usr/bin/env python3
"""Apple Store Discovery via the iTunes Search API (slice 01's only channel).

Honours the documented ~20/min politeness limit (3 s between live
calls). No Playwright, no charts, no Reddit — those are later slices.

Split for testability:

* :func:`search`        — live HTTP via urllib, consults :mod:`cache`.
  **Not unit-tested** (external; its format would rot tests). Verified
  by the dispatcher's manual live-smoke run instead.
* :func:`process_results` — pure transform from raw iTunes result list
  → deduped Core competitor list + extracted+scored keywords. Fully
  offline-testable with a recorded fixture (this is how the
  determinism AC is proven without making live calls in tests).
* :func:`discover`      — orchestrates search → process_results for the
  pipeline.
"""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
from typing import Callable, Dict, List, Optional

import cache as CACHE
import extract
import score
from schema import map_itunes_to_core

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"
DEFAULT_LIMIT = 20
# iTunes Search/Lookup documented ~20/min → 3s between live calls.
POLITENESS_SECONDS = 3.0
USER_AGENT = "aso-research/0.1 (local research; +https://developer.apple.com/itunes/)"


# ---------------------------------------------------------------------------
# Live search (NOT unit-tested)
# ---------------------------------------------------------------------------

def search(
    term: str,
    *,
    country: str = "de",
    entity: str = "software",
    limit: int = DEFAULT_LIMIT,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = CACHE.HTTP_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> Dict:
    """Run one iTunes Search query, cache-backed.

    Returns the parsed JSON mapping. On a cache hit within TTL, no live
    call is made. Raises ``RuntimeError`` on a non-200 response.
    """
    params = {"term": term, "country": country, "entity": entity, "limit": str(limit)}
    key = CACHE.cache_key("GET", ITUNES_SEARCH_URL, params)
    path = CACHE.cache_path(cache_dir, key)
    now_ts = time.time() if now is None else now

    if not fresh and CACHE.is_fresh(path, ttl, now_ts):
        cached = CACHE.read_cache(path)
        if cached is not None:
            return json.loads(cached.decode("utf-8"))

    query = urllib.parse.urlencode(params)
    url = ITUNES_SEARCH_URL + "?" + query
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    # Politeness: pace live calls so we stay under ~20/min.
    sleep(POLITENESS_SECONDS)
    with urllib.request.urlopen(req, timeout=30) as resp:
        status = getattr(resp, "status", resp.getcode())
        raw = resp.read()
    if status != 200:
        raise RuntimeError(f"iTunes Search returned HTTP {status} for term={term!r}")
    CACHE.write_cache(path, raw, now=now_ts)
    return json.loads(raw.decode("utf-8"))


# ---------------------------------------------------------------------------
# Live lookup (NOT unit-tested) — metadata for ids the similar-apps hop finds
# ---------------------------------------------------------------------------

ITUNES_LOOKUP_URL = "https://itunes.apple.com/lookup"


def lookup(
    app_id: str,
    *,
    country: str = "de",
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = CACHE.HTTP_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
    sleep: Callable[[float], None] = time.sleep,
) -> Dict:
    """Look up one app's raw iTunes record by id, cache-backed.

    Returns ``{}`` when the id resolves to nothing (never raises).
    """
    params = {"id": str(app_id), "country": country}
    key = CACHE.cache_key("GET", ITUNES_LOOKUP_URL, params)
    path = CACHE.cache_path(cache_dir, key)
    now_ts = time.time() if now is None else now

    if not fresh and CACHE.is_fresh(path, ttl, now_ts):
        cached = CACHE.read_cache(path)
        if cached is not None:
            payload = json.loads(cached.decode("utf-8"))
            results = payload.get("results") or []
            return results[0] if results else {}

    query = urllib.parse.urlencode(params)
    url = ITUNES_LOOKUP_URL + "?" + query
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    sleep(POLITENESS_SECONDS)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            status = getattr(resp, "status", resp.getcode())
            raw = resp.read()
    except Exception:
        return {}
    if status != 200:
        return {}
    CACHE.write_cache(path, raw, now=now_ts)
    payload = json.loads(raw.decode("utf-8"))
    results = payload.get("results") or []
    return results[0] if results else {}


# ---------------------------------------------------------------------------
# Pure transform (offline-testable)
# ---------------------------------------------------------------------------

def _dedupe_by_id(competitors: List[Dict]) -> List[Dict]:
    seen = set()
    out = []
    for comp in competitors:
        cid = comp.get("id")
        if cid in seen:
            continue
        seen.add(cid)
        out.append(comp)
    return out


def process_results(
    raw_results: List[Dict],
    config: Dict,
    *,
    suggest_terms: Optional[List[str]] = None,
) -> Dict:
    """Map raw iTunes ``results`` → ``{competitors, keywords}``.

    Pure + deterministic: same raw_results + config → byte-identical
    output. ``competitors`` is sorted by ``(-rating_count, id)``;
    ``keywords`` is sorted by the scorer's key. The own-app id (Modus A)
    is carried through but **not** self-audited in this slice.

    Extraction runs the real engine over each competitor's
    title/subtitle/description (position-weighted); ``suggest_terms``
    (Apple Search-Suggest autocomplete) enrich + boost relevance.
    """
    competitors = [map_itunes_to_core(r) for r in raw_results]
    competitors = _dedupe_by_id(competitors)
    competitors.sort(key=lambda c: (-(c.get("rating_count") or 0), str(c.get("id"))))

    generics = [
        config.get("category", ""),
        "apple", "ios", "iphone", "ipad",
        config.get("app_name", ""),
    ]
    documents = [
        {
            "title": c.get("title", ""),
            "subtitle": c.get("subtitle", ""),
            "description": c.get("description", ""),
        }
        for c in competitors
    ]
    suggest = list(suggest_terms or [])
    extracted = extract.extract_keywords(
        documents,
        generics=generics,
        seed_description=config.get("description") or "",
        suggest_terms=suggest,
    )
    keywords = score.score_keywords(
        extracted,
        seed_description=config.get("description") or "",
        suggest_terms=suggest,
        n_docs=len(competitors),
    )

    own_app_id = config.get("own_app_id")
    return {
        "competitors": competitors,
        "keywords": keywords,
        "own_app_id": own_app_id,
    }


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def discover(
    config: Dict,
    *,
    cache_dir: str = CACHE.DEFAULT_CACHE_DIR,
    ttl: float = CACHE.HTTP_TTL,
    now: Optional[float] = None,
    fresh: bool = False,
    max_queries: int = 3,
    limit: int = DEFAULT_LIMIT,
    search_fn=None,
    suggest_terms: Optional[List[str]] = None,
) -> Dict:
    """Run discovery for the resolved config and return process_results output.

    Query terms: seed keywords (capped at ``max_queries``), else the app
    name. ``search_fn`` is injectable so a caller can substitute a
    recorded fetch (tests); it defaults to the live :func:`search`.
    ``suggest_terms`` (Apple Search-Suggest autocomplete) enrich the
    extraction and boost relevance; collected by the dispatcher.
    """
    do_search = search_fn or search
    seeds = [s for s in (config.get("seed_keywords") or []) if s]
    terms = seeds[:max_queries] if seeds else [config["app_name"]]

    accumulated: List[Dict] = []
    for term in terms:
        payload = do_search(
            term,
            country=config.get("country", "de"),
            limit=limit,
            cache_dir=cache_dir,
            ttl=ttl,
            now=now,
            fresh=fresh,
        )
        accumulated.extend(payload.get("results") or [])
    return process_results(accumulated, config, suggest_terms=suggest_terms)
