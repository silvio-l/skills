#!/usr/bin/env python3
"""seo-audit dispatcher (v1).

Phase order: inventory → brand-konsistenz → synthesis → write report.
External probes and push are implemented in later slices; the flags
`--quick`, `--push`, and `--compare-last` are parsed already so the
CLI surface stays stable across versions.

Usage:
    python3 audit.py --root <repo-root> [--report-dir <dir>]
                     [--dist <dist-dir>] [--quick] [--push]
                     [--compare-last]

Defaults:
    --report-dir defaults to `<root>/.scratch/seo-audit/`
    --dist       defaults to `<root>/dist/`
"""

from __future__ import annotations

import argparse
import datetime
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import inventory as INV  # noqa: E402
import glossary_parser as GP  # noqa: E402
import brand_scan as BS  # noqa: E402
import synthesis as SY  # noqa: E402

GENERATOR_VERSION = "v1.0.0"
TEMPLATE_PATH = os.path.join(
    os.path.dirname(HERE), "templates", "report.md"
)


def _load_template() -> str:
    with open(TEMPLATE_PATH, "r", encoding="utf-8") as f:
        return f.read()


def _render_findings_by_category(synth: dict) -> str:
    if not synth["findings"]:
        return "_Keine Findings._"
    by_cat: dict = {}
    for f in synth["findings"]:
        by_cat.setdefault(f["category"], []).append(f)
    parts = []
    for cat in sorted(by_cat):
        parts.append(f"### {cat}\n")
        parts.append(
            "| Score | Datei:Zeile | Match | Vorschlag | Begründung |\n"
            "| ----- | ----------- | ----- | --------- | ---------- |"
        )
        for f in by_cat[cat]:
            loc = f"`{f['file_path']}:{f['line_number']}`"
            parts.append(
                f"| {f['score']} | {loc} | `{f['match']}` | "
                f"{f.get('suggested_replacement', '')} | "
                f"{f.get('rationale', '')} |"
            )
        parts.append("")
    return "\n".join(parts).rstrip()


def _render_recommendations(synth: dict) -> str:
    if not synth["findings"]:
        return "_Nichts zu tun — sauberer Lauf._"
    lines = []
    for i, f in enumerate(synth["findings"][:10], start=1):
        lines.append(
            f"{i}. **{f['match']}** in `{f['file_path']}:{f['line_number']}` "
            f"(Score {f['score']}) — ersetzen durch "
            f"**{f.get('suggested_replacement', '?')}**."
        )
    if len(synth["findings"]) > 10:
        lines.append(f"\n_(+{len(synth['findings']) - 10} weitere Findings.)_")
    return "\n".join(lines)


def _render_diff(prior_path: str | None) -> str:
    if not prior_path:
        return "_Kein vorheriger Lauf zum Vergleich._"
    return f"_Vergleich gegen `{os.path.basename(prior_path)}` (TBD)._"


def _summary_prose(synth: dict, inv: dict) -> str:
    if not synth["findings"]:
        return (
            f"Der Lauf gegen `{inv['root']}` ist sauber — kein Anti-Vokabular "
            f"im gebauten HTML."
        )
    top = synth["findings"][0]
    return (
        f"Top-Befund: `{top['match']}` in "
        f"`{top['file_path']}:{top['line_number']}` (Score {top['score']}). "
        f"Empfohlener Ersatz: **{top.get('suggested_replacement', '?')}**."
    )


def _previous_report(report_dir: str, today: str) -> str | None:
    if not os.path.isdir(report_dir):
        return None
    prior = sorted(
        f for f in os.listdir(report_dir)
        if f.startswith("seo-audit-") and f.endswith(".md")
        and not f.startswith(f"seo-audit-{today}")
    )
    return os.path.join(report_dir, prior[-1]) if prior else None


def _render(template: str, ctx: dict) -> str:
    out = template
    for key, val in ctx.items():
        out = out.replace("{{" + key + "}}", str(val))
    return out


def run(args: argparse.Namespace) -> int:
    root = os.path.abspath(args.root)
    if not os.path.isdir(root):
        print(f"error: --root does not exist: {root}", file=sys.stderr)
        return 2

    dist = args.dist or os.path.join(root, "dist")
    report_dir = args.report_dir or os.path.join(root, ".scratch", "seo-audit")
    os.makedirs(report_dir, exist_ok=True)

    inv = INV.inventory(root)
    glossary = GP.load_glossary_from_repo(root)

    findings = []
    if os.path.isdir(dist):
        for f in BS.scan_directory(dist, glossary):
            f = dict(f)
            f.setdefault("category", "brand")
            f.setdefault("severity", "med")
            f.setdefault("user_impact", 2)
            f.setdefault("fix_effort", 1)
            findings.append(f)

    # External probes deliberately skipped in v1 — --quick is a no-op
    # today, becomes meaningful in slice 02.
    _ = args.quick

    synth = SY.synthesize(findings)

    today = datetime.date.today().strftime("%Y-%m-%d")
    prior = _previous_report(report_dir, today) if args.compare_last else None

    if not synth["groups"]:
        top_category = "-"
    else:
        top_category = max(synth["groups"], key=lambda g: g["count"])["category"]

    ctx = {
        "date": today,
        "root": inv["root"],
        "framework": inv["framework"] or "unknown",
        "domain_doc": inv["domain_doc"] or "(none)",
        "pages_count": len(inv["pages"]),
        "glossary_count": len(glossary),
        "findings_count": len(synth["findings"]),
        "top_category": top_category,
        "summary_prose": _summary_prose(synth, inv),
        "findings_by_category": _render_findings_by_category(synth),
        "diff_section": _render_diff(prior),
        "recommendations": _render_recommendations(synth),
        "generator_version": GENERATOR_VERSION,
    }

    rendered = _render(_load_template(), ctx)
    out_path = os.path.join(report_dir, f"seo-audit-{today}.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered)
    print(out_path)

    if args.push:
        print("warning: --push is implemented in slice 03; ignoring.",
              file=sys.stderr)

    return 0


def parse_args(argv) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        prog="seo-audit",
        description="Local-first SEO audit: inventory, brand-konsistenz, "
                    "synthesis, report.",
    )
    p.add_argument("--root", required=True,
                   help="Repository root to audit.")
    p.add_argument("--dist", default=None,
                   help="Built HTML directory (default: <root>/dist).")
    p.add_argument("--report-dir", default=None,
                   help="Directory the report is written into "
                        "(default: <root>/.scratch/seo-audit).")
    p.add_argument("--quick", action="store_true",
                   help="Skip external probes (no-op in v1).")
    p.add_argument("--push", action="store_true",
                   help="Enable push module (slice 03; no-op in v1).")
    p.add_argument("--compare-last", action="store_true",
                   help="Diff against the most recent prior report.")
    return p.parse_args(argv)


def main(argv=None) -> int:
    return run(parse_args(argv if argv is not None else sys.argv[1:]))


if __name__ == "__main__":
    sys.exit(main())
