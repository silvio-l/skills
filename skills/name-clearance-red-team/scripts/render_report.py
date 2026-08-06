#!/usr/bin/env python3
"""
Deterministic report renderer. Reads every artifact in a run's working
directory and renders report.md (+ report.html with --html); --mode handoff
additionally renders lawyer-handoff.md. Never re-implements band/gate/verdict
logic — everything risk-relevant comes from risk_model.py. See REPORTING.md
for the section layout this mirrors.

Usage: python3 render_report.py <workdir> --mode deep|quick|launch|handoff [--html]
"""
import argparse
import datetime
import html
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).parent))
import risk_model  # noqa: E402

REGISTRABILITY_LABEL = {
    "GREEN": "No absolute-grounds concerns identified.",
    "YELLOW": "Minor descriptive/weak-distinctiveness concerns — see findings.",
    "ORANGE": "Material registrability risk — a graphic/composite mark may not save this.",
    "RED": "Very likely refusal on absolute grounds as filed.",
    "BLACK": "Very likely refusal on absolute grounds as filed.",
}

BAND_BADGE = {"GREEN": "🟢", "YELLOW": "🟡", "ORANGE": "🟠", "RED": "🔴", "BLACK": "⚫"}


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def load_json(path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_workdir(workdir):
    workdir = pathlib.Path(workdir)
    profile = load_json(workdir / "profile.json", {})
    variants = load_json(workdir / "variants.json", {})
    digital = load_json(workdir / "digital-availability.json", {"records": []})
    redteam = load_json(workdir / "redteam.json", {})

    rows_by_key = {}
    plan = load_json(workdir / "searchlog" / "_plan.json", {"rows": []})
    for row in plan.get("rows", []):
        rows_by_key[(row.get("query"), row.get("source_id"), row.get("territory"), row.get("cluster_id"))] = row

    searchlog_dir = workdir / "searchlog"
    if searchlog_dir.exists():
        for path in sorted(searchlog_dir.glob("*.json")):
            if path.name == "_plan.json":
                continue
            for row in load_json(path, []):
                key = (row.get("query"), row.get("source_id"), row.get("territory"), row.get("cluster_id"))
                rows_by_key[key] = row
    searchlog_rows = list(rows_by_key.values())

    findings = []
    findings_dir = workdir / "findings"
    if findings_dir.exists():
        for path in sorted(findings_dir.glob("*.json")):
            findings.extend(load_json(path, []))

    return profile, variants, digital, searchlog_rows, findings, redteam


def md_table(headers, rows):
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(["---"] * len(headers)) + "|"]
    for row in rows:
        lines.append("| " + " | ".join(str(c) for c in row) + " |")
    return "\n".join(lines)


def territorial_coverage(profile, searchlog_rows):
    territories = profile.get("target_territories") or []
    categories = sorted({r.get("source_category") for r in searchlog_rows if r.get("source_category")})
    rows = []
    for territory in territories:
        for category in categories:
            subset = [r for r in searchlog_rows if r.get("territory") == territory and r.get("source_category") == category]
            if not subset:
                rows.append((territory, category, "not searched", "0"))
                continue
            counts = {}
            for r in subset:
                counts[r.get("status", "?")] = counts.get(r.get("status", "?"), 0) + 1
            status_str = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
            worst = "blocked" if any(r.get("status") == "blocked" for r in subset) else (
                "completed" if all(r.get("status") == "completed" for r in subset) else "partial"
            )
            rows.append((territory, category, worst, status_str))
        if not categories:
            rows.append((territory, "—", "not searched", "0"))
    return rows


