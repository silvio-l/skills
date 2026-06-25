#!/usr/bin/env python3
"""Minimal report assembly for the skeleton slice.

Two sections only — Executive Summary + a Competitor table — plus a
short Methodology footnote that is honest about what this slice does
and does not do. The full 8-section report lands in slice 03.

Determinism: the report body is stable for a given
(config, competitors, keywords); only the generated timestamp differs
between runs (expected). The timestamp is injected by the caller so a
test can fix it.
"""

from __future__ import annotations

import datetime
from typing import Dict, List

_GENERATED_LABEL = "Generated"


def _row(cells: List[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def build_report(
    config: Dict,
    competitors: List[Dict],
    keywords: List[Dict],
    *,
    now: datetime.datetime,
) -> str:
    """Assemble the minimal ``report.md`` body as a string."""
    n_comp = len(competitors)
    top_kw = ", ".join(k["term"] for k in keywords[:8]) or "—"
    generated = now.strftime("%Y-%m-%d %H:%M:%S")

    lines: List[str] = []
    lines.append(f"# ASO Research — {config['app_name']}")
    lines.append("")
    lines.append(f"_{_GENERATED_LABEL}: {generated}_")
    lines.append("")
    # --- 1. Executive Summary ---
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(
        f"This is a **skeleton** run (slice 01). It discovered **{n_comp}** "
        f"Apple competitor(s) via the iTunes Search API only — no browser, "
        f"no charts, no LLM. Keyword extraction is deliberately trivial "
        f"(title tokens) and scores are **placeholder signals**, not the "
        f"real Competition/Relevance engine (slice 02) or search volume."
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
    lines.append(f"- **Top placeholder keywords:** {top_kw}")
    lines.append("")
    # --- 2. Competitive Landscape (table) ---
    lines.append("## Competitive Landscape")
    lines.append("")
    if not competitors:
        lines.append("_No competitors discovered for this seed._")
    else:
        header = _row(
            ["Title", "Developer", "Category", "Rating", "# Ratings", "Price", "Updated"]
        )
        sep = _row(["---", "---", "---", "---", "---", "---", "---"])
        lines.append(header)
        lines.append(sep)
        for c in competitors:
            rating = c.get("rating_avg")
            rating_str = f"{float(rating):.1f}" if isinstance(rating, (int, float)) else "—"
            lines.append(
                _row(
                    [
                        str(c.get("title", "")),
                        str(c.get("developer", "")),
                        str(c.get("category", "")),
                        rating_str,
                        str(c.get("rating_count", 0)),
                        str(c.get("price_model", "")),
                        str(c.get("last_updated", "")[:10]),
                    ]
                )
            )
    lines.append("")
    # --- Methodology footnote ---
    lines.append("## Methodology")
    lines.append("")
    lines.append(
        "Slice 01 baseline. Data channel: **iTunes Search API** only "
        "(documented ~20/min rate limit honoured). Apple **Core** metadata "
        "collected; Apple **slot** fields (subtitle/description) are left "
        "empty by this slice (subtitle needs Playwright → slice 02). "
        "Extraction is title-token-only; Competition is a placeholder "
        "title-share fraction, Relevance is a placeholder seed/description "
        "bias — **neither is real search volume**. Reports are not scored "
        "by an LLM in this slice. HTTP responses are cached at "
        "`~/.cache/aso-research/` (24h TTL)."
    )
    lines.append("")
    return "\n".join(lines)
