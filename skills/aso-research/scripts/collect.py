#!/usr/bin/env python3
"""Deep Apple collection orchestration (slice 02).

Wires the deterministic spine end-to-end on top of the collectors:

    iTunes discovery (Core)
      -> enrich top-N with Apple subtitle (Playwright)
      -> similar-apps hop (1 hop from the ~5 strongest) -> niche competitors
      -> Apple RSS charts (deckel-limited)
      -> Reddit .json (qualitative signals + competitor names)
      -> Apple Search-Suggest autocomplete (enrich + relevance boost)
      -> extract -> score

Every collector is **injectable** so the orchestration logic (enrichment
merge, niche de-dup, source-status tracking, never-blocking) is fully
offline-testable with fixtures — the live collectors themselves are not
unit-tested (they fail loud and their formats rot; see CLAUDE.md).

A failing source is recorded as ``"unavailable"`` in ``source_status``
and the pipeline continues — it never blocks.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

import apple_browser
import apple_rss
import extract
import reddit
import score
import schema
import search_suggest
from schema import merge_apple_slots

# How many of the strongest hits to enrich with the subtitle + similar hop.
SUBTITLE_TOP_N = 10
SIMILAR_HOP_TOP_N = 5


def _safe(fn, *args, **kwargs):
    """Run a collector; on any exception return (None, error). Never raises."""
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:  # never-blocking
        return None, exc


def collect_apple(
    config: Dict,
    competitors: List[Dict],
    *,
    seed_terms: Optional[List[str]] = None,
    country: str = "de",
    cache_dir: str = "",
    fresh: bool = False,
    # injectable collectors (tests pass fakes; defaults hit the live modules)
    subtitle_fn: Optional[Callable] = None,
    similar_fn: Optional[Callable] = None,
    chart_fn: Optional[Callable] = None,
    reddit_fn: Optional[Callable] = None,
    suggest_fn: Optional[Callable] = None,
    lookup_fn: Optional[Callable] = None,
    subtitle_top_n: int = SUBTITLE_TOP_N,
    similar_top_n: int = SIMILAR_HOP_TOP_N,
) -> Dict:
    """Run the deep Apple channels over discovered competitors.

    Returns::

        {
          "competitors":   [...enriched + niche Core records, deduped, sorted],
          "suggest_terms": [...],
          "chart_ids":     [...],
          "reddit_threads":[...],
          "source_status": {"apple_subtitle": "ok"|"unavailable", ...},
        }

    Never-blocking: every collector is wrapped; a failure sets its
    ``source_status`` to ``"unavailable"`` and the run continues.
    """
    source_status: Dict[str, str] = {}
    subtitle_fn = subtitle_fn or apple_browser.collect_subtitle
    similar_fn = similar_fn or apple_browser.collect_similar
    chart_fn = chart_fn or apple_rss.collect
    reddit_fn = reddit_fn or reddit.collect
    suggest_fn = suggest_fn or search_suggest.collect
    lookup_fn = lookup_fn or (lambda *a, **k: {})

    seed_terms = list(seed_terms or config.get("seed_keywords") or [])
    if config.get("app_name"):
        seed_terms = seed_terms + [config["app_name"]]

    enriched: List[Dict] = [dict(c) for c in competitors]
    by_id = {c.get("id"): c for c in enriched if c.get("id")}

    # --- Apple subtitle (Playwright) on the top-N strongest hits ---
    strongest = list(enriched[:subtitle_top_n])
    subtitle_ok = False
    for comp in strongest:
        cid = comp.get("id")
        if not cid:
            continue
        sub, err = _safe(
            subtitle_fn, cid, country=country, cache_dir=cache_dir, fresh=fresh
        )
        if err is None and sub:
            by_id[cid] = merge_apple_slots(comp, subtitle=sub)
            subtitle_ok = True
    if not subtitle_ok and strongest:
        source_status["apple_subtitle"] = "unavailable"
    else:
        source_status["apple_subtitle"] = "ok"
    enriched = [by_id[c["id"]] if c.get("id") in by_id else c for c in enriched]

    # --- Similar-apps hop (1 hop from the ~5 strongest) -> niche competitors ---
    niche_ids: List[str] = []
    hop_ok = False
    for comp in enriched[:similar_top_n]:
        cid = comp.get("id")
        if not cid:
            continue
        sims, err = _safe(
            similar_fn, cid, country=country, cache_dir=cache_dir, fresh=fresh
        )
        if err is None:
            hop_ok = True
            for sid in sims or []:
                if sid not in by_id and sid not in niche_ids:
                    niche_ids.append(sid)
    source_status["apple_similar"] = "ok" if hop_ok else "unavailable"

    for sid in niche_ids:
        raw, err = _safe(lookup_fn, sid, country=country)
        if err is not None or not raw:
            continue
        from schema import map_itunes_to_core

        core = map_itunes_to_core(raw)
        if not core.get("id") or core["id"] in by_id:
            continue
        core = merge_apple_slots(core, similar_app_ids=[])
        core["discovery"] = "niche_similar"
        by_id[core["id"]] = core
        enriched.append(core)

    # --- Apple RSS charts (deckel-limited) ---
    chart_ids, cerr = _safe(
        chart_fn,
        config.get("category", ""),
        country=country,
        cache_dir=cache_dir,
        fresh=fresh,
    )
    source_status["apple_rss_charts"] = "unavailable" if cerr else "ok"
    chart_ids = chart_ids or []

    # --- Reddit .json (qualitative) ---
    reddit_queries = [f"{q} app" for q in seed_terms][:5] or [config.get("app_name", "")]
    threads, rerr = _safe(
        reddit_fn,
        reddit_queries,
        cache_dir=cache_dir,
        fresh=fresh,
    )
    source_status["reddit"] = "unavailable" if rerr else "ok"
    threads = threads or []

    # --- Apple Search-Suggest (autocomplete) ---
    suggest, serr = _safe(
        suggest_fn,
        seed_terms,
        cache_dir=cache_dir,
        fresh=fresh,
    )
    source_status["apple_search_suggest"] = "unavailable" if serr else "ok"
    suggest = suggest or []

    # deterministic re-sort: (-rating_count, id) keeps niche competitors in place
    enriched.sort(key=lambda c: (-(c.get("rating_count") or 0), str(c.get("id"))))

    return {
        "competitors": enriched,
        "suggest_terms": suggest,
        "chart_ids": chart_ids,
        "reddit_threads": threads,
        "source_status": source_status,
    }


def extract_and_score(
    competitors: List[Dict],
    config: Dict,
    suggest_terms: Optional[List[str]] = None,
) -> Dict:
    """Run the real extract -> score engine over the deep competitor corpus.

    Slice 04: the corpus is partitioned by platform so each vertical flows
    through the shared engine with its **own** slot model. Apple competitors
    (Title/Subtitle/Description, weights 5/3/1) and Play competitors
    (Title/Short/Long, weights 5/4/2) are extracted + scored separately, then
    merged into one unified score table. Every row is tagged ``platform`` and
    the table is sorted by ``(-opportunity, -relevance, term, platform)`` so
    identical input is byte-identical (determinism AC). Apple-only corpora
    behave exactly as in slice 02 (same fields, same weights, same order).
    """
    generics = [
        config.get("category", ""),
        "apple", "ios", "iphone", "ipad",
        "android", "google", "play",
        config.get("app_name", ""),
    ]
    suggest = list(suggest_terms or [])
    seed_description = config.get("description") or ""
    seed_keywords = list(config.get("seed_keywords") or [])

    apple_comps = [c for c in competitors if c.get("platform", "apple") == "apple"]
    play_comps = [c for c in competitors if c.get("platform") == "play"]

    merged: List[Dict] = []

    if apple_comps:
        apple_docs = [
            {
                "title": c.get("title", ""),
                "subtitle": c.get("subtitle", ""),
                "description": c.get("description", ""),
            }
            for c in apple_comps
        ]
        extracted = extract.extract_keywords(
            apple_docs,
            generics=generics,
            seed_description=seed_description,
            suggest_terms=suggest,
        )
        merged.extend(
            score.score_keywords(
                extracted,
                seed_description=seed_description,
                suggest_terms=suggest,
                n_docs=len(apple_comps),
                platform="apple",
            )
        )

    if play_comps:
        play_docs = [
            {
                "title": c.get("title", ""),
                "short": c.get("short_description", ""),
                "long": c.get("full_description", ""),
            }
            for c in play_comps
        ]
        extracted = extract.extract_keywords(
            play_docs,
            generics=generics,
            seed_description=seed_description,
            suggest_terms=suggest,
            fields=extract.PLAY_FIELDS,
        )
        merged.extend(
            score.score_keywords(
                extracted,
                seed_description=seed_description,
                suggest_terms=suggest,
                n_docs=len(play_comps),
                platform="play",
            )
        )

    merged.sort(key=lambda e: (-e["opportunity"], -e["relevance"], e["term"], e["platform"]))
    return {"keywords": merged}


# ---------------------------------------------------------------------------
# Deep Play collection orchestration (slice 04)
# ---------------------------------------------------------------------------

PLAY_SUBTITLE_TOP_N = 0  # Play has no browser-only slot; placeholder for symmetry
PLAY_SIMILAR_HOP_TOP_N = 5


def _play_safe(fn, *args, **kwargs):
    """Run a Play collector; on any exception return (None, error). Never raises."""
    try:
        return fn(*args, **kwargs), None
    except Exception as exc:  # never-blocking
        return None, exc


def collect_play(
    config: Dict,
    *,
    seed_terms: Optional[List[str]] = None,
    country: str = "de",
    cache_dir: str = "",
    fresh: bool = False,
    # injectable collectors (tests pass fakes; defaults hit the live module)
    search_fn: Optional[Callable] = None,
    lookup_fn: Optional[Callable] = None,
    chart_fn: Optional[Callable] = None,
    similar_fn: Optional[Callable] = None,
    suggest_fn: Optional[Callable] = None,
    similar_top_n: int = PLAY_SIMILAR_HOP_TOP_N,
) -> Dict:
    """Run the deep Play channels (search, charts, similar, suggest).

    Returns::

        {
          "competitors":   [...Play Core records, deduped, sorted],
          "suggest_terms": [...],                 # Play autocomplete
          "source_status": {"play_search": "ok"|"unavailable", ...},
        }

    Every collector is injectable so the orchestration logic (dedup,
    source-status tracking, never-blocking) is fully offline-testable with
    fixtures — the live google-play-scraper collector itself is not
    unit-tested. A failing source is recorded ``"unavailable"`` and the run
    continues (never-blocking), mirroring :func:`collect_apple`.
    """
    import play as play_collector  # type: ignore

    source_status: Dict[str, str] = {}
    search_fn = search_fn or play_collector.search
    lookup_fn = lookup_fn or play_collector.lookup
    chart_fn = chart_fn or play_collector.charts
    similar_fn = similar_fn or play_collector.similar
    suggest_fn = suggest_fn or play_collector.collect_suggest

    seed_terms = list(seed_terms or config.get("seed_keywords") or [])
    if config.get("app_name"):
        seed_terms = seed_terms + [config["app_name"]]

    by_id: Dict[str, Dict] = {}
    enriched: List[Dict] = []

    # --- Play search (seed keywords + app name) ---
    search_ok = False
    for term in seed_terms:
        results, err = _play_safe(search_fn, term, country=country, cache_dir=cache_dir, fresh=fresh)
        if err is None:
            search_ok = True
            for raw in results or []:
                core = schema.map_play_to_core(raw)
                if not core.get("id") or core["id"] in by_id:
                    continue
                by_id[core["id"]] = core
                enriched.append(core)
    source_status["play_search"] = "ok" if (search_ok or not seed_terms) else "unavailable"

    # --- Play category charts (deckel-limited) ---
    chart_raw, cerr = _play_safe(
        chart_fn, config.get("category", ""), country=country, cache_dir=cache_dir, fresh=fresh
    )
    source_status["play_charts"] = "unavailable" if cerr else "ok"
    for raw in chart_raw or []:
        core = schema.map_play_to_core(raw)
        if not core.get("id") or core["id"] in by_id:
            continue
        core["discovery"] = "chart"
        by_id[core["id"]] = core
        enriched.append(core)

    # --- Play similar-apps hop (1 hop from the strongest) -> niche competitors ---
    hop_ok = False
    niche_ids: List[str] = []
    strongest = sorted(
        enriched, key=lambda c: (-(c.get("rating_count") or 0), str(c.get("id")))
    )[:similar_top_n]
    for comp in strongest:
        cid = comp.get("id")
        if not cid:
            continue
        sims, err = _play_safe(similar_fn, cid, country=country, cache_dir=cache_dir, fresh=fresh)
        if err is None:
            hop_ok = True
            for sid in sims or []:
                if sid not in by_id and sid not in niche_ids:
                    niche_ids.append(sid)
    source_status["play_similar"] = "ok" if hop_ok else "unavailable"

    for sid in niche_ids:
        raw, err = _play_safe(lookup_fn, sid, country=country)
        if err is not None or not raw:
            continue
        core = schema.map_play_to_core(raw)
        if not core.get("id") or core["id"] in by_id:
            continue
        core = schema.merge_play_slots(core, similar_app_ids=[])
        core["discovery"] = "niche_similar"
        by_id[core["id"]] = core
        enriched.append(core)

    # --- Play Search-Suggest (autocomplete) ---
    suggest, serr = _play_safe(
        suggest_fn, seed_terms, country=country, cache_dir=cache_dir, fresh=fresh
    )
    source_status["play_search_suggest"] = "unavailable" if serr else "ok"
    suggest = suggest or []

    enriched.sort(key=lambda c: (-(c.get("rating_count") or 0), str(c.get("id"))))
    return {
        "competitors": enriched,
        "suggest_terms": suggest,
        "source_status": source_status,
    }
