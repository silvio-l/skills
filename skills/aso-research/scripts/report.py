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


def _entry_is_ok(entry):
    """Test whether a source_status entry is ok (handles both dict and legacy str)."""
    if isinstance(entry, dict):
        return entry.get("status") == "ok"
    return entry == "ok"


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


def _listing_slot_lines(s2_output: Optional[Dict], h2_output: Optional[Dict], *, store_label: str = "Apple") -> List[str]:
    """Render the S2 listing (1 recommended + 2 alternatives) per slot.

    Works for either store — the slot names + char limits come from the S2
    output itself (validated upstream by :mod:`crosscheck`).
    """
    if not s2_output or not s2_output.get("slots"):
        return [
            f"_{store_label} listing recommendation pending — run the S2 Listing "
            f"Strategist (Sonnet) subagent to produce the per-slot 1 + 2 "
            f"recommendation for the {store_label.lower()} slot model._"
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
        lines.append(f"- **H2 cross-check ({store_label}):** {status} — {note}")
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
    # --- slice 04 Play listing (optional; absent -> Apple-only report) ---
    s2_play_output: Optional[Dict] = None,
    h2_play_output: Optional[Dict] = None,
    # --- slice 05 MS best-effort (optional; qualitative-only, never scored) ---
    ms_entries: Optional[List[Dict]] = None,
) -> str:
    """Assemble the 8-section ``report.md`` body as a string."""
    n_comp = len(competitors)
    apple_comps = [c for c in competitors if c.get("platform", "apple") == "apple"]
    play_comps = [c for c in competitors if c.get("platform") == "play"]
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
    has_play = bool(play_comps) or any(s.startswith("play_") for s in source_status)
    en_without_us = config.get("language", "").lower() == "en" and config.get("country", "").lower() != "us"

    lines: List[str] = []
    lines.append(f"# ASO Research — {config['app_name']}")
    lines.append("")
    lines.append(f"_{_GENERATED_LABEL}: {generated}_")
    lines.append("")

    # === 1. Executive Summary ===
    lines.append("## 1. Executive Summary")
    lines.append("")
    if has_play:
        lines.append(
            f"Discovered **{len(apple_comps)}** Apple and **{len(play_comps)}** Google "
            f"Play competitor(s). Apple via the iTunes Search API (enriched with the "
            f"subtitle via Playwright + a similar-apps hop); Play via "
            f"google-play-scraper (search, charts, similar-apps). The similar-apps "
            f"hop surfaced **{len(niche)}** niche competitor(s). Keywords were "
            f"extracted with a YAKE + TF-IDF engine (position-weighted per platform) "
            f"and scored with the shared Competition/Relevance proxy — **not** real "
            f"search volume. The LLM interprets the token-budget-gated, condensed "
            f"result only."
        )
    else:
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
    if en_without_us:
        lines.append(
            "- :warning: **Language is EN but country is not US** — EN listing "
            "recommendations below are derived from a non-US market crawl and should "
            "NOT be treated as EN-market (US) findings."
        )
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
    # Microsoft Store qualitative signal (slice 05) — best-effort, qualitative
    # only. Surfaced when the MS source ran and returned entries; S1 reads it
    # as additional context, it is never scored (no MS slot model).
    if ms_entries and _entry_is_ok(source_status.get("ms")):
        ms_titles = ", ".join(_md_escape(e.get("title", "")) for e in ms_entries[:8])
        lines.append("")
        lines.append(
            f"**Microsoft Store (qualitative, best-effort):** {len(ms_entries)} app(s) "
            f"observed on apps.microsoft.com — {ms_titles}. This is additional "
            f"qualitative context for positioning only (the MS Store is an SPA, "
            f"collected best-effort); it does NOT enter keyword scoring."
        )
    lines.append("")

    # === 4. Keyword Report ===
    lines.append("## 4. Keyword Report")
    lines.append("")
    lines.append(
        "Scores are a deterministic **Competition/Relevance signal** — a proxy, "
        "**never** search volume. Competition = position-weighted slot share "
        "(Apple: Title ×5 · Subtitle ×3 · Description ×1; Play: Title ×5 · Short "
        "×4 · Long ×2); Relevance = cosine TF-IDF to the seed concept (+15 "
        "Apple/Play Search-Suggest boost); Opportunity = Relevance × (100 − "
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
    lines.append("## 7. Listing Recommendation")
    lines.append("")
    lines.append("### Apple")
    lines.append("")
    if en_without_us:
        lines.append(
            ":warning: **Language is EN but country is not US** — the EN listing "
            "recommendations below are derived from a non-US market crawl and should "
            "NOT be treated as EN-market (US) findings."
        )
        lines.append("")
    lines.append(
        "1 recommended + 2 alternatives per Apple slot (Title 30 / Subtitle 30 "
        "/ hidden Keyword Field 100), validated by the H2 cross-check."
    )
    lines.append("")
    lines.extend(_listing_slot_lines(s2_output, h2_output, store_label="Apple"))
    lines.append("")

    if has_play:
        lines.append("### Google Play")
        lines.append("")
        lines.append(
            "1 recommended + 2 alternatives per Play slot (Title 30 / Short 80 / "
            "Long 4000), optimised for Play's own ranking model (Short is a strong "
            "ranking factor; Long is fully indexed), validated by the H2 cross-check."
        )
        lines.append("")
        lines.extend(_listing_slot_lines(s2_play_output, h2_play_output, store_label="Google Play"))
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
    if has_play:
        lines.append("")
        lines.append(
            "Google Play **Core + Slots** metadata collected via "
            "google-play-scraper (search, charts, similar-apps): Title + "
            "Short Description (80, strong ranking factor) + Long Description "
            "(4000, fully indexed). Play **tags are not collected** (not reliably "
            "extractable). Play keywords flow into the SAME shared scoring engine "
            "with Play's own position weighting (Title ×5 · Short ×4 · Long ×2) "
            "and Play autocomplete enriches the suggest set alongside Apple's."
        )
    # Microsoft Store (slice 05) — best-effort + qualitative-only.
    if _entry_is_ok(source_status.get("ms")):
        lines.append("")
        lines.append(
            "Microsoft Store metadata collected **best-effort** via Playwright "
            "(``apps.microsoft.com`` is a single-page app, so collection uses "
            "``networkidle`` + ``wait_for_selector``). MS carries the ``description`` "
            "slot only — **there is no MS ASO slot model and MS data never enters "
            "keyword extraction or scoring**. It is passed to the S1 Niche & "
            "Positioning Analyst as additional qualitative context."
        )
    elif "ms" in source_status:
        lines.append("")
        lines.append(
            "Microsoft Store was **unavailable** this run (best-effort, never-"
            "blocking — the pipeline completed with Apple + Play results intact). "
            "MS is qualitative-only and would not have entered scoring regardless."
        )
    lines.append("")
    lines.append("**Honesty — what is a proxy vs what is real:**")
    lines.append(
        "- Competition / Relevance / Opportunity are **deterministic proxy "
        "signals**, explicitly **not real search volume or difficulty** — they "
        "are labelled \"signal\" throughout. The only free *real-search* signals "
        "are Apple + Play Search-Suggest autocomplete (a +15 Relevance boost)."
    )
    lines.append(
        "- Keyword counts come from the collected competitor corpus, not from a "
        "proprietary search-volume panel."
    )
    lines.append("")
    lines.append("### Source Health")
    lines.append("")
    lines.append("| Source | Status | Count | Note |")
    lines.append("| --- | --- | --- | --- |")
    _order = (
        ("apple_subtitle", "Apple Subtitle"),
        ("apple_similar", "Apple Similar"),
        ("apple_rss_charts", "Apple RSS Charts"),
        ("reddit", "Reddit"),
        ("apple_search_suggest", "Apple Search-Suggest"),
        ("play_search", "Play Search"),
        ("play_charts", "Play Charts"),
        ("play_similar", "Play Similar"),
        ("play_search_suggest", "Play Search-Suggest"),
        ("ms", "Microsoft Store"),
    )
    for key, label in _order:
        entry = source_status.get(key)
        if entry is None:
            continue
        if isinstance(entry, dict):
            status = entry.get("status", "?")
            count = str(entry.get("result_count", "—"))
            note = ""
            if status == "ok":
                status_display = f"ok ({count})" if entry.get("result_count") is not None else "ok"
            else:
                status_display = "unavailable"
                note = _md_escape(entry.get("reason", ""))
            lines.append(f"| {label} | {status_display} | {count} | {note} |")
        else:
            lines.append(f"| {label} | {entry} | — | |")
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


def _source_split(source_status):
    """Partition source_status into (ran_display, unavailable_display) for the methodology note.

    Each entry is a structured dict: ``{"status":"ok","result_count":N}`` or
    ``{"status":"unavailable","reason":"..."}``.
    """
    order = (
        "apple_subtitle", "apple_similar", "apple_rss_charts",
        "reddit", "apple_search_suggest",
        "play_search", "play_charts", "play_similar", "play_search_suggest",
        "ms",
    )
    ran, unavailable = [], []
    for src in order:
        entry = source_status.get(src)
        if entry is None:
            continue
        if isinstance(entry, dict):
            if entry.get("status") == "ok":
                count = entry.get("result_count")
                label = f"{src} ({count})" if count is not None else src
                ran.append(label)
            else:
                reason = entry.get("reason", "unavailable")
                unavailable.append(f"{src} ({reason})")
        else:
            # Legacy string format
            (ran if entry == "ok" else unavailable).append(src)
    return ran, unavailable
