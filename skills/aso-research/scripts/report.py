#!/usr/bin/env python3
"""Report assembly for aso-research (slice 03 — full 8-section report).

Assembles the canonical 8 sections from deterministic artefacts + the
subagent outputs the agent produces (H1/S1/S2/H2). Data-driven sections
(Executive Summary, Competitive Landscape, Keyword Report, Methodology)
assemble from the scored keywords + competitor metadata. Sections driven
by the LLM (Positioning Map, Opportunities, Risks/Threats, Listing
Recommendation) assemble from the subagent-output JSON when present, and
fall back to a deterministic, clearly-labelled read otherwise — so a
report is always valid and the LLM *enriches* rather than gates it.

Determinism: the body is stable for a given
(config, competitors, keywords, source_status, reddit_threads, subagent
outputs); only the injected timestamp differs between runs (expected).

Score labels read **"Competition/Relevance signal"** — never search
volume (PRD honesty rule, an acceptance criterion). Section 8 (Methodology)
is explicit about which signals are proxies, which sources ran vs were
unavailable, and what is missing.

Modus A: when ``own_app_id`` is present (and referenced) a self-audit
block renders inside the relevant sections — no separate code path (AC7).
Modus B = the same path with the self-audit block absent.
"""

from __future__ import annotations

import datetime
from typing import Dict, List, Optional

_GENERATED_LABEL = "Generated"
_KEYWORD_REPORT_LIMIT = 30  # top-N keywords shown in the report table

# Deterministic opportunity buckets (PRD "Opportunities" — quick win /
# niche lever / coverage gap), derived from the score table as the
# backbone; S1's qualitative read augments them when present.
_QUICK_WIN_OPP_MIN = 40
_QUICK_WIN_COMP_MAX = 30
_NICHE_LEVER_COMP_MAX = 20
_NICHE_LEVER_REL_MIN = 40
_OPPORTUNITY_BUCKET_LIMIT = 8


