#!/usr/bin/env python3
"""Deterministic slop scanner for humanize-text skill.

Reads a text/markdown file and a lexicon JSON, matches patterns
case-insensitively using word-boundary anchors, and emits one Finding
per match.

Multiple matches on the same line produce multiple findings with the same
`line_number`. Output is sorted by `(file_path, line_number, pattern_id)`.

Finding shape (canonical — all subsequent slices reuse this contract):
  file_path             str  — path passed on the CLI
  line_number           int  — 1-based line number
  match                 str  — actual matched substring (case-preserved)
  pattern_id            str  — lexicon entry id
  type                  str  — "word" | "phrase"
  tier                  int  — severity tier (1 = always replace)
  suggested_replacement str  — may be "" if lexicon omits it
  rationale             str  — human-readable explanation

Usage (CLI):
    python3 slop_scanner.py <file_path> <lexicon_json>

Output: JSON array on stdout, sorted, UTF-8, indent=2.

Style modelled after seo-audit/scripts/brand_scan.py (word-boundary
matching, sorted JSON output).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Dict, List


# ---------------------------------------------------------------------------
# Lexicon compilation
# ---------------------------------------------------------------------------

def _compile_lexicon(lexicon: List[Dict]) -> List[Dict]:
    """Pre-compile regex patterns from lexicon entries."""
    compiled = []
    for entry in lexicon:
        raw_pattern = entry.get("pattern", "").strip()
        if not raw_pattern:
            continue
        # Word-boundary + case-insensitive.
        # re.escape handles special chars (ü, ä, ö, spaces …) safely.
        # For multi-word phrases the \b anchors sit at the outer edges only,
        # so spaces within the phrase match literally.
        regex = re.compile(
            r"\b" + re.escape(raw_pattern) + r"\b",
            re.IGNORECASE,
        )
        compiled.append({
            "regex": regex,
            "pattern_id": entry["pattern_id"],
            "type": entry.get("type", "word"),
            "tier": int(entry.get("tier", 1)),
            "suggested_replacement": entry.get("suggested_replacement", ""),
            "rationale": entry.get("rationale", ""),
        })
    return compiled


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_file(file_path: str, lexicon: List[Dict]) -> List[Dict]:
    """Scan *file_path* with *lexicon* and return sorted findings.

    Parameters
    ----------
    file_path:
        Path to the text/markdown/plaintext file to scan.
    lexicon:
        List of dicts loaded from a lexicon JSON (e.g. lexicon.de.json).

    Returns
    -------
    List of finding dicts sorted by (file_path, line_number, pattern_id).
    """
    compiled = _compile_lexicon(lexicon)
    if not compiled:
        return []

    with open(file_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    findings: List[Dict] = []

    for lineno, raw in enumerate(lines, start=1):
        for spec in compiled:
            for m in spec["regex"].finditer(raw):
                findings.append({
                    "file_path": file_path,
                    "line_number": lineno,
                    "match": m.group(0),
                    "pattern_id": spec["pattern_id"],
                    "type": spec["type"],
                    "tier": spec["tier"],
                    "suggested_replacement": spec["suggested_replacement"],
                    "rationale": spec["rationale"],
                })

    # Deterministic sort: (file_path, line_number, pattern_id)
    findings.sort(key=lambda f: (f["file_path"], f["line_number"], f["pattern_id"]))
    return findings


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    if len(argv) < 2:
        print("usage: slop_scanner.py <file_path> <lexicon_json>", file=sys.stderr)
        return 1

    file_path = argv[0]
    lexicon_path = argv[1]

    if not Path(lexicon_path).is_file():
        print(f"Error: lexicon file not found: {lexicon_path}", file=sys.stderr)
        return 1

    if not Path(file_path).is_file():
        print(f"Error: input file not found: {file_path}", file=sys.stderr)
        return 1

    with open(lexicon_path, encoding="utf-8") as f:
        lexicon = json.load(f)

    findings = scan_file(file_path, lexicon)
    print(json.dumps(findings, ensure_ascii=False, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
