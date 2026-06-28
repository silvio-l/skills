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
    # --- slice 05 P3 Brand conflicts (optional; absent -> no subsection) ---
    brand_conflicts: Optional[List[Dict]] = None,
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

    # --- Brand Conflicts (slice 05 P3) ---
    if brand_conflicts:
        lines.append("### Brand Conflicts")
        lines.append("")
        lines.append(
            "Keywords matching terms forbidden by the project's brand glossar "
            "(Anti-Vokabular). Each conflict carries the canonical replacement "
            "and four strategies — **none auto-applied**, decisions stay with the "
            "project owner."
        )
        lines.append("")
        header = _row(
            [
                "Keyword", "Forbidden Match", "Replacement",
                "Opportunity", "Relevance", "Strategies",
            ]
        )
        sep = _row(["---"] * 6)
        lines.append(header)
        lines.append(sep)
        for c in brand_conflicts:
            strat_list = ", ".join(c.get("strategies", []))
            lines.append(
                _row(
                    [
                        _md_escape(c.get("term", "")),
                        _md_escape(c.get("forbidden_match", "")),
                        _md_escape(c.get("replacement", "") or "—"),
                        str(c.get("opportunity", 0)),
                        str(c.get("relevance", 0)),
                        strat_list,
                    ]
                )
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


# ---------------------------------------------------------------------------
# HTML report builder (slice 06 — visual twin of the Markdown report)
# ---------------------------------------------------------------------------

_HTML_SOURCE_ORDER = (
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


def _html_esc(text) -> str:
    if text is None:
        return ""
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _html_source_card(key, label, entry):
    """Render one source-health entry as a signal-channel card."""
    if not isinstance(entry, dict):
        status, result_count, reason = str(entry), None, ""
    else:
        status = entry.get("status", "?")
        result_count = entry.get("result_count")
        reason = _html_esc(entry.get("reason", ""))

    if status == "ok" and result_count == 0:
        cls, read = "empty", "0 Treffer"
    elif status == "ok" and result_count is not None:
        cls, read = "ok", f"{result_count} Treffer"
    elif status == "ok":
        cls, read = "ok", "aktiv"
    else:
        cls, read = "down", "nicht verfügbar"

    note = f'<span class="channel__note">{reason}</span>' if reason else ""
    return (
        f'<div class="channel channel--{cls}">'
        f'<span class="channel__name">{_html_esc(label)}</span>'
        f'<span class="channel__read">{read}</span>{note}'
        f'</div>'
    )


def _meter_band(score, direction):
    """Traffic-light band for a meter value (Astro semantics).

    ``direction`` ``"up"`` = high is good (green high → red low; relevance,
    opportunity); ``"down"`` = high is bad (red high → green low; competition,
    mirroring Astro's Popularity vs Difficulty colouring).
    """
    s = min(max(int(score), 0), 100)
    if direction == "down":
        return "bad" if s >= 66 else "mid" if s >= 33 else "good"
    return "good" if s >= 66 else "mid" if s >= 33 else "bad"


def _html_meter_cell(score, metric):
    """Render a score cell as a traffic-light bar meter (track + fill + number).

    ``metric`` is ``"comp"`` (high = bad), ``"rel"`` or ``"opp"`` (high = good).
    The ``width`` is a data-driven value, so it stays inline; the colour is a
    value-derived class.
    """
    pct = min(max(int(score), 0), 100)
    band = _meter_band(pct, "down" if metric == "comp" else "up")
    return (
        f'<td class="num"><div class="meter">'
        f'<span class="bar bar--{band}"><span class="bar__fill" style="width:{pct}%"></span></span>'
        f'<span class="bar__num">{pct}</span>'
        f'</div></td>'
    )


_SPLIT_LABELS_DE = {
    "primary-candidate": "Primär",
    "long-tail-candidate": "Long-Tail",
}


def _html_tag(on, label):
    cls = "tag tag--on" if on else "tag"
    return f'<span class="{cls}">{label}</span>' if on else '<span class="sub">—</span>'


def _html_keyword_table(keywords, *, include_platform=False):
    """Render the keyword table with signal meters per metric."""
    rows = []
    for k in keywords[:_KEYWORD_REPORT_LIMIT]:
        split_key = k.get("split", "")
        split_label = _SPLIT_LABELS_DE.get(split_key, split_key.replace("-candidate", ""))
        cells = [
            f'<td class="table__name">{_html_esc(k.get("term", ""))}</td>',
            _html_meter_cell(k.get("competition", 0), "comp"),
            _html_meter_cell(k.get("relevance", 0), "rel"),
            _html_meter_cell(k.get("opportunity", 0), "opp"),
            f'<td><span class="split">{_html_esc(split_label)}</span></td>',
            f'<td>{_html_tag(k.get("is_gap"), "Lücke")}</td>',
            f'<td>{_html_tag(k.get("suggest"), "Suggest")}</td>',
        ]
        if include_platform:
            cells.insert(1, f'<td><span class="split">{_html_esc(k.get("platform", "apple"))}</span></td>')
        rows.append(f"<tr>{''.join(cells)}</tr>")

    header_cells = [
        "<th>Keyword</th>",
        *(["<th>Plattform</th>"] if include_platform else []),
        "<th>Wettbewerb</th>",
        "<th>Relevanz</th>",
        "<th>Chance</th>",
        "<th>Klasse</th>",
        "<th>Gap</th>",
        "<th>Suggest</th>",
    ]
    colspan = 7 + (1 if include_platform else 0)
    body = "".join(rows) if rows else f'<tr><td colspan="{colspan}" class="empty">Keine Keywords bewertet.</td></tr>'
    return (
        f'<table class="table table--kw">'
        f'<thead><tr>{"".join(header_cells)}</tr></thead>'
        f'<tbody>{body}</tbody></table>'
    )


def _html_bucket_card(title, keywords, kind):
    """Render an opportunity-bucket card (kind: win | niche | gap)."""
    if keywords:
        terms = ", ".join(_html_esc(k["term"]) for k in keywords)
        cls = "bucket__terms"
    else:
        terms = "keine"
        cls = "bucket__terms is-empty"
    return (
        f'<div class="bucket bucket--{kind}">'
        f'<p class="bucket__title">{_html_esc(title)}</p>'
        f'<p class="{cls}">{terms}</p>'
        f'</div>'
    )


def _html_brand_conflict_row(c):
    strat_list = _html_esc(", ".join(c.get("strategies", [])))
    return (
        f"<tr>"
        f'<td class="table__name">{_html_esc(c.get("term", ""))}</td>'
        f'<td><span class="pill">verboten</span> {_html_esc(c.get("forbidden_match", ""))}</td>'
        f'<td>{_html_esc(c.get("replacement", "") or "—")}</td>'
        f'<td class="num">{c.get("opportunity", 0)}</td>'
        f'<td class="num">{c.get("relevance", 0)}</td>'
        f'<td class="sub">{strat_list}</td>'
        f"</tr>"
    )


def _html_listing_slots(s2_output, h2_output, *, store_label="Apple"):
    """Render S2 listing proposals (1 recommended + 2 alternatives per slot)."""
    if not s2_output or not s2_output.get("slots"):
        return (
            f'<p class="pending">{_html_esc(store_label)}-Listing-Empfehlung ausstehend '
            f'— S2 Listing-Strategen (Sonnet) ausführen.</p>'
        )
    parts = []
    for slot in s2_output.get("slots", []):
        name = _html_esc(slot.get("slot", "?"))
        rec = slot.get("recommended") or {}
        rec_text = _html_esc(rec.get("text", ""))
        rec_count = rec.get("char_count", len(rec.get("text", "")))
        parts.append(
            f'<div class="slot">'
            f'<span class="slot__name">{name}</span>'
            f'<p class="slot__rec"><code>{rec_text}</code>'
            f'<span class="count">{rec_count} Z.</span></p>'
        )
        for i, alt in enumerate((slot.get("alternatives") or [])[:2], start=1):
            alt_text = _html_esc(alt.get("text", ""))
            alt_count = alt.get("char_count", len(alt.get("text", "")))
            parts.append(
                f'<span class="slot__alt">Alt {i}: <code>{alt_text}</code> '
                f'<span class="count">{alt_count} Z.</span></span>'
            )
        parts.append("</div>")
    if h2_output:
        status = _html_esc(str(h2_output.get("status", "—")))
        note = _html_esc(h2_output.get("note", ""))
        parts.append(
            f'<div class="crosscheck"><strong>H2-Cross-Check ({_html_esc(store_label)}):</strong> '
            f'{status} — {note}</div>'
        )
    return "\n".join(parts)


_HTML_CSS = r"""
:root{
  --ink:#1D1D1F;--ink-soft:#3A3A3E;--mute:#6E6E73;
  --bg:#F2F2F5;--card:#FFFFFF;--field:#F5F5F7;--line:#E6E6EA;--line-2:#D7D7DC;
  --indigo:#5B5BD6;--indigo-ink:#4646C0;--indigo-tint:#EDEDFB;
  --orange:#F59E0B;--orange-ink:#B4730A;--orange-tint:#FEF1DC;
  --good:#1FA971;--good-tint:#E4F5EC;
  --mid:#E0922F;--mid-tint:#FBEFDE;
  --bad:#E0544C;--bad-tint:#FBE7E5;
  --shadow:0 1px 2px rgba(20,20,30,.04),0 4px 16px rgba(20,20,40,.05);
  --mono:"SF Mono","JetBrains Mono",ui-monospace,Menlo,Consolas,monospace;
  --sans:-apple-system,BlinkMacSystemFont,system-ui,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
}
*{box-sizing:border-box}
body{margin:0;font-family:var(--sans);color:var(--ink);background:var(--bg);line-height:1.55;-webkit-font-smoothing:antialiased}
.sheet{max-width:1080px;margin:0 auto;padding:32px 22px 72px}
a{color:var(--indigo)}
.num,.kpi__value,.bar__num,.count{font-variant-numeric:tabular-nums}
.eyebrow{font-size:.7rem;font-weight:700;letter-spacing:.04em;text-transform:uppercase;color:var(--indigo)}

/* --- masthead: the app's toolbar identity --- */
.masthead{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:26px 28px;display:flex;flex-direction:column;gap:8px}
.masthead__eyebrow{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
.masthead__title{font-size:2rem;font-weight:700;letter-spacing:-.03em;line-height:1.1;margin:2px 0 0}
.masthead__meta{font-size:.8rem;color:var(--mute);display:flex;flex-wrap:wrap;gap:5px 16px;margin-top:6px}
.masthead__meta span::before{content:"";display:inline-block;width:4px;height:4px;border-radius:50%;background:var(--line-2);margin-right:8px;vertical-align:middle}
.pill-stat{display:inline-flex;align-items:center;gap:6px;background:var(--orange-tint);color:var(--orange-ink);font-size:.78rem;font-weight:600;padding:5px 12px;border-radius:999px}
.pill-stat b{font-variant-numeric:tabular-nums}
.badge{display:inline-block;font-size:.7rem;font-weight:600;padding:4px 11px;border-radius:999px;background:var(--indigo-tint);color:var(--indigo-ink)}
.chip{display:inline-block;font-size:.72rem;font-weight:500;padding:4px 10px;border-radius:999px;background:var(--field);color:var(--ink-soft);border:1px solid var(--line)}
.caveat{margin-top:12px;padding:10px 14px;background:var(--mid-tint);border:1px solid #EBC892;border-radius:10px;color:#7A4E12;font-size:.82rem}

/* --- sections: clean white panels --- */
.section{background:var(--card);border:1px solid var(--line);border-radius:16px;box-shadow:var(--shadow);padding:24px 26px;margin-top:18px}
.section__head{display:flex;align-items:center;gap:12px;margin-bottom:18px}
.section__title{font-size:1.2rem;font-weight:650;letter-spacing:-.015em;margin:0}
.section h3{font-size:.95rem;font-weight:650;margin:22px 0 10px;color:var(--ink)}
.section__intro{font-size:.85rem;color:var(--mute);max-width:78ch;margin:0 0 16px}

/* --- signal channels (source health) --- */
.channels{display:grid;grid-template-columns:repeat(auto-fill,minmax(168px,1fr));gap:10px}
.channel{background:var(--field);border:1px solid var(--line);border-radius:12px;padding:12px 14px;display:flex;flex-direction:column;gap:5px}
.channel--down{background:var(--mid-tint);border-color:#EBC892}
.channel__name{font-size:.76rem;font-weight:600;color:var(--ink-soft)}
.channel__read{font-size:.84rem;font-weight:700;display:flex;align-items:center;gap:6px}
.channel__read::before{content:"";width:7px;height:7px;border-radius:50%;background:var(--line-2);flex:none}
.channel--ok .channel__read{color:var(--good)}.channel--ok .channel__read::before{background:var(--good)}
.channel--empty .channel__read{color:var(--mute)}
.channel--down .channel__read{color:var(--mid)}.channel--down .channel__read::before{background:var(--mid)}
.channel__note{font-size:.68rem;color:var(--mute);word-break:break-word}
.provenance{font-size:.8rem;color:var(--mute);margin-top:14px;line-height:1.7}
.provenance strong{color:var(--ink-soft)}

/* --- KPI readout --- */
.kpis{display:grid;grid-template-columns:repeat(auto-fit,minmax(98px,1fr));gap:10px}
.kpi{background:var(--field);border:1px solid var(--line);border-radius:12px;padding:13px 15px}
.kpi__label{display:block;font-size:.68rem;font-weight:600;letter-spacing:.02em;text-transform:uppercase;color:var(--mute);margin-bottom:3px}
.kpi__value{font-size:1.55rem;font-weight:700;letter-spacing:-.02em}
.lead{font-size:.88rem;margin:16px 0 0}
.lead strong{font-weight:650}

/* --- data tables --- */
.table{width:100%;border-collapse:collapse;font-size:.85rem}
.table th{text-align:left;padding:8px 12px;border-bottom:1px solid var(--line-2);font-size:.7rem;font-weight:600;letter-spacing:.02em;text-transform:uppercase;color:var(--mute);white-space:nowrap}
.table td{padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:middle}
.table tbody tr:last-child td{border-bottom:0}
.table tbody tr:hover{background:var(--field)}
.table .num{text-align:right}
.table__name{font-weight:600}
.sub{color:var(--mute);font-weight:400}

/* --- traffic-light bar meters (the Astro signature) --- */
.meter{display:flex;align-items:center;gap:9px;min-width:124px}
.bar{position:relative;flex:1;height:7px;background:var(--line);border-radius:99px;overflow:hidden}
.bar__fill{position:absolute;inset:0 auto 0 0;height:100%;border-radius:99px}
.bar--good .bar__fill{background:var(--good)}
.bar--mid .bar__fill{background:var(--mid)}
.bar--bad .bar__fill{background:var(--bad)}
.bar__num{font-size:.8rem;font-weight:600;width:2.2ch;text-align:right;color:var(--ink-soft)}
.tag{display:inline-block;font-size:.68rem;font-weight:600;padding:2px 8px;border-radius:999px;background:var(--field);color:var(--mute);border:1px solid var(--line)}
.tag--on{border-color:transparent;color:var(--indigo-ink);background:var(--indigo-tint)}
.split{font-size:.78rem;color:var(--ink-soft)}

/* --- opportunity buckets --- */
.buckets{display:grid;grid-template-columns:repeat(auto-fit,minmax(244px,1fr));gap:12px}
.bucket{border:1px solid var(--line);border-radius:12px;padding:16px 18px;background:var(--field)}
.bucket--win{background:var(--good-tint);border-color:#BBE6CE}
.bucket--niche{background:var(--indigo-tint);border-color:#D5D5F4}
.bucket--gap{background:var(--mid-tint);border-color:#EBC892}
.bucket__title{font-size:.72rem;font-weight:700;letter-spacing:.01em;text-transform:uppercase;margin:0 0 8px;color:var(--ink-soft)}
.bucket__terms{font-size:.86rem;margin:0;color:var(--ink)}
.bucket__terms.is-empty{color:var(--mute)}

/* --- positioning / generic lists --- */
.facts{list-style:none;padding:0;margin:0}
.facts li{font-size:.88rem;padding:8px 0;border-bottom:1px solid var(--line)}
.facts li:last-child{border-bottom:0}
.facts b{font-weight:650}
.quotes{list-style:none;padding:0;margin:8px 0 0}
.quotes li{font-size:.8rem;color:var(--mute);padding:3px 0}

/* --- brand conflicts --- */
.brand{border:1px solid #EFC4C0;background:var(--bad-tint);border-radius:12px;padding:18px 20px;margin-top:18px}
.brand__title{font-size:1rem;font-weight:650;color:#B23B33;margin:0 0 8px}
.brand__note{font-size:.82rem;color:#7C342D;margin:0 0 14px;max-width:78ch}
.table--brand th{border-bottom-color:#EFC4C0}
.table--brand td{border-bottom-color:#F0D4D1}
.pill{display:inline-block;font-size:.66rem;font-weight:700;letter-spacing:.02em;text-transform:uppercase;padding:2px 8px;border-radius:999px;background:var(--bad);color:#fff}

/* --- listing recommendations --- */
.listing{margin-bottom:18px}
.slot{padding:12px 0;border-bottom:1px solid var(--line)}
.slot:last-child{border-bottom:0}
.slot__name{font-size:.7rem;font-weight:700;letter-spacing:.02em;text-transform:uppercase;color:var(--indigo-ink)}
.slot__rec{font-size:.9rem;margin:5px 0 0}
code{font-family:var(--mono);font-size:.82rem;background:var(--field);border:1px solid var(--line);padding:2px 7px;border-radius:6px}
.count{font-size:.74rem;color:var(--mute);margin-left:6px}
.slot__alt{display:block;font-size:.82rem;color:var(--mute);margin:5px 0 0 16px}
.crosscheck{font-size:.78rem;margin-top:12px;padding:9px 13px;background:var(--good-tint);border:1px solid #BBE6CE;border-radius:10px;color:#13694A}
.pending{color:var(--mute);font-size:.85rem}

/* --- methodology + honesty --- */
.honesty{border:1px solid var(--indigo-tint);background:var(--indigo-tint);border-radius:12px;padding:16px 20px;margin-top:14px}
.honesty__title{font-size:.74rem;font-weight:700;letter-spacing:.01em;text-transform:uppercase;color:var(--indigo-ink);margin:0 0 10px}
.honesty ul{margin:0;padding-left:18px}
.honesty li{font-size:.83rem;margin:7px 0}
.meth-note{font-size:.84rem;color:var(--ink-soft);max-width:80ch;margin:0 0 12px}

/* --- glossary --- */
.glossary{display:grid;grid-template-columns:repeat(auto-fit,minmax(288px,1fr));gap:10px;margin:0}
.glossary>div{background:var(--field);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.glossary dt{font-size:.84rem;font-weight:700;color:var(--indigo-ink);margin:0 0 5px}
.glossary dd{font-size:.8rem;color:var(--ink-soft);margin:0;line-height:1.55}

.empty{color:var(--mute);font-size:.86rem}

@media(max-width:640px){
  .sheet{padding:18px 12px 48px}
  .masthead,.section{padding:18px 18px;border-radius:14px}
  .masthead__title{font-size:1.55rem}
  .channels,.kpis,.glossary{grid-template-columns:1fr 1fr}
  .buckets{grid-template-columns:1fr}
  .table{font-size:.8rem}
  .table th,.table td{padding:7px 8px}
}
@media(max-width:430px){.channels,.kpis,.glossary{grid-template-columns:1fr}}
@media(prefers-reduced-motion:no-preference){.bar__fill{transition:width .5s cubic-bezier(.2,.7,.2,1)}}
@media print{body{background:#fff}.section,.masthead{box-shadow:none;break-inside:avoid}}
""".strip()


def build_report_html(
    config: Dict,
    competitors: List[Dict],
    keywords: List[Dict],
    *,
    now: datetime.datetime,
    source_status: Optional[Dict[str, str]] = None,
    reddit_threads: Optional[List[Dict]] = None,
    condensed_profiles: Optional[List[Dict]] = None,
    s1_output: Optional[Dict] = None,
    s2_output: Optional[Dict] = None,
    h2_output: Optional[Dict] = None,
    s2_play_output: Optional[Dict] = None,
    h2_play_output: Optional[Dict] = None,
    ms_entries: Optional[List[Dict]] = None,
    brand_conflicts: Optional[List[Dict]] = None,
) -> str:
    """Assemble a self-contained, browser-openable HTML twin of ``report.md``."""
    source_status = source_status or {}
    reddit_threads = reddit_threads or []
    ms_entries = ms_entries or []
    brand_conflicts = brand_conflicts or []

    n_comp = len(competitors)
    apple_comps = [c for c in competitors if c.get("platform", "apple") == "apple"]
    play_comps = [c for c in competitors if c.get("platform") == "play"]
    niche = [c for c in competitors if c.get("discovery") == "niche_similar"]
    primary = [k for k in keywords if k.get("split") == "primary-candidate"]
    longtail = [k for k in keywords if k.get("split") == "long-tail-candidate"]
    gaps = [k for k in keywords if k.get("is_gap")]
    top_kw = ", ".join(k["term"] for k in keywords[:8]) or "—"
    generated = now.strftime("%Y-%m-%d %H:%M:%S")
    own_app_id = (config.get("own_app_id") or "").strip()
    modus_a = bool(own_app_id)
    has_play = bool(play_comps) or any(s.startswith("play_") for s in source_status)
    en_without_us = config.get("language", "").lower() == "en" and config.get("country", "").lower() != "us"

    # Partition keywords by platform for grouped tables
    apple_kws = [k for k in keywords if k.get("platform", "apple") == "apple"]
    play_kws = [k for k in keywords if k.get("platform") == "play"]

    parts: List[str] = []
    parts.append("<!DOCTYPE html>")
    parts.append('<html lang="de">')
    parts.append("<head>")
    parts.append(f'<meta charset="utf-8">')
    parts.append(f'<meta name="viewport" content="width=device-width,initial-scale=1">')
    parts.append(f"<title>ASO-Recherche — {_html_esc(config['app_name'])}</title>")
    parts.append(f"<style>{_HTML_CSS}</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append('<div class="sheet">')

    cat = config.get("category", "other")
    lang = config.get("language", "de")
    country = config.get("country", "de")
    seeds = config.get("seed_keywords") or []

    # --- Masthead (Astro-style toolbar identity) ---
    parts.append('<header class="masthead">')
    mode_badge = (
        f'Modus A · nach Launch · {_html_esc(own_app_id)}' if modus_a else "Modus B · Pre-Launch"
    )
    parts.append(
        '<div class="masthead__eyebrow">'
        '<span class="eyebrow">ASO-Recherche</span>'
        f'<span class="badge">{mode_badge}</span>'
        f'<span class="pill-stat">💡 <b>{len(keywords)}</b> Keywords bewertet</span>'
        '</div>'
    )
    parts.append(f'<h1 class="masthead__title">{_html_esc(config["app_name"])}</h1>')
    meta_bits = [
        f"<span>{_html_esc(generated)}</span>",
        f"<span>{_html_esc(country)} / {_html_esc(lang)}</span>",
        f"<span>Kategorie: {_html_esc(cat)}</span>",
    ]
    if seeds:
        meta_bits.append(f"<span>Seeds: {_html_esc(', '.join(seeds))}</span>")
    parts.append('<div class="masthead__meta">' + "".join(meta_bits) + "</div>")
    if en_without_us:
        parts.append(
            '<div class="caveat">Sprache ist EN, Land aber nicht US — die EN-Listing-'
            'Empfehlungen stammen aus einem Nicht-US-Markt-Crawl und sind NICHT als '
            'EN-Markt(US)-Ergebnisse zu lesen.</div>'
        )
    parts.append("</header>")

    def _section(eyebrow, title):
        parts.append('<section class="section">')
        parts.append(
            f'<div class="section__head"><span class="eyebrow">{eyebrow}</span>'
            f'<h2 class="section__title">{title}</h2></div>'
        )

    # --- Quellen-Signal (source health) ---
    _section("Provenienz", "Quellen-Signal")
    parts.append('<div class="channels">')
    for key, label in _HTML_SOURCE_ORDER:
        entry = source_status.get(key)
        if entry is None:
            continue
        parts.append(_html_source_card(key, label, entry))
    parts.append("</div>")
    ran, unavailable = _source_split(source_status)
    prov = f'<div class="provenance"><strong>Aktiv:</strong> {", ".join(ran) if ran else "iTunes Search API"}'
    if unavailable:
        prov += f'<br><strong>Nicht verfügbar</strong> (nie blockierend): {", ".join(unavailable)}'
    parts.append(prov + "</div>")
    parts.append("</section>")

    # --- Überblick (KPI readout) ---
    _section("Überblick", "Zusammenfassung")
    parts.append('<div class="kpis">')
    parts.append(f'<div class="kpi"><span class="kpi__label">Apple</span><span class="kpi__value">{len(apple_comps)}</span></div>')
    if has_play:
        parts.append(f'<div class="kpi"><span class="kpi__label">Play</span><span class="kpi__value">{len(play_comps)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi__label">Nische</span><span class="kpi__value">{len(niche)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi__label">Keywords</span><span class="kpi__value">{len(keywords)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi__label">Primär</span><span class="kpi__value">{len(primary)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi__label">Long-Tail</span><span class="kpi__value">{len(longtail)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi__label">Gaps</span><span class="kpi__value">{len(gaps)}</span></div>')
    parts.append("</div>")
    parts.append(f'<p class="lead"><strong>Top-Keywords:</strong> {_html_esc(top_kw)}</p>')
    if s1_output and s1_output.get("dominant_themes"):
        themes = ", ".join(_html_esc(t) for t in s1_output["dominant_themes"][:5])
        parts.append(f'<p class="lead"><strong>Dominante Themen (S1):</strong> {themes}</p>')
    parts.append("</section>")

    # --- Wettbewerbslandschaft ---
    _section("Markt", "Wettbewerbslandschaft")
    if not competitors:
        parts.append('<p class="empty">Keine Wettbewerber zu diesem Seed gefunden.</p>')
    else:
        rows = []
        for c in competitors:
            rating = c.get("rating_avg")
            rating_str = f"{float(rating):.1f}" if isinstance(rating, (int, float)) else "—"
            disc = c.get("discovery")
            source = {"niche_similar": "Nische", "chart": "Chart"}.get(disc, "Suche")
            sub = c.get("subtitle") or ""
            title = f'<span class="table__name">{_html_esc(c.get("title", ""))}</span>'
            if sub:
                title += f' <span class="sub">— {_html_esc(sub)}</span>'
            rows.append(
                "<tr>"
                f"<td>{title}</td>"
                f'<td class="sub">{_html_esc(c.get("developer", ""))}</td>'
                f'<td class="sub">{_html_esc(str(c.get("category", "")))}</td>'
                f'<td class="num">{rating_str}</td>'
                f'<td class="num">{c.get("rating_count", 0)}</td>'
                f'<td class="sub">{_html_esc(str(c.get("price_model", "")))}</td>'
                f'<td><span class="split">{source}</span></td>'
                "</tr>"
            )
        parts.append(
            '<table class="table table--comp"><thead><tr>'
            '<th>Titel</th><th>Entwickler</th><th>Kategorie</th>'
            '<th>Bewertung</th><th>#&nbsp;Bew.</th><th>Preis</th><th>Quelle</th>'
            f'</tr></thead><tbody>{"".join(rows)}</tbody></table>'
        )
    parts.append("</section>")

    # --- Positionierungsmap ---
    _section("Positionierung", "Positionierungsmap")
    if s1_output:
        items = []
        for key, label in (
            ("niches", "Nischen"),
            ("dominant_themes", "Dominante Themen"),
            ("leader_positioning", "Positionierung der Marktführer"),
            ("audiences", "Zielgruppen"),
        ):
            values = s1_output.get(key) or []
            if values:
                joined = "; ".join(_html_esc(v) for v in values[:8])
                items.append(f"<li><b>{_html_esc(label)}:</b> {joined}</li>")
        if items:
            parts.append('<ul class="facts">' + "".join(items) + "</ul>")
        if reddit_threads:
            parts.append("<h3>Qualitative Untermauerung · Reddit</h3>")
            quotes = "".join(
                f'<li>r/{_html_esc(t.get("subreddit") or "—")} — {_html_esc(t.get("title", ""))}</li>'
                for t in reddit_threads[:6]
            )
            parts.append(f'<ul class="quotes">{quotes}</ul>')
    else:
        parts.append(
            '<p class="section__intro">Vollständige LLM-Positionierungsanalyse ausstehend '
            '(S1 Nischen- &amp; Positionierungs-Analyst, Sonnet). Deterministische '
            'Kategorie-Clusterung als Platzhalter:</p>'
        )
        clusters: Dict[str, List[str]] = {}
        for c in competitors:
            ccat = str(c.get("category", "other"))
            clusters.setdefault(ccat, []).append(c.get("title", ""))
        items = "".join(
            f'<li><b>{_html_esc(ccat)}:</b> {", ".join(_html_esc(t) for t in clusters[ccat][:6])}</li>'
            for ccat in sorted(clusters)
        )
        parts.append(f'<ul class="facts">{items}</ul>')
    if ms_entries and _entry_is_ok(source_status.get("ms")):
        parts.append("<h3>Microsoft Store · Windows-Desktop (qualitativ)</h3>")
        parts.append(
            f'<p class="section__intro">{len(ms_entries)} App(s) auf apps.microsoft.com '
            f'(StoreEdge-API: Bewertungen, Beschreibung, Kategorie). Kontext für die '
            f'Positionierung — fließt NICHT ins Keyword-Scoring ein (kein MS-Slot-Modell).</p>'
        )
        ms_sorted = sorted(ms_entries, key=lambda e: -(e.get("rating_count") or 0))
        ms_rows = []
        for e in ms_sorted[:12]:
            ra = e.get("rating_avg")
            ra_str = f"{float(ra):.1f}" if isinstance(ra, (int, float)) and ra else "—"
            ms_rows.append(
                "<tr>"
                f'<td class="table__name">{_html_esc(e.get("title", ""))}</td>'
                f'<td class="sub">{_html_esc(str(e.get("category", "") or "—"))}</td>'
                f'<td class="num">{ra_str}</td>'
                f'<td class="num">{e.get("rating_count", 0) or 0}</td>'
                "</tr>"
            )
        parts.append(
            '<table class="table"><thead><tr>'
            '<th>Titel</th><th>Kategorie</th><th>Bewertung</th><th>#&nbsp;Bew.</th>'
            f'</tr></thead><tbody>{"".join(ms_rows)}</tbody></table>'
        )
    parts.append("</section>")

    # --- Keyword-Bericht ---
    _section("Signal", "Keyword-Bericht")
    parts.append(
        '<p class="section__intro">Die Werte sind ein deterministisches '
        '<strong>Wettbewerbs-/Relevanz-Signal</strong> — ein Proxy, '
        '<strong>kein</strong> echtes Suchvolumen. Wettbewerb = positionsgewichteter '
        'Slot-Anteil (Apple Titel&times;5 · Untertitel&times;3 · Beschreibung&times;1; '
        'Play Titel&times;5 · Kurz&times;4 · Lang&times;2); Relevanz = Blend aus '
        'Seed-Nähe (40&nbsp;%) und Wettbewerber-Korpus-Zentralität (60&nbsp;%) (+15 Search-Suggest-Bonus); '
        'Chance = Relevanz &times; (100 − Wettbewerb) (+10 Nischen-Bonus). '
        'Balken-Farbe: grün = günstig, rot = ungünstig (Wettbewerb invers).</p>'
    )
    if not keywords:
        parts.append('<p class="empty">Keine Keywords bewertet (leerer Wettbewerber-Korpus).</p>')
    else:
        if has_play and play_kws:
            parts.append("<h3>Apple</h3>")
            parts.append(_html_keyword_table(apple_kws))
            parts.append("<h3>Google Play</h3>")
            parts.append(_html_keyword_table(play_kws))
        else:
            parts.append(_html_keyword_table(keywords))
        if gaps:
            gap_terms = ", ".join(_html_esc(k["term"]) for k in gaps[:15])
            parts.append(
                f'<p class="section__intro" style="margin-top:14px"><strong>Abdeckungslücken</strong> '
                f'(Wettbewerber führen im Titel, Seed nicht): {gap_terms}</p>'
            )

    if brand_conflicts:
        parts.append('<div class="brand">')
        parts.append('<p class="brand__title">⚠ Markenkonflikte</p>')
        parts.append(
            '<p class="brand__note">Keywords, die Begriffe aus dem Anti-Vokabular des '
            'Projekts enthalten. Jeder Konflikt zeigt die kanonische Ersetzung und vier '
            'Strategien — <strong>keine automatisch angewandt</strong>, die Entscheidung '
            'liegt beim Projektinhaber.</p>'
        )
        parts.append(
            '<table class="table table--brand"><thead><tr>'
            '<th>Keyword</th><th>Verbotener Treffer</th><th>Ersetzung</th>'
            '<th>Chance</th><th>Rel.</th><th>Strategien</th>'
            f'</tr></thead><tbody>{"".join(_html_brand_conflict_row(c) for c in brand_conflicts)}</tbody></table>'
        )
        parts.append("</div>")
    parts.append("</section>")

    # --- Chancen ---
    _section("Chancen", "Hebel & Quick Wins")
    buckets = _opportunity_buckets(keywords)
    parts.append('<div class="buckets">')
    parts.append(_html_bucket_card(
        f"Schnelle Gewinne · Chance ≥ {_QUICK_WIN_OPP_MIN}, Wettb. ≤ {_QUICK_WIN_COMP_MAX}",
        buckets["quick_win"], "win"))
    parts.append(_html_bucket_card(
        f"Nischen-Hebel · Wettb. ≤ {_NICHE_LEVER_COMP_MAX}, Rel. ≥ {_NICHE_LEVER_REL_MIN}",
        buckets["niche_lever"], "niche"))
    parts.append(_html_bucket_card(
        "Abdeckungslücken · Wettbewerber führen im Titel",
        buckets["coverage_gap"], "gap"))
    parts.append("</div>")
    if s1_output and s1_output.get("missing_themes"):
        missing = "; ".join(_html_esc(t) for t in s1_output["missing_themes"][:8])
        parts.append(f'<p class="lead"><strong>Fehlende Themen (S1):</strong> {missing}</p>')
    parts.append("</section>")

    # --- Risiken / Bedrohungen ---
    _section("Risiko", "Risiken & Bedrohungen")
    if s1_output and s1_output.get("threats"):
        lis = "".join(f"<li>{_html_esc(t)}</li>" for t in s1_output["threats"][:10])
        parts.append(f'<ul class="facts">{lis}</ul>')
    else:
        top_comp = sorted(keywords, key=lambda k: -int(k.get("competition", 0)))[:8]
        parts.append(
            '<p class="section__intro">Vollständige LLM-Bedrohungsanalyse ausstehend (S1). '
            'Begriffe mit höchstem Wettbewerb als deterministischer Proxy:</p>'
        )
        lis = "".join(
            f'<li><b>{_html_esc(k.get("term", ""))}</b> — Wettbewerbssignal '
            f'<span class="num">{k.get("competition", 0)}</span></li>'
            for k in top_comp
        )
        parts.append(f'<ul class="facts">{lis}</ul>')
    parts.append("</section>")

    # --- Listing-Empfehlung ---
    _section("Listing", "Listing-Empfehlung")
    parts.append('<div class="listing">')
    parts.append("<h3>Apple</h3>")
    if en_without_us:
        parts.append(
            '<div class="caveat">Sprache ist EN, Land aber nicht US — die EN-Listing-'
            'Empfehlungen stammen aus einem Nicht-US-Markt-Crawl.</div>'
        )
    parts.append(
        '<p class="section__intro">1 empfohlen + 2 Alternativen pro Apple-Slot '
        '(Titel 30 / Untertitel 30 / Keyword-Feld 100), validiert durch den H2-Cross-Check.</p>'
    )
    parts.append(_html_listing_slots(s2_output, h2_output, store_label="Apple"))
    parts.append("</div>")

    if has_play:
        parts.append('<div class="listing">')
        parts.append("<h3>Google Play</h3>")
        parts.append(
            '<p class="section__intro">1 empfohlen + 2 Alternativen pro Play-Slot '
            '(Titel 30 / Kurz 80 / Lang 4000), optimiert für Plays Ranking-Modell, '
            'validiert durch den H2-Cross-Check.</p>'
        )
        parts.append(_html_listing_slots(s2_play_output, h2_play_output, store_label="Google Play"))
        parts.append("</div>")

    if modus_a:
        parts.append("<h3>Selbstaudit · Modus A</h3>")
        audit = (s1_output or {}).get("own_app_audit") or (s2_output or {}).get("own_app_audit")
        if audit:
            items = audit if isinstance(audit, list) else [audit]
            lis = "".join(f"<li>{_html_esc(i)}</li>" for i in items)
            parts.append(f'<ul class="facts">{lis}</ul>')
        else:
            parts.append(
                f'<p class="pending">Eigene App <code>{_html_esc(own_app_id)}</code> '
                f'als Referenzeintrag geführt; S1/S2 mit Own-App-Kontext ausführen, um den '
                f'Selbstaudit zu befüllen.</p>'
            )
    parts.append("</section>")

    # --- Methodik & Ehrlichkeit ---
    _section("Methode", "Methodik & Ehrlichkeit")
    parts.append(
        '<p class="meth-note">Apple <strong>Core + Slots</strong> gesammelt (Untertitel via '
        'Playwright, Beschreibung aus der iTunes-API, keyword_hints durch Inversion — niemals '
        'das versteckte 100-Zeichen-Feld). Extraktion: YAKE-Phrasen + positionsgewichtetes '
        'TF-IDF (Titel&times;5 · Untertitel&times;3 · Beschreibung&times;1) + Apple-Search-Suggest; '
        'DE+EN-Stopwörter, Generika &amp; reine Zahlen gefiltert, leichte Morphologie-Gruppierung.</p>'
    )
    if has_play:
        parts.append(
            '<p class="meth-note">Google Play <strong>Core + Slots</strong> via google-play-scraper '
            '(Suche, Charts, Similar): Titel + Kurzbeschreibung (80, starker Ranking-Faktor) + '
            'Langbeschreibung (4000, voll indexiert). Tags werden nicht erfasst. Play-Keywords '
            'fließen in DIESELBE Engine mit Play-Gewichtung (Titel&times;5 · Kurz&times;4 · '
            'Lang&times;2); Play-Autocomplete ergänzt das Suggest-Set.</p>'
        )
    if _entry_is_ok(source_status.get("ms")):
        parts.append(
            '<p class="meth-note">Microsoft Store <strong>per Best-Effort</strong> via Playwright '
            '(<code>apps.microsoft.com</code> ist eine SPA → <code>networkidle</code> + '
            '<code>wait_for_selector</code>). Nur der <code>description</code>-Slot — '
            '<strong>kein MS-ASO-Slot-Modell; MS-Daten fließen nie in Extraktion oder Scoring</strong>, '
            'nur als qualitativer Kontext an S1.</p>'
        )
    elif "ms" in source_status:
        parts.append(
            '<p class="meth-note">Microsoft Store war in diesem Durchlauf <strong>nicht '
            'verfügbar</strong> (Best-Effort, nie blockierend). MS ist rein qualitativ und '
            'wäre ohnehin nicht ins Scoring eingeflossen.</p>'
        )
    parts.append('<div class="honesty">')
    parts.append('<p class="honesty__title">Proxy vs. echt — was die Zahlen sind</p>')
    parts.append(
        '<ul>'
        '<li>Wettbewerb / Relevanz / Chance sind <strong>deterministische Proxy-Signale</strong>, '
        'ausdrücklich <strong>kein echtes Suchvolumen und keine echte Difficulty</strong> — '
        'durchgängig als „Signal" bezeichnet. Die einzigen kostenlosen <em>Echtsuche</em>-Signale '
        'sind Apple- &amp; Play-Search-Suggest (ein +15-Relevanz-Bonus).</li>'
        '<li>Keyword-Zahlen stammen aus dem gesammelten Wettbewerber-Korpus, nicht aus einem '
        'proprietären Suchvolumen-Panel.</li>'
        '<li><strong>LLM-Phase (Claude-nativ, keine kostenpflichtigen API-Keys):</strong> das '
        'deterministische Grundgerüst bereitet eine token-budget-begrenzte, kondensierte '
        'Repräsentation vor (~70k-Cap); H1 (Haiku), S1 (Sonnet), S2 (Sonnet), H2 (Haiku) '
        'interpretieren sie — jeder Subagent-Aufruf setzt sein Modell explizit. Höflichkeit: '
        '≤1 Anfrage/s/Domain + Jitter, Backoff bei 429/503, HTTP-Cache 24h / Browser-Cache 12h.</li>'
        '</ul>'
    )
    parts.append("</div>")
    parts.append("</section>")

    # --- Glossar ---
    _section("Begriffe", "Glossar")
    glossary_terms = [
        ("Relevanz",
         "Wie sehr ein Keyword zur Nische gehört. Blend aus (40 %) Nähe zum "
         "Seed-Konzept und (60 %) Zentralität im Wettbewerber-Korpus — also wie "
         "stark die echten Markt-Apps den Begriff nutzen. So stehen oben die "
         "Markt-Keywords, nicht die eigenen Beschreibungs-Füllwörter."),
        ("Chance (Opportunity)",
         "Kombinierter Kennwert aus Relevanz und Wettbewerb. Je relevanter ein "
         "Keyword und je weniger umkämpft, desto höher die Chance. Der wichtigste "
         "Sortierwert für Listing-Entscheidungen."),
        ("Suchvolumen",
         "Im Report bewusst NICHT enthalten — wir nutzen stattdessen einen "
         "Wettbewerbs-/Relevanz-Proxy. Echtes Suchvolumen müsste über Apple "
         "Search Ads oder Drittanbieter (z. B. Sensor Tower) bezogen werden."),
        ("Primärkandidat (Primary)",
         "Keyword mit hoher Relevanz zum Produkt — taucht prominent in Wettbewerber-"
         "Titeln und/oder -Untertiteln auf. Ideale Kandidaten für den eigenen "
         "Titel oder Untertitel."),
        ("Long-Tail-Kandidat",
         "Spezifischere, weniger umkämpfte Keyword-Kombination aus mehreren Wörtern. "
         "Niedrigerer Wettbewerb, dafür auch geringere Sichtbarkeit — gut für "
         "Beschreibungstexte und das Keyword-Feld."),
        ("Qualitativer Kanal",
         "Eine Datenquelle, die bewusst NICHT in das Scoring einfließt, sondern "
         "als Kontext für die LLM-Analyse dient (z. B. Microsoft Store, "
         "Reddit-Threads). Liefert Tiefe, aber keine Zahlen."),
        ("Markenkonflikt (Brand Conflict)",
         "Ein Keyword, das Begriffe aus dem Anti-Vokabular des Projekts enthält — "
         "z. B. Konkurrenzmarken oder unerwünschte Assoziationen. Wird im Report "
         "rot markiert; die Entscheidung über die Verwendung bleibt beim "
         "Projektinhaber."),
        ("Anti-Vokabular",
         "Eine projektspezifische Liste verbotener Begriffe (Markennamen, "
         "unerwünschte Assoziationen), die in Keywords und Listings vermieden "
         "werden sollen."),
        ("Seed-Keywords",
         "Die vom Nutzer vorgegebenen Startbegriffe, mit denen die Recherche "
         "beginnt. Ausgehend davon werden Wettbewerber gefunden und der "
         "Keyword-Korpus aufgebaut."),
    ]
    parts.append('<dl class="glossary">')
    for term, definition in glossary_terms:
        parts.append(f'<div><dt>{_html_esc(term)}</dt><dd>{_html_esc(definition)}</dd></div>')
    parts.append("</dl>")
    parts.append("</section>")

    parts.append("</div>")  # .sheet
    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)