def missing_and_how_to_complete(gates, searchlog_rows):
    lines = []
    open_gates = [(name, g) for name, g in gates.items() if not g["value"]]
    if open_gates:
        lines.append("### Open gates")
        for name, g in open_gates:
            lines.append(f"- **{name}**: {g['reason']}")
    unresolved = [r for r in searchlog_rows if r.get("status") in ("blocked", "pending_user_verification", "not_attempted")]
    if unresolved:
        lines.append("\n### Lookups to complete manually")
        for r in unresolved:
            mi = r.get("manual_instructions") or {}
            lines.append(
                f"- **{r.get('source_id')}** ({r.get('territory')}, `{r.get('status')}`"
                f"{', ' + r.get('block_reason') if r.get('block_reason') else ''}): "
                f"query `{r.get('query')}`"
                + (f" — URL: {mi.get('url')}" if mi.get("url") else "")
                + (f", search string: `{mi.get('search_string')}`" if mi.get("search_string") else "")
                + (f", filters: {mi.get('filters')}" if mi.get("filters") else "")
            )
    return "\n".join(lines) if lines else "_Nothing outstanding._"


def render_finding_row(f):
    sim = f.get("similarity") or {}
    return (
        f.get("id", "?"), f.get("territory", "?"), f.get("category", "?"),
        f.get("mark_or_name", "—"), f.get("owner", "—"),
        f"v{sim.get('visual', '—')}/p{sim.get('phonetic', '—')}/c{sim.get('conceptual', '—')}" if sim else "—",
        f.get("goods_proximity", "—"),
        risk_model.band_for_finding(f), risk_model.cap_evidence_quality(f),
    )


