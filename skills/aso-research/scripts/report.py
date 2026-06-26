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
    """Render one source-health card as an HTML snippet."""
    if not isinstance(entry, dict):
        status = str(entry)
        result_count = None
        reason = ""
    else:
        status = entry.get("status", "?")
        result_count = entry.get("result_count")
        reason = _html_esc(entry.get("reason", ""))

    if status == "ok":
        if result_count is not None and result_count == 0:
            css_class = "ok-empty"
            count_str = "0 results"
        elif result_count is not None:
            css_class = "ok"
            count_str = f"{result_count} result(s)"
        else:
            css_class = "ok"
            count_str = "ran"
    else:
        css_class = "unavailable"
        count_str = "unavailable"

    note_cell = f'<span class="note">{reason}</span>' if reason else ""
    return (
        f'<div class="source-card {css_class}">'
        f'<span class="source-label">{_html_esc(label)}</span>'
        f'<span class="source-status">{count_str}</span>'
        f'{note_cell}'
        f'</div>'
    )


def _html_keyword_table(keywords, *, include_platform=False):
    """Render the keyword table as an HTML snippet."""
    rows = []
    for k in keywords[:_KEYWORD_REPORT_LIMIT]:
        cells = [
            f"<td>{_html_esc(k.get('term', ''))}</td>",
            f"<td>{k.get('competition', 0)}</td>",
            f"<td>{k.get('relevance', 0)}</td>",
            f"<td>{k.get('opportunity', 0)}</td>",
            f"<td>{_html_esc(k.get('split', '').replace('-candidate', ''))}</td>",
            f"<td>{'yes' if k.get('is_gap') else ''}</td>",
            f"<td>{'yes' if k.get('suggest') else ''}</td>",
        ]
        if include_platform:
            cells.insert(1, f"<td>{_html_esc(k.get('platform', 'apple'))}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    header_cells = [
        "<th>Keyword</th>",
        *(["<th>Platform</th>"] if include_platform else []),
        "<th>Competition</th>",
        "<th>Relevance</th>",
        "<th>Opportunity</th>",
        "<th>Split</th>",
        "<th>Gap</th>",
        "<th>Suggest</th>",
    ]
    return (
        f'<table class="kw-table">'
        f'<thead><tr>{"".join(header_cells)}</tr></thead>'
        f'<tbody>{"".join(rows) if rows else "<tr><td colspan=7>No keywords scored.</td></tr>"}'
        f'</tbody></table>'
    )


def _html_bucket_card(title, keywords, accent_class):
    """Render an opportunity-bucket card as an HTML snippet."""
    terms = ", ".join(_html_esc(k["term"]) for k in keywords) if keywords else "&mdash;"
    return (
        f'<div class="bucket-card {accent_class}">'
        f'<h4>{_html_esc(title)}</h4>'
        f'<p>{terms}</p>'
        f'</div>'
    )


def _html_brand_conflict_row(c):
    strat_list = ", ".join(c.get("strategies", []))
    return (
        f'<tr class="brand-conflict">'
        f'<td><span class="badge-danger">&#9888;</span> {_html_esc(c.get("term", ""))}</td>'
        f'<td><span class="badge-danger">FORBIDDEN</span> {_html_esc(c.get("forbidden_match", ""))}</td>'
        f'<td>{_html_esc(c.get("replacement", "") or "&mdash;")}</td>'
        f'<td>{c.get("opportunity", 0)}</td>'
        f'<td>{c.get("relevance", 0)}</td>'
        f'<td class="strat-cell">{_html_esc(strat_list)}</td>'
        f'</tr>'
    )


