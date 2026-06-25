#!/usr/bin/env python3
"""Report assembly for aso-research (slice 02).

Gains a real **Keyword Report** section driven by the scored keywords
(Competition/Relevance signal, Opportunity, primary/long-tail split,
``is_gap``), a **Competitive Landscape** that surfaces niche competitors
from the similar-apps hop, a **Sources** section (which ran vs
unavailable), and an honest **Methodology** footnote.

Determinism: the report body is stable for a given
(config, competitors, keywords, source_status); only the generated
timestamp differs between runs (expected). The timestamp is injected by
the caller so a test can fix it. Optional kwargs (``source_status`` …)
default so the slice-01 call shape keeps working.

Score labels read **"Competition/Relevance signal"** — never "search
volume" (PRD honesty rule, an acceptance criterion).
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional

_GENERATED_LABEL = "Generated"
_KEYWORD_REPORT_LIMIT = 30  # top-N keywords shown in the report table


def _row(cells: List[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _md_escape(text: str) -> str:
    if text is None:
        return ""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def build_report(
    config: Dict,
    competitors: List[Dict],
    keywords: List[Dict],
    *,
    now: datetime.datetime,
    source_status: Optional[Dict[str, str]] = None,
    reddit_threads: Optional[List[Dict]] = None,
) -> str:
    """Assemble the ``report.md`` body as a string."""
    n_comp = len(competitors)
    niche = [c for c in competitors if c.get("discovery") == "niche_similar"]
    primary = [k for k in keywords if k.get("split") == "primary-candidate"]
    longtail = [k for k in keywords if k.get("split") == "long-tail-candidate"]
    gaps = [k for k in keywords if k.get("is_gap")]
    top_kw = ", ".join(k["term"] for k in keywords[:8]) or "—"
    generated = now.strftime("%Y-%m-%d %H:%M:%S")
    source_status = source_status or {}

    lines: List[str] = []
    lines.append(f"# ASO Research — {config['app_name']}")
    lines.append("")
    lines.append(f"_{_GENERATED_LABEL}: {generated}_")
    lines.append("")

    # --- 1. Executive Summary ---
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(
        f"Discovered **{n_comp}** Apple competitor(s) via the iTunes Search API, "
        f"enriched with the Apple **subtitle** (Playwright) and a **similar-apps** "
        f"hop that surfaced **{len(niche)}** niche competitor(s). Keywords were "
        f"extracted with a YAKE + TF-IDF engine (position-weighted) and scored "
        f"with the Competition/Relevance proxy — **not** real search volume."
    )
    lines.append("")
    lines.append(f"- **Category:** {config.get('category', 'other')}")
    lines.append(f"- **Country / language:** {config['country']} / {config['language']}")
    own = config.get("own_app_id")
    if own:
        lines.append(f"- **Mode:** A (own app `{own}` carried, not yet self-audited)")
    else:
        lines.append("- **Mode:** B (pre-launch / idea only)")
    seeds = config.get("seed_keywords") or []
    if seeds:
        lines.append("- **Seed keywords:** " + ", ".join(seeds))
    lines.append(
        f"- **Keyword split:** {len(primary)} primary-candidate / "
        f"{len(longtail)} long-tail-candidate ({len(gaps)} coverage gap flagged)"
    )
    lines.append(f"- **Top keywords:** {top_kw}")
    lines.append("")

    # --- 2. Competitive Landscape ---
    lines.append("## Competitive Landscape")
    lines.append("")
    if not competitors:
        lines.append("_No competitors discovered for this seed._")
    else:
        header = _row(
            ["Title", "Developer", "Category", "Rating", "# Ratings", "Price", "Source"]
        )
        sep = _row(["---", "---", "---", "---", "---", "---", "---"])
        lines.append(header)
        lines.append(sep)
        for c in competitors:
            rating = c.get("rating_avg")
            rating_str = f"{float(rating):.1f}" if isinstance(rating, (int, float)) else "—"
            source = "niche" if c.get("discovery") == "niche_similar" else "chart/search"
            sub = c.get("subtitle") or ""
            title = _md_escape(c.get("title", ""))
            if sub:
                title = f"{title} — *{_md_escape(sub)}*"
            lines.append(
                _row(
                    [
                        title,
                        _md_escape(c.get("developer", "")),
                        str(c.get("category", "")),
                        rating_str,
                        str(c.get("rating_count", 0)),
                        str(c.get("price_model", "")),
                        source,
                    ]
                )
            )
    lines.append("")

    # --- 3. Keyword Report ---
    lines.append("## Keyword Report")
    lines.append("")
    lines.append(
        "Scores are a deterministic **Competition/Relevance signal** — a proxy, "
        "**never** search volume. Competition = position-weighted title/subtitle/"
        "description share; Relevance = cosine TF-IDF to the seed concept "
        "(+15 Apple Search-Suggest boost); Opportunity = Relevance × (100 − "
        "Competition) (+10 niche bonus)."
    )
    lines.append("")
    if not keywords:
        lines.append("_No keywords scored (empty competitor corpus)._")
    else:
        header = _row(
            [
                "Keyword", "Competition signal", "Relevance signal", "Opportunity",
                "Split", "Gap", "Suggest",
            ]
        )
        sep = _row(["---", "---", "---", "---", "---", "---", "---"])
        lines.append(header)
        lines.append(sep)
        for k in keywords[:_KEYWORD_REPORT_LIMIT]:
            lines.append(
                _row(
                    [
                        _md_escape(k.get("term", "")),
                        str(k.get("competition", 0)),
                        str(k.get("relevance", 0)),
                        str(k.get("opportunity", 0)),
                        k.get("split", "").replace("-candidate", ""),
                        "yes" if k.get("is_gap") else "",
                        "yes" if k.get("suggest") else "",
                    ]
                )
            )
        lines.append("")
        if gaps:
            gap_terms = ", ".join(_md_escape(k["term"]) for k in gaps[:15])
            lines.append(f"**Coverage gaps** (competitors own in Title, seed lacks): {gap_terms}")
            lines.append("")

    # --- 4. Qualitative signals (Reddit) ---
    if reddit_threads:
        lines.append("## Qualitative Signals (Reddit)")
        lines.append("")
        for t in reddit_threads[:8]:
            sub = t.get("subreddit") or "—"
            lines.append(f"- **r/{sub}** — {_md_escape(t.get('title', ''))}")
        lines.append("")

    # --- 5. Sources ---
    lines.append("## Sources")
    lines.append("")
    if source_status:
        for src in (
            "apple_subtitle", "apple_similar", "apple_rss_charts",
            "reddit", "apple_search_suggest",
        ):
            if src in source_status:
                status = source_status[src]
                tag = "✅ ran" if status == "ok" else "⚠️ unavailable"
                lines.append(f"- **{src}:** {tag}")
        lines.append("")
    else:
        lines.append("- iTunes Search API (always on)")
        lines.append("")

    # --- Methodology footnote ---
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "Apple **Core + Slots** metadata collected (subtitle via Playwright, "
        "description from the iTunes API, keyword_hints inferred by inversion — "
        "never the hidden 100-char field). Keyword extraction: YAKE phrases + "
        "TF-IDF with position weighting (Title ×5 · Subtitle ×3 · Description ×1) "
        "+ Apple Search-Suggest enrichment; DE+EN stopwords, generics filtered, "
        "light morphology grouping. Scoring is a **Competition/Relevance proxy**, "
        "explicitly **not real search volume** — labelled as signal throughout. "
        "Politeness: ≤1 req/s/domain + jitter, exponential backoff on 429/503 "
        "(max 3 then skip), robots.txt respected, **no stealth plugins**. A "
        "failing source is marked unavailable and the pipeline continues. HTTP "
        "cache 24h / browser cache 12h at `~/.cache/aso-research/`."
    )
    lines.append("")
    return "\n".join(lines)