def render_markdown(profile, variants, digital, searchlog_rows, findings, redteam, mode):
    gates = risk_model.derive_gates(profile, variants, searchlog_rows, findings, redteam)
    band, dominating_id, reason = risk_model.overall_band(findings)
    verdict = risk_model.verdict_for(band, mode, gates, searchlog_rows)

    name = profile.get("name", "?")
    lines = [f"# Name Clearance Report — {name}", ""]
    lines.append(f"Generated: {now_iso()} · Mode: {mode}")
    lines.append("")
    lines.append(
        "This is a preliminary, deliberately conservative screening. It is not "
        "legal advice and does not guarantee freedom to use this name anywhere in "
        "the world. A LAWYER CLEARANCE REQUIRED or DO NOT USE verdict, or any "
        "hard-stop finding, should be reviewed by a qualified trademark/legal "
        "professional before this name is used, filed, or invested in further."
    )
    lines.append("")

    if mode == "quick":
        lines.append(f"## Quick Scan result: {verdict}")
        lines.append("")
        lines.append(
            "A Quick Scan is never a green light — it only tells you whether a full "
            "Deep Clearance is warranted, likely to end in a rename, or should stop "
            "immediately."
        )
    else:
        lines.append(f"## Freedom-to-use verdict: {BAND_BADGE.get(band, '')} {verdict}")
        lines.append(f"Dominating finding: `{dominating_id}` — {reason}" if dominating_id else "No adverse findings on record.")
        lines.append("")
        absolute_findings = [f for f in findings if f.get("category") == "absolute_ground"]
        reg_band, _, _ = risk_model.overall_band(absolute_findings)
        lines.append(f"## Registrability assessment: {BAND_BADGE.get(reg_band, '')} {REGISTRABILITY_LABEL[reg_band]}")
        lines.append(
            "_Registrability (can this be filed as a mark at all) and freedom-to-use "
            "(does using it collide with someone else's rights) are separate questions "
            "— a name can be perfectly registrable and still infringe, or refused "
            "registration yet still safe to use as an unregistered business name._"
        )
        lines.append("")

    lines.append("## Assumptions")
    assumptions = profile.get("assumptions") or []
    if assumptions:
        lines.extend(f"- **{a.get('field')}** = `{a.get('assumed_value')}` — {a.get('reason')}" for a in assumptions)
    else:
        lines.append("_None recorded._")
    lines.append("")

    lines.append("## Territorial coverage")
    coverage_rows = territorial_coverage(profile, searchlog_rows)
    if coverage_rows:
        lines.append(md_table(["Territory", "Source category", "Status", "Detail"], coverage_rows))
    else:
        lines.append("_No search plan on record._")
    lines.append("")

    lines.append("## Findings")
    if findings:
        lines.append(md_table(
            ["id", "territory", "category", "mark/name", "owner", "similarity v/p/c", "goods proximity", "band", "evidence quality"],
            [render_finding_row(f) for f in findings],
        ))
        lines.append("")
        for f in findings:
            lines.append(f"### `{f.get('id')}` — {f.get('summary', '')}")
            lines.append(f"- **Strongest counter-argument:** {f.get('strongest_counter_argument', '—')}")
            evidence = f.get("evidence") or []
            for e in evidence:
                lines.append(f"- Evidence: {e.get('url') or e.get('register_id') or '—'} — {e.get('description', '')}")
            lines.append("")
    else:
        lines.append("_No findings recorded._")
    lines.append("")

    if mode in ("deep", "launch", "handoff"):
        lines.append("## Digital availability")
        records = digital.get("records") or []
        if records:
            lines.append(md_table(
                ["identifier", "status", "method", "reason"],
                [(r.get("identifier"), r.get("status"), r.get("method"), r.get("reason")) for r in records],
            ))
        else:
            lines.append("_Not checked._")
        lines.append("")

        lines.append("## Red team")
        attacks = redteam.get("attacks") or []
        if attacks:
            for a in attacks:
                lines.append(f"- **{a.get('vector')}** (severity {a.get('severity')}): {a.get('argument')}")
                lines.append(f"  - Rebuttal: {a.get('rebuttal')}")
        else:
            lines.append("_Not yet run._")
        missed = redteam.get("missed_vectors") or []
        if missed:
            lines.append("\n### Missed vectors reopened for research")
            for v in missed:
                lines.append(f"- {v.get('vector')} (severity {v.get('severity')}) — resolution: {v.get('resolution') or '_pending_'}")
        lines.append("")

        if mode == "launch":
            lines.append("## Launch economics")
            econ = profile.get("launch_economics") or {}
            if econ:
                for key in ("sunk_cost", "rename_cost_estimate", "coexistence_strategy", "goods_services_narrowing", "alternate_spelling_considered", "defensibility_assessment"):
                    if econ.get(key):
                        lines.append(f"- **{key.replace('_', ' ')}:** {econ[key]}")
            else:
                lines.append("_No launch-economics intake recorded._")
            lines.append("")

        lines.append("## Gate status")
        lines.append(md_table(
            ["gate", "status", "reason"],
            [(name, "✅" if g["value"] else "❌", g["reason"]) for name, g in gates.items()],
        ))
        lines.append("")

        lines.append("## What is missing and how to complete it")
        lines.append(missing_and_how_to_complete(gates, searchlog_rows))
        lines.append("")

        lines.append("## Limitations")
        lines.append(
            "- This screening never claims full worldwide coverage — only the "
            "territories and sources listed in Territorial coverage above were checked.\n"
            "- Absence of a finding is not proof of freedom to use; it means nothing "
            "adverse was found in the sources actually reached.\n"
            "- Registers with no reliable automated access (see SOURCES.md) were "
            "checked only where a completed row above says so.\n"
            "- This report expresses no opinion on jurisdictions, goods/services, or "
            "sources outside what was explicitly in scope for this run."
        )
        lines.append("")

    return "\n".join(lines)


