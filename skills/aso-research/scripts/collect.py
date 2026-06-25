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
    """Run the real extract -> score engine over the deep competitor corpus."""
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
    return {"keywords": keywords}
