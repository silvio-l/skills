#!/usr/bin/env python3
"""humanize — entry script for the humanize-text skill (slice 05).

Wires slop_scanner + slop_scorer and exposes a unified CLI.

Usage:
    python3 humanize.py <file_path> --mode scan|score [options]

Flags:
    --mode scan|score       scan: report only (exit 0 always)
                            score: gate (exit 0 = pass, exit 1 = needs-revision)
    --threshold N           override score gate threshold (default 35/50)
    --format json|text      output format (default: json)
    --lang de|en|auto       language for scan (default: auto)
    --lexicon-dir <dir>     directory containing lexicon.*.json files

Exit codes:
    0   pass (or --mode scan always exits 0)
    1   needs-revision (--mode score only)
    2   error (bad arguments, file not found, etc.)

Output (--format json):
    --mode scan:
        {"language": "...", "findings": [...]}

    --mode score:
        {
          "language":  "...",
          "findings":  [...],           # all findings from scan
          "surfaced":  [...],           # tier-gated subset
          "tier3_density_hint": bool,
          "dimensions": {...},
          "overall":   float,
          "verdict":   "pass" | "needs-revision"
        }

Output (--format text):
    Human-readable summary for terminal use.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Resolve script directory so we can import sibling modules regardless of cwd
_SCRIPTS_DIR = Path(__file__).resolve().parent
if str(_SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS_DIR))

import slop_scanner  # noqa: E402
import slop_scorer   # noqa: E402


# ---------------------------------------------------------------------------
# Text-format renderers
# ---------------------------------------------------------------------------

def _render_scan_text(scan_result: dict) -> str:
    """Render scan result as human-readable text.

    Surfaced findings (tier-1 + tier-2 clusters) are listed individually.
    Tier-3 weak/density tells (em-dash overuse, tricolon) are NOT nagged
    per occurrence — a single em-dash is not slop — only summarised, with a
    nudge when their density is high.
    """
    lang = scan_result.get("language", "?")
    findings = scan_result.get("findings", [])
    surfaced = scan_result.get("surfaced", findings)
    tier3_hint = scan_result.get("tier3_density_hint", False)
    n_t3 = sum(1 for f in findings if f.get("tier") == 3)

    lines = [
        f"Language: {lang}",
        f"Findings: {len(findings)} total  |  "
        f"{len(surfaced)} surfaced (tier-1 + tier-2 clusters)",
    ]
    if surfaced:
        lines.append("")
        for f in surfaced:
            lines.append(
                f"  line {f['line_number']:>4}  [t{f['tier']}]  "
                f"{f['match']!r}  ({f['pattern_id']})"
            )
            if f.get("suggested_replacement"):
                lines.append(f"              → {f['suggested_replacement']}")
    else:
        lines.append("")
        lines.append("  No surfaced lexical/structural slop.")
    if n_t3:
        note = f"  Weak tells (not scored): {n_t3} em-dash/structure occurrence(s)."
        if tier3_hint:
            note += " Density is high — consider varying punctuation/rhythm."
        lines.append("")
        lines.append(note)
    return "\n".join(lines)


def _render_score_text(result: dict) -> str:
    """Render score result as human-readable text."""
    lang = result.get("language", "?")
    findings = result.get("findings", [])
    verdict = result.get("verdict", "?")
    overall = result.get("overall", 0)
    dims = result.get("dimensions", {})
    surfaced = result.get("surfaced", [])
    tier3_hint = result.get("tier3_density_hint", False)

    lines = [
        f"Language:  {lang}",
        f"Overall:   {overall:.1f}/50  →  {verdict.upper()}",
        "",
        "Dimensions:",
    ]
    for name, val in dims.items():
        bar = "█" * int(val) + "░" * (10 - int(val))
        lines.append(f"  {name:<14} {bar}  {val:.1f}/10")

    lines.append("")
    lines.append(f"Total findings: {len(findings)}  |  Surfaced: {len(surfaced)}")

    if surfaced:
        lines.append("")
        lines.append("Surfaced findings (tier-1 + tier-2 clusters):")
        for f in surfaced:
            lines.append(
                f"  line {f['line_number']:>4}  [t{f['tier']}]  "
                f"{f['match']!r}  ({f['pattern_id']})"
            )
            if f.get("suggested_replacement"):
                lines.append(f"              → {f['suggested_replacement']}")

    if tier3_hint:
        lines.append("")
        lines.append("Hint: high density of structural tells (tier-3). "
                     "Consider varying sentence rhythm.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="humanize.py",
        description="humanize — scan + score gate for the humanize-text skill.",
    )
    parser.add_argument("file_path", help="Path to the file to analyse.")
    parser.add_argument(
        "--mode",
        choices=["scan", "score"],
        default="scan",
        help="'scan' reports findings only (exit 0 always). "
             "'score' applies the quality gate (exit 0 = pass, exit 1 = needs-revision).",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=slop_scorer.DEFAULT_THRESHOLD,
        help=f"Minimum overall score to pass (default: {slop_scorer.DEFAULT_THRESHOLD}).",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format: 'json' (default) or 'text' (human-readable).",
    )
    parser.add_argument(
        "--lang",
        choices=["de", "en", "auto"],
        default="auto",
        help="Language for scanning. Default: auto (heuristic detection).",
    )
    parser.add_argument(
        "--lexicon-dir",
        default=None,
        help="Directory containing lexicon.de.json, lexicon.en.json. "
             "Defaults to the skill's own data directory.",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 2

    file_path = args.file_path
    if not Path(file_path).is_file():
        print(f"Error: file not found: {file_path}", file=sys.stderr)
        return 2

    # Determine lexicon_dir (default = skill data dir = parent of scripts/)
    lexicon_dir = args.lexicon_dir or str(Path(__file__).resolve().parent.parent)

    # --- Step 1: scan ---
    try:
        scan_result = slop_scanner.scan_file_with_language(
            file_path=file_path,
            lang=args.lang,
            lexicon_dir=lexicon_dir,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2

    if args.mode == "scan":
        # Apply tier gating so scan output mirrors the score gate: tier-1 always,
        # tier-2 only in clusters, tier-3 (em-dash/structure) as a density hint.
        with open(file_path, encoding="utf-8", errors="replace") as f:
            _text = f.read()
        _wc = max(len(_text.split()), 1)
        _gating = slop_scorer.apply_tier_gating(scan_result["findings"], word_count=_wc)
        scan_out = dict(scan_result)
        scan_out["surfaced"] = _gating["surfaced_findings"]
        scan_out["tier3_density_hint"] = _gating["tier3_density_hint"]
        if args.format == "json":
            print(json.dumps(scan_out, ensure_ascii=False, indent=2, sort_keys=False))
        else:
            print(_render_scan_text(scan_out))
        return 0

    # --- Step 2: score (--mode score) ---
    # Read text for scoring (rhythm / density use word count)
    with open(file_path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    findings = scan_result["findings"]
    wc = max(len(text.split()), 1)

    score_result = slop_scorer.score(text, findings, threshold=args.threshold)
    gating = slop_scorer.apply_tier_gating(findings, word_count=wc)

    output = {
        "language": scan_result["language"],
        "findings": findings,
        "surfaced": gating["surfaced_findings"],
        "tier3_density_hint": gating["tier3_density_hint"],
        "dimensions": score_result["dimensions"],
        "overall": score_result["overall"],
        "verdict": score_result["verdict"],
    }

    if args.format == "json":
        print(json.dumps(output, ensure_ascii=False, indent=2, sort_keys=False))
    else:
        print(_render_score_text(output))

    return 0 if score_result["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
