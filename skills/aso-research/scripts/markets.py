#!/usr/bin/env python3
"""Cross-market keyword comparison (D4 — multi-country).

Given the scored ``keywords.json`` of the same app researched in several
markets (countries), build a comparison that shows, per keyword, its
**opportunity in each market** and flags **market-specific opportunities** —
a term that is strong in one country but weak/absent in another is an
expansion lever (localise the listing for that market).

Pure + deterministic: identical per-market input → identical comparison.
"""

from __future__ import annotations

from typing import Dict, List, Mapping, Sequence

# A keyword counts as "strong" in a market at/above this opportunity, and
# "weak/absent" below the low bar — the spread is what flags a market gap.
STRONG_OPP = 35
WEAK_OPP = 12


def _best_opp_by_term(keywords: Sequence[Mapping]) -> Dict[str, int]:
    """Map term → its best opportunity across platforms in one market."""
    out: Dict[str, int] = {}
    for k in keywords or []:
        term = str(k.get("term", ""))
        if not term:
            continue
        opp = int(k.get("opportunity", 0))
        if opp > out.get(term, -1):
            out[term] = opp
    return out


def compare_markets(per_market: Sequence[Mapping], *, top: int = 40) -> Dict:
    """Compare keyword opportunity across markets.

    ``per_market`` is a list of ``{"country": str, "keywords": [...]}``. Returns::

        {"countries": [...],
         "rows": [{"term", "by_country": {cc: opp}, "max_opp", "markets",
                   "gap": bool, "gap_note": str}, ...],
         "market_specific": {cc: [terms strong here but weak elsewhere]}}

    Rows are sorted by ``(-max_opp, term)`` and capped at ``top``.
    """
    countries = [str(m.get("country", "")) for m in per_market if m.get("country")]
    per = {str(m.get("country", "")): _best_opp_by_term(m.get("keywords", [])) for m in per_market}

    all_terms = sorted({t for opp in per.values() for t in opp})
    rows: List[Dict] = []
    market_specific: Dict[str, List[str]] = {c: [] for c in countries}
    for term in all_terms:
        by_country = {c: int(per[c].get(term, 0)) for c in countries}
        max_opp = max(by_country.values()) if by_country else 0
        if max_opp <= 0:
            continue
        present = [c for c in countries if by_country[c] > 0]
        strong = [c for c in countries if by_country[c] >= STRONG_OPP]
        weak = [c for c in countries if by_country[c] <= WEAK_OPP]
        gap = bool(strong) and bool(weak)
        gap_note = ""
        if gap:
            gap_note = f"stark in {', '.join(strong)} · schwach/fehlt in {', '.join(weak)}"
            for c in strong:
                market_specific[c].append(term)
        rows.append({
            "term": term,
            "by_country": by_country,
            "max_opp": max_opp,
            "markets": present,
            "gap": gap,
            "gap_note": gap_note,
        })
    rows.sort(key=lambda r: (-r["max_opp"], r["term"]))
    for c in market_specific:
        # keep each market's specific terms ordered by its own opportunity
        market_specific[c] = sorted(
            set(market_specific[c]), key=lambda t: (-per[c].get(t, 0), t)
        )[:15]
    return {
        "countries": countries,
        "rows": rows[:top],
        "market_specific": market_specific,
    }


def render_html(comparison: Mapping, *, app_name: str, generated: str) -> str:
    """A small self-contained HTML page for the cross-market comparison."""
    def esc(t):
        return (str(t).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))

    countries = comparison.get("countries", [])
    rows = comparison.get("rows", [])
    css = (
        "body{font-family:-apple-system,system-ui,Segoe UI,Roboto,sans-serif;margin:0;"
        "background:#F2F2F5;color:#1D1D1F}.s{max-width:1000px;margin:0 auto;padding:32px 22px}"
        ".card{background:#fff;border:1px solid #E6E6EA;border-radius:16px;padding:24px;"
        "box-shadow:0 1px 2px rgba(0,0,0,.04),0 4px 16px rgba(0,0,0,.05);margin-bottom:18px}"
        "h1{font-size:1.6rem;letter-spacing:-.02em;margin:0 0 4px}.ey{color:#4646C0;font-size:.7rem;"
        "font-weight:700;letter-spacing:.04em;text-transform:uppercase}.meta{color:#6E6E73;font-size:.8rem}"
        "table{width:100%;border-collapse:collapse;font-size:.85rem}th{text-align:left;padding:8px 10px;"
        "border-bottom:1px solid #D7D7DC;font-size:.7rem;text-transform:uppercase;color:#6E6E73}"
        "td{padding:8px 10px;border-bottom:1px solid #E6E6EA}.num{text-align:right;font-variant-numeric:tabular-nums}"
        ".gap{background:#FBEFDE}.tag{background:#FBEFDE;color:#7A4E12;font-size:.7rem;padding:1px 7px;border-radius:999px}"
        ".chip{display:inline-block;background:#EDEDFB;color:#4646C0;font-weight:600;font-size:.72rem;"
        "padding:3px 10px;border-radius:999px;margin-right:6px}"
    )
    head_cells = "".join(f"<th class='num'>{esc(c)}</th>" for c in countries)
    body = []
    for r in rows:
        cls = " class='gap'" if r["gap"] else ""
        cells = "".join(f"<td class='num'>{r['by_country'].get(c, 0)}</td>" for c in countries)
        note = f"<span class='tag'>{esc(r['gap_note'])}</span>" if r["gap"] else ""
        body.append(f"<tr{cls}><td>{esc(r['term'])}</td>{cells}<td>{note}</td></tr>")
    spec = []
    for c, terms in (comparison.get("market_specific") or {}).items():
        if terms:
            spec.append(f"<p><span class='chip'>{esc(c)}</span> {esc(', '.join(terms))}</p>")
    return (
        "<!DOCTYPE html><html lang='de'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>Markt-Vergleich — {esc(app_name)}</title><style>{css}</style></head><body><div class='s'>"
        f"<div class='card'><div class='ey'>ASO · Markt-Vergleich</div>"
        f"<h1>{esc(app_name)}</h1><div class='meta'>Erstellt: {esc(generated)} · Märkte: {esc(', '.join(countries))}</div></div>"
        "<div class='card'><div class='ey'>Pro Markt</div><h2 style='margin:.2rem 0 1rem'>Keyword-Chance je Markt</h2>"
        f"<table><thead><tr><th>Keyword</th>{head_cells}<th>Hinweis</th></tr></thead><tbody>{''.join(body)}</tbody></table>"
        "<p class='meta' style='margin-top:12px'>Gelb = Markt-Lücke: in einem Markt stark, im anderen schwach/fehlend → "
        "Lokalisierungs-Hebel.</p></div>"
        + (f"<div class='card'><div class='ey'>Markt-spezifisch</div>"
           f"<h2 style='margin:.2rem 0 1rem'>Stark in genau einem Markt</h2>{''.join(spec)}</div>" if spec else "")
        + "</div></body></html>"
    )