def _row(cells: List[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def _md_escape(text) -> str:
    if text is None:
        return ""
    return str(text).replace("|", "\\|").replace("\n", " ").strip()


def _opportunity_buckets(keywords: List[Dict]) -> Dict[str, List[Dict]]:
    """Derive quick-win / niche-lever / coverage-gap buckets deterministically."""
    quick_win: List[Dict] = []
    niche_lever: List[Dict] = []
    coverage_gap: List[Dict] = []
    for k in keywords:
        opp = int(k.get("opportunity", 0))
        comp = int(k.get("competition", 0))
        rel = int(k.get("relevance", 0))
        if opp >= _QUICK_WIN_OPP_MIN and comp <= _QUICK_WIN_COMP_MAX:
            quick_win.append(k)
        if comp <= _NICHE_LEVER_COMP_MAX and rel >= _NICHE_LEVER_REL_MIN:
            niche_lever.append(k)
        if k.get("is_gap"):
            coverage_gap.append(k)
    return {
        "quick_win": quick_win[:_OPPORTUNITY_BUCKET_LIMIT],
        "niche_lever": niche_lever[:_OPPORTUNITY_BUCKET_LIMIT],
        "coverage_gap": coverage_gap[:_OPPORTUNITY_BUCKET_LIMIT],
    }


def _listing_slot_lines(s2_output: Optional[Dict], h2_output: Optional[Dict]) -> List[str]:
    """Render the S2 listing (1 recommended + 2 alternatives) per Apple slot."""
    if not s2_output or not s2_output.get("slots"):
        return [
            "_Listing recommendation pending — run the S2 Listing Strategist "
            "(Sonnet) subagent to produce the per-slot 1 + 2 recommendation._"
        ]
    lines: List[str] = []
    for slot in s2_output.get("slots", []):
        name = slot.get("slot", "?")
        rec = slot.get("recommended") or {}
        rec_text = _md_escape(rec.get("text", ""))
        rec_count = rec.get("char_count", len(rec.get("text", "")))
        lines.append(f"- **{name}** (recommended): `{rec_text}` ({rec_count} chars)")
        alts = slot.get("alternatives") or []
        for i, alt in enumerate(alts[:2], start=1):
            alt_text = _md_escape(alt.get("text", ""))
            alt_count = alt.get("char_count", len(alt.get("text", "")))
            lines.append(f"  - alt {i}: `{alt_text}` ({alt_count} chars)")
    if h2_output:
        status = h2_output.get("status", "—")
        note = _md_escape(h2_output.get("note", ""))
        lines.append(f"- **H2 cross-check:** {status} — {note}")
    return lines


def build_report(
    config: Dict,
    competitors: List[Dict],
    keywords: List[Dict],
    *,
    now: datetime.datetime,
    source_status: Optional[Dict[str, str]] = None,
    reddit_threads: Optional[List[Dict]] = None,
    # --- slice 03 LLM phase (all optional; absent -> deterministic fallback) ---
    condensed_profiles: Optional[List[Dict]] = None,
    s1_output: Optional[Dict] = None,
    s2_output: Optional[Dict] = None,
    h2_output: Optional[Dict] = None,
) -> str:
    """Assemble the 8-section ``report.md`` body as a string."""
    n_comp = len(competitors)
    niche = [c for c in competitors if c.get("discovery") == "niche_similar"]
    primary = [k for k in keywords if k.get("split") == "primary-candidate"]
    longtail = [k for k in keywords if k.get("split") == "long-tail-candidate"]
    gaps = [k for k in keywords if k.get("is_gap")]
    top_kw = ", ".join(k["term"] for k in keywords[:8]) or "—"
    generated = now.strftime("%Y-%m-%d %H:%M:%S")
    source_status = source_status or {}
    reddit_threads = reddit_threads or []
    own_app_id = (config.get("own_app_id") or "").strip()
    modus_a = bool(own_app_id)

    lines: List[str] = []
    lines.append(f"# ASO Research — {config['app_name']}")
    lines.append("")
    lines.append(f"_{_GENERATED_LABEL}: {generated}_")
    lines.append("")

    # === 1. Executive Summary ===
    lines.append("## 1. Executive Summary")
    lines.append("")
    lines.append(
        f"Discovered **{n_comp}** Apple competitor(s) via the iTunes Search API, "
        f"enriched with the Apple **subtitle** (Playwright) and a **similar-apps** "
        f"hop that surfaced **{len(niche)}** niche competitor(s). Keywords were "
        f"extracted with a YAKE + TF-IDF engine (position-weighted) and scored "
        f"with the Competition/Relevance proxy — **not** real search volume. The "
        f"LLM interprets the token-budget-gated, condensed result only."
    )
    lines.append("")
    lines.append(f"- **Category:** {config.get('category', 'other')}")
    lines.append(f"- **Country / language:** {config['country']} / {config['language']}")
    if modus_a:
        lines.append(
            f"- **Mode:** A (post-launch) — own app `{own_app_id}` carried as a "
            f"reference entry and self-audited against the competitors."
        )
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
    if s1_output and s1_output.get("dominant_themes"):
        themes = ", ".join(_md_escape(t) for t in s1_output["dominant_themes"][:5])
        lines.append(f"- **Dominant themes (S1):** {themes}")
    lines.append("")

    # === 2. Competitive Landscape ===
    lines.append("## 2. Competitive Landscape")
    lines.append("")
    if not competitors:
        lines.append("_No competitors discovered for this seed._")
    else:
        header = _row(
            ["Title", "Developer", "Category", "Rating", "# Ratings", "Price", "Source"]
        )
        sep = _row(["---"] * 7)
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

    # === 3. Positioning Map ===
    lines.append("## 3. Positioning Map")
    lines.append("")
    if s1_output:
        for key, label in (
            ("niches", "Niches"),
            ("dominant_themes", "Dominant themes"),
            ("leader_positioning", "Leader positioning patterns"),
            ("audiences", "Audiences"),
        ):
            values = s1_output.get(key) or []
            if values:
                joined = "; ".join(_md_escape(v) for v in values[:8])
                lines.append(f"- **{label}:** {joined}")
        if reddit_threads:
            lines.append("")
            lines.append("**Qualitative grounding (Reddit):**")
            for t in reddit_threads[:6]:
                sub = t.get("subreddit") or "—"
                lines.append(f"  - r/{_md_escape(sub)} — {_md_escape(t.get('title', ''))}")
    else:
        # Deterministic fallback: position competitors by category cluster.
        lines.append(
            "_Full LLM positioning analysis pending (run the S1 Niche & "
            "Positioning Analyst, Sonnet). Deterministic category clustering "
            "below as a placeholder read._"
        )
        lines.append("")
        clusters: Dict[str, List[str]] = {}
        for c in competitors:
            cat = str(c.get("category", "other"))
            clusters.setdefault(cat, []).append(c.get("title", ""))
        for cat in sorted(clusters):
            titles = ", ".join(_md_escape(t) for t in clusters[cat][:6])
            lines.append(f"- **{cat}:** {titles}")
    lines.append("")

    # === 4. Keyword Report ===
    lines.append("## 4. Keyword Report")
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
        sep = _row(["---"] * 7)
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
            lines.append(
                f"**Coverage gaps** (competitors own in Title, seed lacks): {gap_terms}"
            )
            lines.append("")

    # === 5. Opportunities ===
    lines.append("## 5. Opportunities")
    lines.append("")
    buckets = _opportunity_buckets(keywords)
    lines.append(
        f"- **Quick wins** (Opportunity ≥ {_QUICK_WIN_OPP_MIN}, Competition ≤ "
        f"{_QUICK_WIN_COMP_MAX}): "
        + (", ".join(_md_escape(k["term"]) for k in buckets["quick_win"]) or "—")
    )
    lines.append(
        f"- **Niche levers** (Competition ≤ {_NICHE_LEVER_COMP_MAX}, Relevance ≥ "
        f"{_NICHE_LEVER_REL_MIN}): "
        + (", ".join(_md_escape(k["term"]) for k in buckets["niche_lever"]) or "—")
    )
    lines.append(
        "- **Coverage gaps** (competitors own in Title, seed lacks): "
        + (", ".join(_md_escape(k["term"]) for k in buckets["coverage_gap"]) or "—")
    )
    if s1_output and s1_output.get("missing_themes"):
        missing = "; ".join(_md_escape(t) for t in s1_output["missing_themes"][:8])
        lines.append(f"- **Missing themes (S1):** {missing}")
    lines.append("")

    # === 6. Risks / Threats ===
    lines.append("## 6. Risks / Threats")
    lines.append("")
    if s1_output and s1_output.get("threats"):
        for t in s1_output["threats"][:10]:
            lines.append(f"- {_md_escape(t)}")
    else:
        top_comp = sorted(keywords, key=lambda k: -int(k.get("competition", 0)))[:8]
        lines.append(
            "_Full LLM threat read pending (run S1). Highest-competition terms "
            "below as a deterministic threat proxy._"
        )
        lines.append("")
        for k in top_comp:
            lines.append(
                f"- **{_md_escape(k.get('term', ''))}** — competition signal "
                f"{k.get('competition', 0)}"
            )
    lines.append("")

    # === 7. Listing Recommendation ===
    lines.append("## 7. Listing Recommendation (Apple)")
    lines.append("")
    lines.append(
        "1 recommended + 2 alternatives per Apple slot (Title 30 / Subtitle 30 "
        "/ hidden Keyword Field 100), validated by the H2 cross-check."
    )
    lines.append("")
    lines.extend(_listing_slot_lines(s2_output, h2_output))
    lines.append("")

    # Modus A self-audit block (no separate code path — present iff own app).
    if modus_a:
        lines.append("### Self-audit (Modus A)")
        lines.append("")
        if s1_output and s1_output.get("own_app_audit"):
            audit = s1_output["own_app_audit"]
            if isinstance(audit, list):
                for item in audit:
                    lines.append(f"- {_md_escape(item)}")
            else:
                lines.append(f"- {_md_escape(audit)}")
        elif s2_output and s2_output.get("own_app_audit"):
            audit = s2_output["own_app_audit"]
            if isinstance(audit, list):
                for item in audit:
                    lines.append(f"- {_md_escape(item)}")
            else:
                lines.append(f"- {_md_escape(audit)}")
        else:
            lines.append(
                f"_Own app `{own_app_id}` carried as a reference entry; run S1/S2 "
                f"with the own-app context to populate the self-audit comparison._"
            )
        lines.append("")

    # === 8. Methodology ===
    lines.append("## 8. Methodology")
    lines.append("")
    ran, unavailable = _source_split(source_status)
    lines.append(
        "Apple **Core + Slots** metadata collected (subtitle via Playwright, "
        "description from the iTunes API, keyword_hints inferred by inversion — "
        "never the hidden 100-char field). Keyword extraction: YAKE phrases + "
        "TF-IDF with position weighting (Title ×5 · Subtitle ×3 · Description ×1) "
        "+ Apple Search-Suggest enrichment; DE+EN stopwords, generics filtered, "
        "light morphology grouping."
    )
    lines.append("")
    lines.append("**Honesty — what is a proxy vs what is real:**")
    lines.append(
        "- Competition / Relevance / Opportunity are **deterministic proxy "
        "signals**, explicitly **not real search volume or difficulty** — they "
        "are labelled \"signal\" throughout. The only free *real-search* signal "
        "is Apple Search-Suggest autocomplete (a +15 Relevance boost)."
    )
    lines.append(
        "- Keyword counts come from the collected competitor corpus, not from a "
        "proprietary search-volume panel."
    )
    lines.append("")
    lines.append("**Sources that ran:** " + (", ".join(ran) if ran else "iTunes Search API"))
    if unavailable:
        lines.append(
            "**Sources unavailable** (never-blocking — pipeline continued): "
            + ", ".join(unavailable)
        )
    lines.append("")
    lines.append(
        "**LLM phase (Claude-native, no paid API keys):** the deterministic "
        "spine prepares a token-budget-gated, condensed representation (~70k "
        "token cap, chars/4 estimate); the H1 (Haiku) Metadata-Condenser, S1 "
        "(Sonnet) Niche & Positioning Analyst, S2 (Sonnet) Listing Strategist, "
        "and H2 (Haiku) Cross-Checker interpret it — every subagent call sets "
        "its model explicitly. Politeness: ≤1 req/s/domain + jitter, "
        "exponential backoff on 429/503 (max 3 then skip), robots.txt "
        "respected, **no stealth plugins**. HTTP cache 24h / browser cache 12h "
        "at `~/.cache/aso-research/`."
    )
    lines.append("")
    return "\n".join(lines)


def _source_split(source_status: Dict[str, str]):
    """Partition source_status into (ran, unavailable) for the methodology note."""
    order = (
        "apple_subtitle", "apple_similar", "apple_rss_charts",
        "reddit", "apple_search_suggest",
    )
    ran, unavailable = [], []
    for src in order:
        if src not in source_status:
            continue
        (ran if source_status[src] == "ok" else unavailable).append(src)
    return ran, unavailable