def _html_listing_slots(s2_output, h2_output, *, store_label="Apple", slot_limits=""):
    """Render S2 listing proposals as HTML."""
    if not s2_output or not s2_output.get("slots"):
        return (
            f'<p class="pending">'
            f'<em>{_html_esc(store_label)} listing recommendation pending &mdash; '
            f'run the S2 Listing Strategist (Sonnet) subagent.</em>'
            f'</p>'
        )
    parts = []
    for slot in s2_output.get("slots", []):
        name = _html_esc(slot.get("slot", "?"))
        rec = slot.get("recommended") or {}
        rec_text = _html_esc(rec.get("text", ""))
        rec_count = rec.get("char_count", len(rec.get("text", "")))
        parts.append(
            f'<div class="listing-slot">'
            f'<strong>{name}</strong> (recommended): '
            f'<code>{rec_text}</code> <span class="char-count">({rec_count} chars)</span>'
        )
        alts = slot.get("alternatives") or []
        for i, alt in enumerate(alts[:2], start=1):
            alt_text = _html_esc(alt.get("text", ""))
            alt_count = alt.get("char_count", len(alt.get("text", "")))
            parts.append(
                f'<span class="alt">alt {i}: <code>{alt_text}</code> ({alt_count} chars)</span>'
            )
        parts.append("</div>")
    if h2_output:
        status = _html_esc(str(h2_output.get("status", "&mdash;")))
        note = _html_esc(h2_output.get("note", ""))
        parts.append(
            f'<div class="h2-crosscheck">'
            f'<strong>H2 cross-check ({_html_esc(store_label)}):</strong> {status} &mdash; {note}'
            f'</div>'
        )
    return "\n".join(parts)


