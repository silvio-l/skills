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

CLI usage (slice 02+):
    python3 slop_scanner.py <file_path> --lang de|en|auto [--lexicon-dir <dir>]

Backwards-compatible legacy usage (slice 01):
    python3 slop_scanner.py <file_path> <lexicon_json>

Output (slice 02+):
  JSON object on stdout:
    {
      "language": "de",      # detected or forced language
      "findings": [...]      # sorted findings array, same shape as slice 01
    }

  Slice-01 legacy CLI (two-positional-arg form) emits a plain JSON array for
  backwards compatibility with existing tests/consumers.

Language detection (--lang auto):
  Heuristic: count umlauts (ä, ö, ü, Ä, Ö, Ü, ß) and a small set of
  high-frequency DE stopwords in the file text. If the normalised score
  exceeds a threshold (0.002 per character), classify as "de"; otherwise "en".
  Clear DE texts (with umlauts or common DE stopwords) score well above the
  threshold; clear EN texts score zero or near-zero.

Style modelled after seo-audit/scripts/brand_scan.py (word-boundary
matching, sorted JSON output).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


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
        # re.escape handles special chars (ü, ä, ö, spaces, apostrophes …).
        # For multi-word phrases the \b anchors sit at the outer edges only,
        # so spaces within the phrase match literally.
        # Note on apostrophes: \b before a word starting with an apostrophe
        # (e.g. "it's") matches at the space before "it", so the phrase
        # "it's worth noting" is enclosed by \b…\b correctly because the
        # leading \b matches at the boundary before 'i' and the trailing \b
        # matches after 'g' in 'noting'.
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
# Language detection
# ---------------------------------------------------------------------------

# High-frequency DE stopwords (lowercase); chosen to be absent from EN.
_DE_STOPWORDS = frozenset([
    "und", "der", "die", "das", "in", "ist", "zu", "den", "des",
    "mit", "wir", "auf", "für", "nicht", "auch", "an", "es",
    "sich", "ein", "eine", "als", "von", "im", "bei", "haben",
    "wird", "sind", "durch", "gibt", "nach", "mehr",
])

# Umlaut chars (case-insensitive matching done via lower())
_UMLAUT_RE = re.compile(r"[äöüäöüß]", re.IGNORECASE)


def detect_language(text: str) -> str:
    """Return 'de' or 'en' using a dependency-free heuristic.

    Heuristic:
    - Count umlaut characters (ä, ö, ü, Ä, Ö, Ü, ß).
    - Count occurrences of high-frequency DE stopwords (whole-word match).
    - Compute a score: (umlauts * 2 + de_stopword_hits) / max(len(text), 1).
    - Threshold 0.005: above → 'de', at or below → 'en'.

    This is conservative: a single umlaut in a short text is enough to
    classify as DE; pure EN texts have no umlauts and few DE stopwords.
    """
    lower = text.lower()

    umlaut_count = len(_UMLAUT_RE.findall(text))

    stopword_hits = 0
    for word in _DE_STOPWORDS:
        stopword_hits += len(re.findall(r"\b" + re.escape(word) + r"\b", lower))

    score = (umlaut_count * 2 + stopword_hits) / max(len(text), 1)
    return "de" if score > 0.005 else "en"


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
    Each finding has exactly the eight canonical keys.
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


def scan_file_with_language(
    file_path: str,
    lang: str,
    lexicon_dir: Optional[str] = None,
) -> Dict:
    """Scan *file_path*, auto-detect or force *lang*, return envelope dict.

    Parameters
    ----------
    file_path:
        Path to the file to scan.
    lang:
        'de', 'en', or 'auto'. 'auto' runs the heuristic detector.
    lexicon_dir:
        Directory containing lexicon.de.json and lexicon.en.json.
        Defaults to the parent directory of this script's parent.

    Returns
    -------
    {'language': 'de'|'en', 'findings': [...]}
    """
    if lexicon_dir is None:
        lexicon_dir = Path(__file__).resolve().parent.parent

    lexicon_dir = Path(lexicon_dir)

    if lang == "auto":
        with open(file_path, encoding="utf-8", errors="replace") as f:
            text = f.read()
        chosen_lang = detect_language(text)
    elif lang in ("de", "en"):
        chosen_lang = lang
    else:
        raise ValueError(f"lang must be 'de', 'en', or 'auto'; got {lang!r}")

    lexicon_path = lexicon_dir / f"lexicon.{chosen_lang}.json"
    if not lexicon_path.is_file():
        raise FileNotFoundError(f"Lexicon file not found: {lexicon_path}")

    with open(lexicon_path, encoding="utf-8") as f:
        lexicon = json.load(f)

    findings = scan_file(file_path, lexicon)
    return {"language": chosen_lang, "findings": findings}


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    # ---------------------------------------------------------------------------
    # Legacy slice-01 mode: two positional args (file_path lexicon_json).
    # Detected when the second argument looks like a .json file path and
    # no --lang flag is present. Emits a plain JSON array for backwards compat.
    # ---------------------------------------------------------------------------
    if (
        len(argv) == 2
        and not argv[0].startswith("-")
        and not argv[1].startswith("-")
        and argv[1].endswith(".json")
    ):
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

    # ---------------------------------------------------------------------------
    # Slice-02+ mode: argparse with --lang and --lexicon-dir.
    # ---------------------------------------------------------------------------
    parser = argparse.ArgumentParser(
        prog="slop_scanner.py",
        description="Deterministic slop scanner (bilingual DE/EN).",
    )
    parser.add_argument("file_path", help="Path to the file to scan.")
    parser.add_argument(
        "--lang",
        choices=["de", "en", "auto"],
        default="auto",
        help="Language to use: 'de', 'en', or 'auto' (heuristic). Default: auto.",
    )
    parser.add_argument(
        "--lexicon-dir",
        default=None,
        help=(
            "Directory containing lexicon.de.json and lexicon.en.json. "
            "Defaults to the skill's own data directory."
        ),
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 1

    file_path = args.file_path
    if not Path(file_path).is_file():
        print(f"Error: input file not found: {file_path}", file=sys.stderr)
        return 1

    try:
        result = scan_file_with_language(
            file_path=file_path,
            lang=args.lang,
            lexicon_dir=args.lexicon_dir,
        )
    except FileNotFoundError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