def render_lawyer_handoff(profile, variants, searchlog_rows, findings, redteam):
    name = profile.get("name", "?")
    lines = [f"# Lawyer Handoff — {name}", "", f"Generated: {now_iso()}", ""]
    lines.append("## Context")
    lines.append(f"- Name type: {profile.get('name_type', '—')}")
    lines.append(f"- Goods/services: {'; '.join(profile.get('goods_and_services') or [])}")
    lines.append(f"- Target territories: {', '.join(profile.get('target_territories') or [])}")
    lines.append(f"- Planned use: {', '.join(profile.get('planned_use') or [])}")
    prior = profile.get("prior_events") or {}
    flagged = [k for k, v in prior.items() if k != "details" and v]
    lines.append(f"- Prior events flagged: {', '.join(flagged) if flagged else 'none'}" + (f" — {prior['details']}" if prior.get("details") else ""))
    lines.append("")

    lines.append("## Search variants used")
    for v in (variants.get("variants") or []):
        lines.append(f"- {v.get('variant')} ({v.get('class')}/{v.get('rule')})")
    lines.append("")

    lines.append("## Strongest conflicts")
    ranked = sorted(findings, key=lambda f: -risk_model._band_index(risk_model.band_for_finding(f)))
    for f in ranked[:10]:
        lines.append(f"- `{f.get('id')}` [{risk_model.band_for_finding(f)}] {f.get('mark_or_name', '—')} — {f.get('summary', '')}")
    lines.append("")

    lines.append("## Open legal questions for counsel")
    gates = risk_model.derive_gates(profile, variants, searchlog_rows, findings, redteam)
    for name_, g in gates.items():
        if not g["value"]:
            lines.append(f"- {name_}: {g['reason']}")
    for f in findings:
        if f.get("hard_stop_id"):
            lines.append(f"- `{f.get('id')}` triggers hard stop `{f.get('hard_stop_id')}` — {f.get('strongest_counter_argument', '')}")
    lines.append("")

    lines.append("## Evidence")
    for f in findings:
        for e in f.get("evidence") or []:
            lines.append(f"- [{f.get('id')}] {e.get('url') or e.get('register_id') or '—'} — {e.get('description', '')}")
    return "\n".join(lines)


def render_html(markdown_body, name, verdict, band):
    color = {"GREEN": "#1a7f37", "YELLOW": "#9a6700", "ORANGE": "#bc4c00", "RED": "#cf222e", "BLACK": "#1f2328"}.get(band, "#57606a")
    body_html = "<pre class=\"report\">" + html.escape(markdown_body) + "</pre>"
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>Name Clearance Report — {html.escape(name)}</title>
<style>
:root {{ color-scheme: light dark; }}
body {{ font-family: -apple-system, system-ui, sans-serif; max-width: 900px; margin: 2rem auto; padding: 0 1rem;
        background: #fff; color: #1f2328; }}
@media (prefers-color-scheme: dark) {{ body {{ background: #0d1117; color: #e6edf3; }} }}
.badge {{ display: inline-block; padding: 0.25rem 0.75rem; border-radius: 999px; color: #fff; background: {color};
          font-weight: 600; }}
pre.report {{ white-space: pre-wrap; word-wrap: break-word; font-family: ui-monospace, monospace; font-size: 0.85rem;
              line-height: 1.5; }}
</style></head>
<body>
<p class="badge">{html.escape(verdict)}</p>
{body_html}
</body></html>"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("workdir")
    parser.add_argument("--mode", choices=["quick", "deep", "launch", "handoff"], default="deep")
    parser.add_argument("--html", action="store_true")
    args = parser.parse_args()

    workdir = pathlib.Path(args.workdir)
    profile, variants, digital, searchlog_rows, findings, redteam = load_workdir(workdir)

    markdown = render_markdown(profile, variants, digital, searchlog_rows, findings, redteam, args.mode)
    (workdir / "report.md").write_text(markdown, encoding="utf-8")
    print(f"wrote {workdir / 'report.md'}")

    if args.html:
        gates = risk_model.derive_gates(profile, variants, searchlog_rows, findings, redteam)
        band, _, _ = risk_model.overall_band(findings)
        verdict = risk_model.verdict_for(band, args.mode, gates, searchlog_rows)
        (workdir / "report.html").write_text(render_html(markdown, profile.get("name", "?"), verdict, band), encoding="utf-8")
        print(f"wrote {workdir / 'report.html'}")

    if args.mode == "handoff":
        handoff = render_lawyer_handoff(profile, variants, searchlog_rows, findings, redteam)
        (workdir / "lawyer-handoff.md").write_text(handoff, encoding="utf-8")
        print(f"wrote {workdir / 'lawyer-handoff.md'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
