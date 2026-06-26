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
            count_str = "0 Ergebnisse"
        elif result_count is not None:
            css_class = "ok"
            count_str = f"{result_count} Ergebnis(se)"
        else:
            css_class = "ok"
            count_str = "lief"
    else:
        css_class = "unavailable"
        count_str = "nicht verfügbar"

    note_cell = f'<span class="note">{reason}</span>' if reason else ""
    return (
        f'<div class="source-card {css_class}">'
        f'<span class="source-label">{_html_esc(label)}</span>'
        f'<span class="source-status">{count_str}</span>'
        f'{note_cell}'
        f'</div>'
    )


def _html_score_cell(score, max_score=100):
    """Render a score cell with an inline bar indicator."""
    pct = min(max(int(score), 0), max_score)
    return (
        f'<td class="score-cell">'
        f'<div class="score-bar"><div class="score-fill" style="width:{pct}%"></div></div>'
        f'<span class="score-num">{pct}</span>'
        f'</td>'
    )


_SPLIT_LABELS_DE = {
    "primary-candidate": "Primär",
    "long-tail-candidate": "Long-Tail",
}


def _html_keyword_table(keywords, *, include_platform=False):
    """Render the keyword table as an HTML snippet with score bars."""
    rows = []
    for k in keywords[:_KEYWORD_REPORT_LIMIT]:
        split_key = k.get("split", "")
        split_label = _SPLIT_LABELS_DE.get(split_key, split_key.replace("-candidate", ""))
        cells = [
            f"<td>{_html_esc(k.get('term', ''))}</td>",
            _html_score_cell(k.get("competition", 0)),
            _html_score_cell(k.get("relevance", 0)),
            _html_score_cell(k.get("opportunity", 0)),
            f"<td>{_html_esc(split_label)}</td>",
            f"<td>{'ja' if k.get('is_gap') else ''}</td>",
            f"<td>{'ja' if k.get('suggest') else ''}</td>",
        ]
        if include_platform:
            cells.insert(1, f"<td>{_html_esc(k.get('platform', 'apple'))}</td>")
        rows.append(f"<tr>{''.join(cells)}</tr>")

    header_cells = [
        "<th>Keyword</th>",
        *(["<th>Plattform</th>"] if include_platform else []),
        "<th>Wettbewerb</th>",
        "<th>Relevanz</th>",
        "<th>Chance</th>",
        "<th>Kategorie</th>",
        "<th>Lücke</th>",
        "<th>Suggest</th>",
    ]
    colspan = 7 + (1 if include_platform else 0)
    return (
        f'<table class="kw-table">'
        f'<thead><tr>{"".join(header_cells)}</tr></thead>'
        f'<tbody>{"".join(rows) if rows else f"<tr><td colspan={colspan}>Keine Keywords bewertet.</td></tr>"}'
        f'</tbody></table>'
    )


def _html_bucket_card(title, keywords, accent_class):
    """Render an opportunity-bucket card as an HTML snippet."""
    terms = ", ".join(_html_esc(k["term"]) for k in keywords) if keywords else "&mdash;"
    css_map = {
        "schnelle-gewinne": "schnelle-gewinne",
        "nischen-hebel": "nischen-hebel",
        "abdeckungsluecken": "abdeckungsluecken",
    }
    return (
        f'<div class="bucket-card {css_map.get(accent_class, accent_class)}">'
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
            f'<em>{_html_esc(store_label)} Listing-Empfehlung ausstehend &mdash; '
            f'S2 Listing-Stratege (Sonnet) Subagent ausführen.</em>'
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
            f'<strong>{name}</strong> (empfohlen): '
            f'<code>{rec_text}</code> <span class="char-count">({rec_count} Zeichen)</span>'
        )
        alts = slot.get("alternatives") or []
        for i, alt in enumerate(alts[:2], start=1):
            alt_text = _html_esc(alt.get("text", ""))
            alt_count = alt.get("char_count", len(alt.get("text", "")))
            parts.append(
                f'<span class="alt">Alt {i}: <code>{alt_text}</code> ({alt_count} Zeichen)</span>'
            )
        parts.append("</div>")
    if h2_output:
        status = _html_esc(str(h2_output.get("status", "&mdash;")))
        note = _html_esc(h2_output.get("note", ""))
        parts.append(
            f'<div class="h2-crosscheck">'
            f'<strong>H2-Cross-Check ({_html_esc(store_label)}):</strong> {status} &mdash; {note}'
            f'</div>'
        )
    return "\n".join(parts)