_HTML_CSS = r"""
body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Oxygen,Ubuntu,Cantarell,sans-serif;color:#1e293b;background:#f1f5f9;line-height:1.6}
.container{max-width:960px;margin:0 auto;padding:24px 20px 60px}

header{background:#1a365d;color:#fff;padding:28px 24px;border-radius:8px;margin-bottom:24px}
header h1{font-size:1.6rem;margin:0 0 6px;font-weight:700}
header .meta{font-size:.85rem;color:#94a3b8}
header .modus{display:inline-block;background:#334155;color:#cbd5e1;padding:2px 8px;border-radius:4px;font-size:.75rem;margin-top:6px}
header .en-caveat{background:#fef3c7;color:#92400e;padding:6px 12px;border-radius:4px;margin-top:10px;font-size:.8rem;display:inline-block}

section{background:#fff;border-radius:8px;padding:24px;margin-bottom:20px;box-shadow:0 1px 3px rgba(0,0,0,.06)}
section h2{font-size:1.25rem;margin:0 0 16px;color:#1a365d;border-bottom:2px solid #e2e8f0;padding-bottom:8px}
section h3{font-size:1.05rem;margin:18px 0 10px;color:#334155}
section h4{font-size:.95rem;margin:0 0 6px;color:#1a365d}

.source-board{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:12px}
.source-card{border-radius:6px;padding:12px 14px;display:flex;flex-direction:column;gap:4px}
.source-card.ok{background:#ecfdf5;border:1px solid #a7f3d0}
.source-card.ok-empty{background:#f8fafc;border:1px solid #cbd5e1}
.source-card.unavailable{background:#fef3c7;border:1px solid #fcd34d}
.source-label{font-size:.8rem;font-weight:600;color:#475569}
.source-status{font-size:.75rem;font-weight:700;text-transform:uppercase}
.source-card.ok .source-status{color:#059669}
.source-card.ok-empty .source-status{color:#64748b}
.source-card.unavailable .source-status{color:#92400e}
.source-card .note{font-size:.7rem;color:#64748b;word-break:break-word}
.source-summary{font-size:.8rem;color:#475569;margin-top:8px}

.exec-summary p{font-size:.9rem;color:#334155;margin:6px 0}
.exec-summary .kpi-row{display:flex;flex-wrap:wrap;gap:12px;margin-top:12px}
.exec-summary .kpi{background:#f1f5f9;border-radius:6px;padding:10px 14px;min-width:100px}
.exec-summary .kpi .kpi-label{font-size:.7rem;color:#64748b;text-transform:uppercase;letter-spacing:.05em}
.exec-summary .kpi .kpi-value{font-size:1.1rem;font-weight:700;color:#1a365d}

.comp-table{width:100%;border-collapse:collapse;font-size:.85rem}
.comp-table th{text-align:left;padding:8px 10px;background:#f1f5f9;font-weight:600;color:#475569;font-size:.75rem;text-transform:uppercase}
.comp-table td{padding:8px 10px;border-bottom:1px solid #f1f5f9}
.comp-table tr:hover{background:#f8fafc}

.bucket-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.bucket-card{border-radius:8px;padding:16px;border:1px solid #e2e8f0}
.bucket-card.quick-win{background:#ecfdf5;border-color:#a7f3d0}
.bucket-card.niche-lever{background:#eff6ff;border-color:#bfdbfe}
.bucket-card.coverage-gap{background:#fef3c7;border-color:#fcd34d}
.bucket-card h4{font-size:.85rem}
.bucket-card p{font-size:.8rem;color:#475569;margin:4px 0 0}

.kw-table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:8px}
.kw-table th{text-align:left;padding:6px 8px;background:#f1f5f9;font-weight:600;color:#475569;font-size:.75rem;text-transform:uppercase}
.kw-table td{padding:6px 8px;border-bottom:1px solid #f1f5f9}
.kw-table tr:hover{background:#f8fafc}

.brand-panel{border:2px solid #dc2626;border-radius:8px;padding:20px;background:#fef2f2;margin-top:16px}
.brand-panel h3{color:#991b1b;margin-top:0}
.brand-panel .brand-note{font-size:.8rem;color:#7f1d1d;margin-bottom:14px}
.brand-table{width:100%;border-collapse:collapse;font-size:.85rem}
.brand-table th{text-align:left;padding:6px 8px;background:#fecaca;font-weight:600;color:#991b1b;font-size:.75rem;text-transform:uppercase}
.brand-table td{padding:6px 8px;border-bottom:1px solid #fecaca}
tr.brand-conflict{background:#fef2f2}
tr.brand-conflict:hover{background:#fee2e2}
.badge-danger{display:inline-block;background:#dc2626;color:#fff;padding:1px 6px;border-radius:3px;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em}
.strat-cell{max-width:260px;font-size:.78rem;color:#475569}

.listing-slot{margin:6px 0;font-size:.9rem}
.listing-slot code{background:#f1f5f9;padding:1px 5px;border-radius:3px;font-size:.85rem}
.char-count{color:#64748b;font-size:.8rem}
.listing-slot .alt{display:block;margin-left:20px;font-size:.85rem;color:#64748b}
.h2-crosscheck{font-size:.85rem;margin-top:12px;padding:8px 12px;background:#f0fdf4;border-radius:4px;color:#166534}
.listing-store{margin-bottom:20px}
.pending{color:#64748b;font-size:.85rem;font-style:italic}

.meth-list{font-size:.85rem;color:#334155;margin:6px 0 12px 20px}
.meth-list li{margin:4px 0}

threats-list{font-size:.85rem;color:#334155}
threats-list li{margin:4px 0}

.positioning-list{font-size:.85rem;color:#334155;margin:6px 0 12px 20px}
.positioning-list li{margin:4px 0}
.positioning-sub{font-size:.8rem;color:#64748b;margin:4px 0 12px 20px}
.positioning-sub li{margin:2px 0}

@media(max-width:640px){
  .container{padding:12px 8px}
  header{padding:18px 14px}
  section{padding:16px}
  .source-board{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
  .bucket-grid{grid-template-columns:1fr}
}
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
    parts.append('<html lang="en">')
    parts.append("<head>")
    parts.append(f'<meta charset="utf-8">')
    parts.append(f'<meta name="viewport" content="width=device-width,initial-scale=1">')
    parts.append(f"<title>ASO Research — {_html_esc(config['app_name'])}</title>")
    parts.append(f"<style>{_HTML_CSS}</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append('<div class="container">')

    # --- Header ---
    parts.append("<header>")
    parts.append(f"<h1>ASO Research &mdash; {_html_esc(config['app_name'])}</h1>")
    parts.append(f'<div class="meta">Generated: {_html_esc(generated)}</div>')
    modus_label = f"Mode A (post-launch) &mdash; {_html_esc(own_app_id)}" if modus_a else "Mode B (pre-launch)"
    parts.append(f'<span class="modus">{modus_label}</span>')
    if en_without_us:
        parts.append(
            '<div class="en-caveat">&#9888; Language is EN but country is not US &mdash; '
            'EN listing recommendations below are derived from a non-US market crawl and '
            'should NOT be treated as EN-market (US) findings.</div>'
        )
    parts.append("</header>")

    # --- Source Health Board ---
    parts.append("<section>")
    parts.append("<h2>Source Health</h2>")
    parts.append('<div class="source-board">')
    for key, label in _HTML_SOURCE_ORDER:
        entry = source_status.get(key)
        if entry is None:
            continue
        parts.append(_html_source_card(key, label, entry))
    parts.append("</div>")
    ran, unavailable = _source_split(source_status)
    parts.append(
        f'<div class="source-summary">'
        f'<strong>Sources that ran:</strong> {", ".join(ran) if ran else "iTunes Search API"}'
    )
    if unavailable:
        parts.append(
            f'<br><strong>Sources unavailable</strong> (never-blocking): {", ".join(unavailable)}'
        )
    parts.append("</div>")
    parts.append("</section>")

    # --- Executive Summary ---
    parts.append("<section>")
    parts.append("<h2>Executive Summary</h2>")
    cat = config.get("category", "other")
    lang = config.get("language", "de")
    country = config.get("country", "de")
    parts.append(f"<p><strong>Category:</strong> {_html_esc(cat)} &middot; "
                 f"<strong>Country / language:</strong> {country} / {lang}</p>")
    seeds = config.get("seed_keywords") or []
    if seeds:
        parts.append(f"<p><strong>Seed keywords:</strong> {', '.join(_html_esc(s) for s in seeds)}</p>")
    parts.append('<div class="kpi-row">')
    parts.append(f'<div class="kpi"><span class="kpi-label">Apple Competitors</span><span class="kpi-value">{len(apple_comps)}</span></div>')
    if has_play:
        parts.append(f'<div class="kpi"><span class="kpi-label">Play Competitors</span><span class="kpi-value">{len(play_comps)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Niche</span><span class="kpi-value">{len(niche)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Keywords</span><span class="kpi-value">{len(keywords)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Primary</span><span class="kpi-value">{len(primary)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Long-tail</span><span class="kpi-value">{len(longtail)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Coverage Gaps</span><span class="kpi-value">{len(gaps)}</span></div>')
    parts.append("</div>")
    parts.append(f"<p style='margin-top:12px;font-size:.85rem'><strong>Top keywords:</strong> {_html_esc(top_kw)}</p>")
    if s1_output and s1_output.get("dominant_themes"):
        themes = ", ".join(_html_esc(t) for t in s1_output["dominant_themes"][:5])
        parts.append(f"<p style='font-size:.85rem'><strong>Dominant themes (S1):</strong> {themes}</p>")
    parts.append("</section>")

    # --- Competitive Landscape ---
    parts.append("<section>")
    parts.append("<h2>Competitive Landscape</h2>")
    if not competitors:
        parts.append("<p><em>No competitors discovered for this seed.</em></p>")
    else:
        rows = []
        for c in competitors:
            rating = c.get("rating_avg")
            rating_str = f"{float(rating):.1f}" if isinstance(rating, (int, float)) else "—"
            source = "niche" if c.get("discovery") == "niche_similar" else "chart/search"
            sub = c.get("subtitle") or ""
            title = _html_esc(c.get("title", ""))
            if sub:
                title = f"{title} — <em>{_html_esc(sub)}</em>"
            rows.append(
                f"<tr>"
                f"<td>{title}</td>"
                f"<td>{_html_esc(c.get('developer', ''))}</td>"
                f"<td>{_html_esc(str(c.get('category', '')))}</td>"
                f"<td>{rating_str}</td>"
                f"<td>{c.get('rating_count', 0)}</td>"
                f"<td>{_html_esc(str(c.get('price_model', '')))}</td>"
                f"<td>{source}</td>"
                f"</tr>"
            )
        parts.append(
            '<table class="comp-table">'
            '<thead><tr>'
            '<th>Title</th><th>Developer</th><th>Category</th>'
            '<th>Rating</th><th># Ratings</th><th>Price</th><th>Source</th>'
            '</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )
    parts.append("</section>")

    # --- Positioning Map ---
    parts.append("<section>")
    parts.append("<h2>Positioning Map</h2>")
    if s1_output:
        for key, label in (
            ("niches", "Niches"),
            ("dominant_themes", "Dominant themes"),
            ("leader_positioning", "Leader positioning patterns"),
            ("audiences", "Audiences"),
        ):
            values = s1_output.get(key) or []
            if values:
                joined = "; ".join(_html_esc(v) for v in values[:8])
                parts.append(f"<li><strong>{_html_esc(label)}:</strong> {joined}</li>")
        if reddit_threads:
            parts.append("<p style='margin-top:12px'><strong>Qualitative grounding (Reddit):</strong></p>")
            for t in reddit_threads[:6]:
                sub = t.get("subreddit") or "—"
                parts.append(f"<li class='positioning-sub'>r/{_html_esc(sub)} — {_html_esc(t.get('title', ''))}</li>")
    else:
        parts.append(
            "<p><em>Full LLM positioning analysis pending (run the S1 Niche &amp; "
            "Positioning Analyst, Sonnet). Deterministic category clustering "
            "below as a placeholder read.</em></p>"
        )
        clusters: Dict[str, List[str]] = {}
        for c in competitors:
            cat = str(c.get("category", "other"))
            clusters.setdefault(cat, []).append(c.get("title", ""))
        for cat in sorted(clusters):
            titles = ", ".join(_html_esc(t) for t in clusters[cat][:6])
            parts.append(f"<li><strong>{_html_esc(cat)}:</strong> {titles}</li>")
    parts.append("</ul>")

    # MS qualitative
    if ms_entries and _entry_is_ok(source_status.get("ms")):
        ms_titles = ", ".join(_html_esc(e.get("title", "")) for e in ms_entries[:8])
        parts.append(
            f"<p style='font-size:.85rem;margin-top:12px;color:#475569'>"
            f"<strong>Microsoft Store (qualitative, best-effort):</strong> {len(ms_entries)} app(s) "
            f"observed &mdash; {ms_titles}. This is additional qualitative context only; "
            f"it does NOT enter keyword scoring."
            f"</p>"
        )
    parts.append("</section>")

    # --- Keyword Report ---
    parts.append("<section>")
    parts.append("<h2>Keyword Report</h2>")
    parts.append(
        '<p style="font-size:.85rem;color:#64748b">'
        "Scores are a deterministic <strong>Competition/Relevance signal</strong> &mdash; a proxy, "
        "<strong>never</strong> search volume. Competition = position-weighted slot share "
        "(Apple: Title &times;5 &middot; Subtitle &times;3 &middot; Description &times;1; "
        "Play: Title &times;5 &middot; Short &times;4 &middot; Long &times;2); "
        "Relevance = cosine TF-IDF to the seed concept (+15 Apple/Play Search-Suggest boost); "
        "Opportunity = Relevance &times; (100 &minus; Competition) (+10 niche bonus)."
        "</p>"
    )
    if not keywords:
        parts.append("<p><em>No keywords scored (empty competitor corpus).</em></p>")
    else:
        if has_play and play_kws:
            parts.append("<h3>Apple</h3>")
            parts.append(_html_keyword_table(apple_kws))
            parts.append("<h3>Google Play</h3>")
            parts.append(_html_keyword_table(play_kws))
        else:
            parts.append(_html_keyword_table(keywords))

        if gaps:
            gap_terms = ", ". join(_html_esc(k["term"]) for k in gaps[:15])
            parts.append(
                f"<p style='font-size:.85rem;margin-top:12px'>"
                f"<strong>Coverage gaps</strong> (competitors own in Title, seed lacks): {gap_terms}"
                f"</p>"
            )

    # Brand Conflicts
    if brand_conflicts:
        parts.append(
            '<div class="brand-panel">'
            '<h3>&#9888; Brand Conflicts</h3>'
            '<p class="brand-note">'
            "Keywords matching terms forbidden by the project's brand glossar "
            "(Anti-Vokabular). Each conflict carries the canonical replacement "
            "and four strategies &mdash; <strong>none auto-applied</strong>, "
            "decisions stay with the project owner."
            "</p>"
            '<table class="brand-table">'
            '<thead><tr>'
            '<th>Keyword</th><th>Forbidden Match</th><th>Replacement</th>'
            '<th>Opp.</th><th>Rel.</th><th>Strategies</th>'
            '</tr></thead>'
            f'<tbody>{"".join(_html_brand_conflict_row(c) for c in brand_conflicts)}</tbody>'
            '</table></div>'
        )
    parts.append("</section>")

    # --- Opportunities ---
    parts.append("<section>")
    parts.append("<h2>Opportunities</h2>")
    buckets = _opportunity_buckets(keywords)
    parts.append('<div class="bucket-grid">')
    parts.append(_html_bucket_card(
        f"Quick wins (Opp. &ge; {_QUICK_WIN_OPP_MIN}, Comp. &le; {_QUICK_WIN_COMP_MAX})",
        buckets["quick_win"], "quick-win"))
    parts.append(_html_bucket_card(
        f"Niche levers (Comp. &le; {_NICHE_LEVER_COMP_MAX}, Rel. &ge; {_NICHE_LEVER_REL_MIN})",
        buckets["niche_lever"], "niche-lever"))
    parts.append(_html_bucket_card(
        "Coverage gaps (competitors own in Title, seed lacks)",
        buckets["coverage_gap"], "coverage-gap"))
    parts.append("</div>")
    if s1_output and s1_output.get("missing_themes"):
        missing = "; ".join(_html_esc(t) for t in s1_output["missing_themes"][:8])
        parts.append(
            f"<p style='margin-top:14px;font-size:.85rem'>"
            f"<strong>Missing themes (S1):</strong> {missing}"
            f"</p>"
        )
    parts.append("</section>")

    # --- Risks / Threats ---
    parts.append("<section>")
    parts.append("<h2>Risks / Threats</h2>")
    if s1_output and s1_output.get("threats"):
        parts.append("<ul>")
        for t in s1_output["threats"][:10]:
            parts.append(f"<li>{_html_esc(t)}</li>")
        parts.append("</ul>")
    else:
        top_comp = sorted(keywords, key=lambda k: -int(k.get("competition", 0)))[:8]
        parts.append(
            "<p><em>Full LLM threat read pending (run S1). Highest-competition terms "
            "below as a deterministic threat proxy.</em></p>"
        )
        parts.append("<ul>")
        for k in top_comp:
            parts.append(
                f"<li><strong>{_html_esc(k.get('term', ''))}</strong> &mdash; "
                f"competition signal {k.get('competition', 0)}</li>"
            )
        parts.append("</ul>")
    parts.append("</section>")

    # --- Listing Recommendation ---
    parts.append("<section>")
    parts.append("<h2>Listing Recommendation</h2>")

    parts.append('<div class="listing-store">')
    parts.append("<h3>Apple</h3>")
    if en_without_us:
        parts.append(
            '<div class="en-caveat" style="margin-bottom:12px">&#9888; '
            'Language is EN but country is not US &mdash; the EN listing '
            'recommendations below are derived from a non-US market crawl and should '
            'NOT be treated as EN-market (US) findings.</div>'
        )
    limits = "Title 30 / Subtitle 30 / Keyword Field 100"
    parts.append(
        f'<p style="font-size:.85rem;color:#64748b">'
        f'1 recommended + 2 alternatives per Apple slot ({limits}), '
        f'validated by the H2 cross-check.</p>'
    )
    parts.append(_html_listing_slots(s2_output, h2_output, store_label="Apple"))
    parts.append("</div>")

    if has_play:
        parts.append('<div class="listing-store">')
        parts.append("<h3>Google Play</h3>")
        parts.append(
            '<p style="font-size:.85rem;color:#64748b">'
            "1 recommended + 2 alternatives per Play slot (Title 30 / Short 80 / "
            "Long 4000), optimised for Play's own ranking model, validated by the "
            "H2 cross-check.</p>"
        )
        parts.append(_html_listing_slots(s2_play_output, h2_play_output,
                                          store_label="Google Play"))
        parts.append("</div>")

    # Modus A self-audit
    if modus_a:
        parts.append("<h3>Self-audit (Modus A)</h3>")
        if s1_output and s1_output.get("own_app_audit"):
            audit = s1_output["own_app_audit"]
            items = audit if isinstance(audit, list) else [audit]
            parts.append("<ul>")
            for item in items:
                parts.append(f"<li>{_html_esc(item)}</li>")
            parts.append("</ul>")
        elif s2_output and s2_output.get("own_app_audit"):
            audit = s2_output["own_app_audit"]
            items = audit if isinstance(audit, list) else [audit]
            parts.append("<ul>")
            for item in items:
                parts.append(f"<li>{_html_esc(item)}</li>")
            parts.append("</ul>")
        else:
            parts.append(
                f"<p><em>Own app `{_html_esc(own_app_id)}` carried as a reference entry; "
                f"run S1/S2 with the own-app context to populate the self-audit comparison.</em></p>"
            )
    parts.append("</section>")

    # --- Methodology ---
    parts.append("<section>")
    parts.append("<h2>Methodology</h2>")
    parts.append(
        "<p style='font-size:.85rem;color:#334155'>"
        "Apple <strong>Core + Slots</strong> metadata collected (subtitle via Playwright, "
        "description from the iTunes API, keyword_hints inferred by inversion &mdash; "
        "never the hidden 100-char field). Keyword extraction: YAKE phrases + "
        "TF-IDF with position weighting (Title &times;5 &middot; Subtitle &times;3 "
        "&middot; Description &times;1) + Apple Search-Suggest enrichment; DE+EN "
        "stopwords, generics filtered, light morphology grouping."
        "</p>"
    )
    if has_play:
        parts.append(
            "<p style='font-size:.85rem;color:#334155'>"
            "Google Play <strong>Core + Slots</strong> metadata collected via "
            "google-play-scraper (search, charts, similar-apps): Title + "
            "Short Description (80, strong ranking factor) + Long Description "
            "(4000, fully indexed). Play <strong>tags are not collected</strong> "
            "(not reliably extractable). Play keywords flow into the SAME shared "
            "scoring engine with Play's own position weighting (Title &times;5 "
            "&middot; Short &times;4 &middot; Long &times;2) and Play autocomplete "
            "enriches the suggest set alongside Apple's."
            "</p>"
        )
    if _entry_is_ok(source_status.get("ms")):
        parts.append(
            "<p style='font-size:.85rem;color:#334155'>"
            "Microsoft Store metadata collected <strong>best-effort</strong> via Playwright "
            "(<code>apps.microsoft.com</code> is a single-page app, so collection uses "
            "<code>networkidle</code> + <code>wait_for_selector</code>). MS carries the "
            "<code>description</code> slot only &mdash; <strong>there is no MS ASO slot model "
            "and MS data never enters keyword extraction or scoring</strong>. It is passed "
            "to the S1 Niche &amp; Positioning Analyst as additional qualitative context."
            "</p>"
        )
    elif "ms" in source_status:
        parts.append(
            "<p style='font-size:.85rem;color:#334155'>"
            "Microsoft Store was <strong>unavailable</strong> this run (best-effort, "
            "never-blocking &mdash; the pipeline completed with Apple + Play results intact). "
            "MS is qualitative-only and would not have entered scoring regardless."
            "</p>"
        )
    parts.append("<p style='font-size:.85rem;color:#1a365d'><strong>Honesty &mdash; what is a proxy vs what is real:</strong></p>")
    parts.append(
        "<ul class='meth-list'>"
        "<li>Competition / Relevance / Opportunity are <strong>deterministic proxy "
        "signals</strong>, explicitly <strong>not real search volume or difficulty</strong> &mdash; they "
        "are labelled &quot;signal&quot; throughout. The only free <em>real-search</em> signals "
        "are Apple + Play Search-Suggest autocomplete (a +15 Relevance boost).</li>"
        "<li>Keyword counts come from the collected competitor corpus, not from a "
        "proprietary search-volume panel.</li>"
        "<li><strong>LLM phase (Claude-native, no paid API keys):</strong> the deterministic "
        "spine prepares a token-budget-gated, condensed representation (~70k "
        "token cap, chars/4 estimate); the H1 (Haiku) Metadata-Condenser, S1 "
        "(Sonnet) Niche &amp; Positioning Analyst, S2 (Sonnet) Listing Strategist, "
        "and H2 (Haiku) Cross-Checker interpret it &mdash; every subagent call sets "
        "its model explicitly. Politeness: &le;1 req/s/domain + jitter, "
        "exponential backoff on 429/503 (max 3 then skip), robots.txt "
        "respected, <strong>no stealth plugins</strong>. HTTP cache 24h / browser cache 12h "
        "at <code>~/.cache/aso-research/</code>.</li>"
        "</ul>"
    )
    parts.append("</section>")

    parts.append("</div>")  # .container
    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)