_HTML_CSS = r"""
body{margin:0;padding:0;font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;color:#1A1D23;background:#F7F8FA;line-height:1.6}
.container{max-width:960px;margin:0 auto;padding:24px 20px 60px}

header{background:linear-gradient(135deg,#4338CA 0%,#3730A3 100%);color:#fff;padding:32px 28px;border-radius:10px;margin-bottom:24px}
header h1{font-family:Georgia,ui-serif,serif;font-size:1.75rem;margin:0 0 8px;font-weight:400;letter-spacing:-0.01em}
header .meta{font-size:.8rem;color:rgba(255,255,255,.65)}
header .modus{display:inline-block;background:rgba(255,255,255,.12);color:rgba(255,255,255,.85);padding:3px 10px;border-radius:4px;font-size:.75rem;margin-top:8px}
header .en-caveat{background:#FEF3C7;color:#92400E;padding:6px 12px;border-radius:4px;margin-top:10px;font-size:.8rem;display:inline-block}

section{background:#fff;border-radius:10px;padding:28px;margin-bottom:20px;box-shadow:0 1px 2px rgba(0,0,0,.04),0 2px 8px rgba(0,0,0,.04);border:1px solid #E5E7EB}
section h2{font-family:Georgia,ui-serif,serif;font-size:1.3rem;margin:0 0 18px;color:#4338CA;font-weight:400;letter-spacing:-0.01em;border-bottom:2px solid #EEF2FF;padding-bottom:10px}
section h3{font-size:1.05rem;margin:20px 0 10px;color:#3730A3;font-family:Georgia,ui-serif,serif;font-weight:400}
section h4{font-size:.9rem;margin:0 0 6px;color:#4338CA}

.source-board{display:grid;grid-template-columns:repeat(auto-fill,minmax(180px,1fr));gap:10px;margin-bottom:12px}
.source-card{border-radius:8px;padding:12px 14px;display:flex;flex-direction:column;gap:4px;border:1px solid #E5E7EB}
.source-card.ok{background:#ECFDF5;border-color:#A7F3D0}
.source-card.ok-empty{background:#F9FAFB;border-color:#E5E7EB}
.source-card.unavailable{background:#FEF3C7;border-color:#FDE68A}
.source-label{font-size:.72rem;font-weight:600;color:#6B7280;text-transform:uppercase;letter-spacing:.04em}
.source-status{font-size:.75rem;font-weight:700}
.source-card.ok .source-status{color:#059669}
.source-card.ok-empty .source-status{color:#6B7280}
.source-card.unavailable .source-status{color:#92400E}
.source-card .note{font-size:.68rem;color:#6B7280;word-break:break-word}
.source-summary{font-size:.78rem;color:#6B7280;margin-top:8px}

.kpi-row{display:flex;flex-wrap:wrap;gap:10px;margin-top:12px}
.kpi{background:#F7F8FA;border-radius:8px;padding:12px 16px;min-width:100px;border:1px solid #E5E7EB}
.kpi-label{font-size:.68rem;color:#6B7280;text-transform:uppercase;letter-spacing:.05em;display:block}
.kpi-value{font-size:1.2rem;font-weight:700;color:#4338CA;font-variant-numeric:tabular-nums}

.comp-table{width:100%;border-collapse:collapse;font-size:.85rem}
.comp-table th{text-align:left;padding:8px 10px;background:#F7F8FA;font-weight:600;color:#6B7280;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}
.comp-table td{padding:8px 10px;border-bottom:1px solid #F3F4F6}
.comp-table tr:hover{background:#FAFBFC}

.bucket-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px}
.bucket-card{border-radius:10px;padding:18px;border:1px solid #E5E7EB}
.bucket-card.schnelle-gewinne{background:#ECFDF5;border-color:#A7F3D0}
.bucket-card.nischen-hebel{background:#EEF2FF;border-color:#C7D2FE}
.bucket-card.abdeckungsluecken{background:#FEF3C7;border-color:#FDE68A}
.bucket-card h4{font-size:.85rem;margin-bottom:6px}
.bucket-card p{font-size:.8rem;color:#6B7280;margin:4px 0 0}

.kw-table{width:100%;border-collapse:collapse;font-size:.85rem;margin-top:8px}
.kw-table th{text-align:left;padding:6px 10px;background:#F7F8FA;font-weight:600;color:#6B7280;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}
.kw-table td{padding:6px 10px;border-bottom:1px solid #F3F4F6;font-variant-numeric:tabular-nums}
.kw-table tr:hover{background:#FAFBFC}

.score-cell{min-width:95px;white-space:nowrap}
.score-bar{display:inline-block;width:64px;height:6px;background:#E5E7EB;border-radius:3px;vertical-align:middle;margin-right:6px;overflow:hidden}
.score-fill{height:100%;background:#4338CA;border-radius:3px;transition:width .3s ease}
.score-num{font-size:.8rem;font-weight:600;color:#1A1D23;vertical-align:middle;font-variant-numeric:tabular-nums}

.brand-panel{border:2px solid #991B1B;border-radius:10px;padding:22px;background:#FEF2F2;margin-top:16px}
.brand-panel h3{color:#991B1B;margin-top:0}
.brand-note{font-size:.8rem;color:#991B1B;margin-bottom:14px}
.brand-table{width:100%;border-collapse:collapse;font-size:.85rem}
.brand-table th{text-align:left;padding:6px 10px;background:#FECACA;font-weight:600;color:#991B1B;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}
.brand-table td{padding:6px 10px;border-bottom:1px solid #FECACA}
tr.brand-conflict{background:#FEF2F2}
tr.brand-conflict:hover{background:#FEE2E2}
.badge-danger{display:inline-block;background:#991B1B;color:#fff;padding:1px 7px;border-radius:4px;font-size:.7rem;font-weight:700;text-transform:uppercase;letter-spacing:.03em}
.strat-cell{max-width:260px;font-size:.78rem;color:#6B7280}

.listing-slot{margin:6px 0;font-size:.88rem}
.listing-slot code{background:#F3F4F6;padding:1px 6px;border-radius:4px;font-size:.82rem;font-family:"SF Mono",ui-monospace,monospace}
.char-count{color:#6B7280;font-size:.78rem}
.listing-slot .alt{display:block;margin-left:20px;font-size:.82rem;color:#6B7280}
.h2-crosscheck{font-size:.82rem;margin-top:12px;padding:8px 14px;background:#ECFDF5;border-radius:6px;color:#065F46}
.listing-store{margin-bottom:22px}
.pending{color:#6B7280;font-size:.82rem;font-style:italic}

.glossary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}
.glossary-card{padding:16px;border-radius:8px;background:#F7F8FA;border:1px solid #E5E7EB}
.glossary-card dt{font-size:.85rem;font-weight:700;color:#4338CA;margin-bottom:4px}
.glossary-card dd{font-size:.78rem;color:#6B7280;margin:0;line-height:1.5}

.meth-list{font-size:.82rem;color:#1A1D23;margin:6px 0 12px 20px}
.meth-list li{margin:6px 0}

ul li{font-size:.85rem;color:#1A1D23;margin:4px 0}

@media(max-width:640px){
  .container{padding:12px 10px}
  header{padding:22px 16px}
  section{padding:18px}
  .source-board{grid-template-columns:repeat(auto-fill,minmax(140px,1fr))}
  .bucket-grid{grid-template-columns:1fr}
  .glossary-grid{grid-template-columns:1fr}
  .kpi-row{gap:8px}
  .kpi{min-width:80px;padding:10px 12px}
  .kpi-value{font-size:1rem}
}

@media(prefers-reduced-motion:reduce){
  .score-fill{transition:none}
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
    parts.append('<html lang="de">')
    parts.append("<head>")
    parts.append(f'<meta charset="utf-8">')
    parts.append(f'<meta name="viewport" content="width=device-width,initial-scale=1">')
    parts.append(f"<title>ASO-Recherche — {_html_esc(config['app_name'])}</title>")
    parts.append(f"<style>{_HTML_CSS}</style>")
    parts.append("</head>")
    parts.append("<body>")
    parts.append('<div class="container">')

    # --- Header ---
    parts.append("<header>")
    parts.append(f"<h1>ASO-Recherche &mdash; {_html_esc(config['app_name'])}</h1>")
    parts.append(f'<div class="meta">Erstellt: {_html_esc(generated)}</div>')
    modus_label = f"Modus A (nach Launch) &mdash; {_html_esc(own_app_id)}" if modus_a else "Modus B (Pre-Launch)"
    parts.append(f'<span class="modus">{modus_label}</span>')
    if en_without_us:
        parts.append(
            '<div class="en-caveat">&#9888; Sprache ist EN, Land aber nicht US &mdash; '
            'die EN-Listing-Empfehlungen stammen aus einem Nicht-US-Markt-Crawl und '
            'sollten NICHT als EN-Markt(US)-Ergebnisse behandelt werden.</div>'
        )
    parts.append("</header>")

    # --- Quellenstatus ---
    parts.append("<section>")
    parts.append("<h2>Quellenstatus</h2>")
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
        f'<strong>Verfügbare Quellen:</strong> {", ".join(ran) if ran else "iTunes Search API"}'
    )
    if unavailable:
        parts.append(
            f'<br><strong>Nicht verfügbar</strong> (nie blockierend): {", ".join(unavailable)}'
        )
    parts.append("</div>")
    parts.append("</section>")

    # --- Zusammenfassung ---
    parts.append("<section>")
    parts.append("<h2>Zusammenfassung</h2>")
    cat = config.get("category", "other")
    lang = config.get("language", "de")
    country = config.get("country", "de")
    parts.append(f"<p><strong>Kategorie:</strong> {_html_esc(cat)} &middot; "
                 f"<strong>Land / Sprache:</strong> {country} / {lang}</p>")
    seeds = config.get("seed_keywords") or []
    if seeds:
        parts.append(f"<p><strong>Seed-Keywords:</strong> {', '.join(_html_esc(s) for s in seeds)}</p>")
    parts.append('<div class="kpi-row">')
    parts.append(f'<div class="kpi"><span class="kpi-label">Apple-Wettbewerber</span><span class="kpi-value">{len(apple_comps)}</span></div>')
    if has_play:
        parts.append(f'<div class="kpi"><span class="kpi-label">Play-Wettbewerber</span><span class="kpi-value">{len(play_comps)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Nische</span><span class="kpi-value">{len(niche)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Keywords</span><span class="kpi-value">{len(keywords)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Primär</span><span class="kpi-value">{len(primary)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Long-Tail</span><span class="kpi-value">{len(longtail)}</span></div>')
    parts.append(f'<div class="kpi"><span class="kpi-label">Lücken</span><span class="kpi-value">{len(gaps)}</span></div>')
    parts.append("</div>")
    parts.append(f"<p style='margin-top:12px;font-size:.85rem'><strong>Top-Keywords:</strong> {_html_esc(top_kw)}</p>")
    if s1_output and s1_output.get("dominant_themes"):
        themes = ", ".join(_html_esc(t) for t in s1_output["dominant_themes"][:5])
        parts.append(f"<p style='font-size:.85rem'><strong>Dominante Themen (S1):</strong> {themes}</p>")
    parts.append("</section>")

    # --- Wettbewerbslandschaft ---
    parts.append("<section>")
    parts.append("<h2>Wettbewerbslandschaft</h2>")
    if not competitors:
        parts.append("<p><em>Keine Wettbewerber zu diesem Seed gefunden.</em></p>")
    else:
        rows = []
        for c in competitors:
            rating = c.get("rating_avg")
            rating_str = f"{float(rating):.1f}" if isinstance(rating, (int, float)) else "—"
            source = "Nische" if c.get("discovery") == "niche_similar" else "Chart/Suche"
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
            '<th>Titel</th><th>Entwickler</th><th>Kategorie</th>'
            '<th>Bewertung</th><th># Bewertungen</th><th>Preis</th><th>Quelle</th>'
            '</tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>'
        )
    parts.append("</section>")

    # --- Positionierungsmap ---
    parts.append("<section>")
    parts.append("<h2>Positionierungsmap</h2>")
    if s1_output:
        for key, label in (
            ("niches", "Nischen"),
            ("dominant_themes", "Dominante Themen"),
            ("leader_positioning", "Positionierung der Marktführer"),
            ("audiences", "Zielgruppen"),
        ):
            values = s1_output.get(key) or []
            if values:
                joined = "; ".join(_html_esc(v) for v in values[:8])
                parts.append(f"<li><strong>{_html_esc(label)}:</strong> {joined}</li>")
        if reddit_threads:
            parts.append("<p style='margin-top:12px'><strong>Qualitative Untermauerung (Reddit):</strong></p>")
            for t in reddit_threads[:6]:
                sub = t.get("subreddit") or "—"
                parts.append(f"<li style='font-size:.8rem;color:#6B7280;margin:2px 0'>r/{_html_esc(sub)} — {_html_esc(t.get('title', ''))}</li>")
    else:
        parts.append(
            "<p><em>Vollständige LLM-Positionierungsanalyse ausstehend (S1 Nische &amp; "
            "Positionierungs-Analyst, Sonnet ausführen). Deterministische Kategorie-"
            "Clusterung unten als Platzhalter.</em></p>"
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
            f"<p style='font-size:.85rem;margin-top:12px;color:#6B7280'>"
            f"<strong>Microsoft Store (qualitativ, Best-Effort):</strong> {len(ms_entries)} App(s) "
            f"beobachtet &mdash; {ms_titles}. Rein qualitativer Kontext; "
            f"fließt NICHT in das Keyword-Scoring ein."
            f"</p>"
        )
    parts.append("</section>")

    # --- Keyword-Bericht ---
    parts.append("<section>")
    parts.append("<h2>Keyword-Bericht</h2>")
    parts.append(
        '<p style="font-size:.85rem;color:#6B7280">'
        "Die Werte sind ein deterministisches <strong>Wettbewerbs-/Relevanz-Signal</strong> &mdash; ein Proxy, "
        "<strong>kein</strong> echtes Suchvolumen. Wettbewerb = positionsgewichteter Slot-Anteil "
        "(Apple: Titel &times;5 &middot; Untertitel &times;3 &middot; Beschreibung &times;1; "
        "Play: Titel &times;5 &middot; Kurzbeschreibung &times;4 &middot; Langbeschreibung &times;2); "
        "Relevanz = Cosinus-TF-IDF zum Seed-Konzept (+15 Apple/Play Search-Suggest-Bonus); "
        "Chance = Relevanz &times; (100 &minus; Wettbewerb) (+10 Nischen-Bonus)."
        "</p>"
    )
    if not keywords:
        parts.append("<p><em>Keine Keywords bewertet (leerer Wettbewerber-Korpus).</em></p>")
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
                f"<strong>Abdeckungslücken</strong> (Wettbewerber führen im Titel, Seed nicht): {gap_terms}"
                f"</p>"
            )

    # Markenkonflikte
    if brand_conflicts:
        parts.append(
            '<div class="brand-panel">'
            '<h3>&#9888; Markenkonflikte</h3>'
            '<p class="brand-note">'
            "Keywords, die Begriffe aus dem Anti-Vokabular des Projekts enthalten. "
            "Jeder Konflikt zeigt die kanonische Ersetzung und vier Strategien "
            "&mdash; <strong>keine automatisch angewandt</strong>, "
            "die Entscheidung liegt beim Projektinhaber."
            "</p>"
            '<table class="brand-table">'
            '<thead><tr>'
            '<th>Keyword</th><th>Verbotener Treffer</th><th>Ersetzung</th>'
            '<th>Chance</th><th>Rel.</th><th>Strategien</th>'
            '</tr></thead>'
            f'<tbody>{"".join(_html_brand_conflict_row(c) for c in brand_conflicts)}</tbody>'
            '</table></div>'
        )
    parts.append("</section>")

    # --- Chancen ---
    parts.append("<section>")
    parts.append("<h2>Chancen</h2>")
    buckets = _opportunity_buckets(keywords)
    parts.append('<div class="bucket-grid">')
    parts.append(_html_bucket_card(
        f"Schnelle Gewinne (Chance &ge; {_QUICK_WIN_OPP_MIN}, Wettb. &le; {_QUICK_WIN_COMP_MAX})",
        buckets["quick_win"], "schnelle-gewinne"))
    parts.append(_html_bucket_card(
        f"Nischen-Hebel (Wettb. &le; {_NICHE_LEVER_COMP_MAX}, Rel. &ge; {_NICHE_LEVER_REL_MIN})",
        buckets["niche_lever"], "nischen-hebel"))
    parts.append(_html_bucket_card(
        "Abdeckungslücken (Wettbewerber führen im Titel, Seed nicht)",
        buckets["coverage_gap"], "abdeckungsluecken"))
    parts.append("</div>")
    if s1_output and s1_output.get("missing_themes"):
        missing = "; ".join(_html_esc(t) for t in s1_output["missing_themes"][:8])
        parts.append(
            f"<p style='margin-top:14px;font-size:.85rem'>"
            f"<strong>Fehlende Themen (S1):</strong> {missing}"
            f"</p>"
        )
    parts.append("</section>")

    # --- Risiken / Bedrohungen ---
    parts.append("<section>")
    parts.append("<h2>Risiken / Bedrohungen</h2>")
    if s1_output and s1_output.get("threats"):
        parts.append("<ul>")
        for t in s1_output["threats"][:10]:
            parts.append(f"<li>{_html_esc(t)}</li>")
        parts.append("</ul>")
    else:
        top_comp = sorted(keywords, key=lambda k: -int(k.get("competition", 0)))[:8]
        parts.append(
            "<p><em>Vollständige LLM-Bedrohungsanalyse ausstehend (S1 ausführen). "
            "Begriffe mit höchstem Wettbewerb unten als deterministischer Proxy.</em></p>"
        )
        parts.append("<ul>")
        for k in top_comp:
            parts.append(
                f"<li><strong>{_html_esc(k.get('term', ''))}</strong> &mdash; "
                f"Wettbewerbssignal {k.get('competition', 0)}</li>"
            )
        parts.append("</ul>")
    parts.append("</section>")

    # --- Listing-Empfehlung ---
    parts.append("<section>")
    parts.append("<h2>Listing-Empfehlung</h2>")

    parts.append('<div class="listing-store">')
    parts.append("<h3>Apple</h3>")
    if en_without_us:
        parts.append(
            '<div class="en-caveat" style="margin-bottom:12px">&#9888; '
            'Sprache ist EN, Land aber nicht US &mdash; die EN-Listing-Empfehlungen '
            'stammen aus einem Nicht-US-Markt-Crawl und sollten NICHT als '
            'EN-Markt(US)-Ergebnisse behandelt werden.</div>'
        )
    limits = "Titel 30 / Untertitel 30 / Keyword-Feld 100"
    parts.append(
        f'<p style="font-size:.85rem;color:#6B7280">'
        f'1 empfohlen + 2 Alternativen pro Apple-Slot ({limits}), '
        f'validiert durch den H2-Cross-Check.</p>'
    )
    parts.append(_html_listing_slots(s2_output, h2_output, store_label="Apple"))
    parts.append("</div>")

    if has_play:
        parts.append('<div class="listing-store">')
        parts.append("<h3>Google Play</h3>")
        parts.append(
            '<p style="font-size:.85rem;color:#6B7280">'
            "1 empfohlen + 2 Alternativen pro Play-Slot (Titel 30 / Kurzbeschreibung 80 / "
            "Langbeschreibung 4000), optimiert für Plays Ranking-Modell, validiert durch den "
            "H2-Cross-Check.</p>"
        )
        parts.append(_html_listing_slots(s2_play_output, h2_play_output,
                                          store_label="Google Play"))
        parts.append("</div>")

    # Modus A self-audit
    if modus_a:
        parts.append("<h3>Selbstaudit (Modus A)</h3>")
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
                f"<p><em>Eigene App `{_html_esc(own_app_id)}` als Referenzeintrag geführt; "
                f"S1/S2 mit Own-App-Kontext ausführen, um den Selbstaudit zu befüllen.</em></p>"
            )
    parts.append("</section>")

    # --- Methodik ---
    parts.append("<section>")
    parts.append("<h2>Methodik</h2>")
    parts.append(
        "<p style='font-size:.85rem;color:#1A1D23'>"
        "Apple <strong>Core + Slots</strong>-Metadaten gesammelt (Untertitel via Playwright, "
        "Beschreibung aus der iTunes-API, keyword_hints durch Inversion abgeleitet &mdash; "
        "niemals das versteckte 100-Zeichen-Feld). Keyword-Extraktion: YAKE-Phrasen + "
        "TF-IDF mit Positionsgewichtung (Titel &times;5 &middot; Untertitel &times;3 "
        "&middot; Beschreibung &times;1) + Apple Search-Suggest-Anreicherung; DE+EN-"
        "Stopwörter, Generika gefiltert, leichte Morphologie-Gruppierung."
        "</p>"
    )
    if has_play:
        parts.append(
            "<p style='font-size:.85rem;color:#1A1D23'>"
            "Google Play <strong>Core + Slots</strong>-Metadaten gesammelt via "
            "google-play-scraper (Suche, Charts, Similar-Apps): Titel + "
            "Kurzbeschreibung (80, starker Ranking-Faktor) + Langbeschreibung "
            "(4000, vollständig indexiert). Play-<strong>Tags werden nicht erfasst</strong> "
            "(nicht zuverlässig extrahierbar). Play-Keywords fließen in DIESELBE "
            "Scoring-Engine mit Play-eigener Positionsgewichtung (Titel &times;5 "
            "&middot; Kurzbeschreibung &times;4 &middot; Langbeschreibung &times;2) "
            "und Play-Autocomplete ergänzt das Suggest-Set."
            "</p>"
        )
    if _entry_is_ok(source_status.get("ms")):
        parts.append(
            "<p style='font-size:.85rem;color:#1A1D23'>"
            "Microsoft Store-Metadaten <strong>per Best-Effort</strong> via Playwright gesammelt "
            "(<code>apps.microsoft.com</code> ist eine Single-Page-App, daher mit "
            "<code>networkidle</code> + <code>wait_for_selector</code>). MS hat nur den "
            "<code>description</code>-Slot &mdash; <strong>es gibt kein MS-ASO-Slot-Modell "
            "und MS-Daten fließen niemals in Keyword-Extraktion oder Scoring ein</strong>. "
            "Sie werden als zusätzlicher qualitativer Kontext an den S1-Analysten übergeben."
            "</p>"
        )
    elif "ms" in source_status:
        parts.append(
            "<p style='font-size:.85rem;color:#1A1D23'>"
            "Microsoft Store war in diesem Durchlauf <strong>nicht verfügbar</strong> (Best-Effort, "
            "nie blockierend &mdash; die Pipeline wurde mit Apple + Play-Ergebnissen abgeschlossen). "
            "MS ist rein qualitativ und wäre ohnehin nicht ins Scoring eingeflossen."
            "</p>"
        )
    parts.append("<p style='font-size:.85rem;color:#4338CA'><strong>Ehrlichkeit &mdash; was ist ein Proxy, was ist echt:</strong></p>")
    parts.append(
        "<ul class='meth-list'>"
        "<li>Wettbewerb / Relevanz / Chance sind <strong>deterministische Proxy-"
        "Signale</strong>, ausdrücklich <strong>kein echtes Suchvolumen und keine echte Difficulty</strong> &mdash; "
        "sie werden durchgängig als &quot;Signal&quot; bezeichnet. Die einzigen kostenlosen "
        "<em>Echtsuche</em>-Signale sind Apple- und Play-Search-Suggest-Autovervollständigung "
        "(ein +15-Relevanz-Bonus).</li>"
        "<li>Keyword-Zahlen stammen aus dem gesammelten Wettbewerber-Korpus, nicht aus "
        "einem proprietären Suchvolumen-Panel.</li>"
        "<li><strong>LLM-Phase (Claude-nativ, keine kostenpflichtigen API-Keys):</strong> "
        "das deterministische Grundgerüst bereitet eine Token-Budget-begrenzte, "
        "kondensierte Repräsentation vor (~70k Token-Cap, Zeichen/4-Schätzung); "
        "der H1 (Haiku) Metadaten-Kondensierer, S1 (Sonnet) Nischen- &amp; Positionierungs-"
        "Analyst, S2 (Sonnet) Listing-Stratege und H2 (Haiku) Cross-Checker "
        "interpretieren sie &mdash; jeder Subagent-Aufruf setzt sein Modell explizit. "
        "Höflichkeit: &le;1 Anfrage/s/Domain + Jitter, exponentielles Backoff bei "
        "429/503 (max. 3, dann überspringen), robots.txt respektiert, "
        "<strong>keine Stealth-Plugins</strong>. HTTP-Cache 24h / Browser-Cache 12h "
        "unter <code>~/.cache/aso-research/</code>.</li>"
        "</ul>"
    )
    parts.append("</section>")

    # --- Glossar ---
    parts.append("<section>")
    parts.append("<h2>Glossar</h2>")
    parts.append('<div class="glossary-grid">')
    glossary_terms = [
        ("Relevanz",
         "Maß für die thematische Nähe eines Keywords zum Produktkonzept. "
         "Berechnet als gewichtete TF-IDF-Ähnlichkeit zu den Seed-Keywords — "
         "je höher, desto passender zum Produkt."),
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
    for term, definition in glossary_terms:
        parts.append(
            f'<div class="glossary-card">'
            f'<dt>{_html_esc(term)}</dt>'
            f'<dd>{_html_esc(definition)}</dd>'
            f'</div>'
        )
    parts.append("</div>")
    parts.append("</section>")

    parts.append("</div>")  # .container
    parts.append("</body>")
    parts.append("</html>")

    return "\n".join(parts)
