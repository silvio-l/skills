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
  type                  str  — "word" | "phrase" | "punctuation" | "structure"
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

Slice 03 additions (structure_patterns.json):
  scan_file_with_structure(file_path, structure_dir=None) scans for
  punctuation and sentence-structure tells that are language-neutral:
  - Em-dash (U+2014)  → type: "punctuation", tier 1 (surfaced)
  - Negative parallelism → type: "structure", tier 2 (surfaced)
  - Tricolon/rule-of-three → tier 3, NOT surfaced. A rhetorical rule-of-three
    cannot be reliably told apart from an ordinary three-item enumeration with
    surface heuristics, so no individual finding is emitted; the tell is kept in
    structure_patterns.json (surfaced=false) for a future density-based pass.
  Patterns are loaded from structure_patterns.json alongside the lexica.
  These findings merge into the same sorted list as word/phrase findings
  inside the slice-02 envelope.

Slice 04 additions (filetype strip strategies + suppression markers):
  File type is detected by extension and the appropriate strip strategy applied:
  - .md and unknown extensions: scanned as-is (current behaviour, plain text).
  - .html and .astro: <script> and <style> block contents are blanked to empty
    lines (line-count preserved), then HTML tags are stripped per line.
  - .ts and .astro: the string values of `de` and `en` keys inside a `summary`
    object literal are extracted and scanned as text; all other code is ignored.
    For .astro both strategies are applied (HTML body + summary extraction).
  Suppression markers (humanize's OWN syntax, distinct from seo-audit's):
  - Per-file: <!-- humanize:ignore-file --> anywhere in the file → whole file
    is skipped.
  - Section: <!-- humanize:ignore --> ... <!-- /humanize:ignore --> → lines
    inside the block are not scanned. A missing closing marker suppresses to
    end of file.
  These markers deliberately use the prefix "humanize:" and differ from
  seo-audit's "seo-audit:" prefix (<!-- seo-audit:contrastive --> etc.).

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
# Slice 04: Suppression markers
# ---------------------------------------------------------------------------
# These markers are deliberately distinct from seo-audit's markers:
#   seo-audit uses: <!-- seo-audit:contrastive --> / <!-- /seo-audit:contrastive -->
#   humanize uses:  <!-- humanize:ignore -->        / <!-- /humanize:ignore -->
#   humanize per-file: <!-- humanize:ignore-file -->

_HUMANIZE_OPEN_RE = re.compile(
    r"<!--\s*humanize:ignore\s*-->",
    re.IGNORECASE,
)
_HUMANIZE_CLOSE_RE = re.compile(
    r"<!--\s*/humanize:ignore\s*-->",
    re.IGNORECASE,
)
_HUMANIZE_FILE_IGNORE_RE = re.compile(
    r"<!--\s*humanize:ignore-file\s*-->",
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Slice 04: HTML/Astro strip helpers (mirroring seo-audit/scripts/brand_scan.py)
# ---------------------------------------------------------------------------

_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)


def _strip_script_style_preserving_lines(text: str) -> str:
    """Replace <script>/<style> block contents with blank lines.

    Newlines inside the stripped block are kept so subsequent line
    numbers stay aligned with the source file.
    """
    def repl(m: re.Match) -> str:
        body = m.group(0)
        return "\n" * body.count("\n")
    return _SCRIPT_STYLE_RE.sub(repl, text)


def _strip_tags(line: str) -> str:
    """Lossy per-line tag stripping for matching. Keeps text positions."""
    return re.sub(r"<[^>]+>", " ", line)


# ---------------------------------------------------------------------------
# Slice 04: TypeScript/Astro summary field extraction
# ---------------------------------------------------------------------------
# Conservative regex: finds  summary: {  ... de: '<value>' ... en: '<value>' ...  }
# Limits: does not handle nested braces inside summary, multi-line string
# continuations via template literals, or dynamic values. See module docstring.

_SUMMARY_BLOCK_RE = re.compile(
    r"\bsummary\s*:\s*\{([^}]*)\}",
    re.DOTALL,
)
_SUMMARY_FIELD_RE = re.compile(
    r"""\b(de|en)\s*:\s*(?:'([^']*)'|"([^"]*)")""",
)


def _extract_summary_lines(source: str) -> List[tuple]:
    """Extract (line_number, text) tuples for summary { de, en } string values.

    Scans *source* for `summary: { de: '...', en: '...' }` blocks and returns
    the line number (1-based, pointing to the line in *source* where the field
    literal begins) and the string value for each de/en field found.

    Limits (documented): only handles single- and double-quoted string literals;
    does not handle template literals, computed keys, or nested braces inside
    the summary object.
    """
    results = []
    lines = source.splitlines(keepends=True)

    for block_m in _SUMMARY_BLOCK_RE.finditer(source):
        block_content = block_m.group(1)
        block_start_pos = block_m.start(1)  # absolute offset of block body start

        for field_m in _SUMMARY_FIELD_RE.finditer(block_content):
            # Determine the string value (single- or double-quoted)
            value = field_m.group(2) if field_m.group(2) is not None else field_m.group(3)
            if not value:
                continue
            # Absolute offset of the field match within source
            abs_offset = block_start_pos + field_m.start()
            # Convert to 1-based line number
            line_number = source[:abs_offset].count("\n") + 1
            results.append((line_number, value))
    return results


# ---------------------------------------------------------------------------
# Slice 04: filetype detection
# ---------------------------------------------------------------------------

def _detect_file_strategy(file_path: str) -> str:
    """Return the strip strategy for *file_path* based on its extension.

    Returns one of: 'plain', 'html', 'ts', 'astro'.
    """
    ext = Path(file_path).suffix.lower()
    if ext in (".html", ".htm"):
        return "html"
    if ext == ".astro":
        return "astro"
    if ext == ".ts":
        return "ts"
    # .md and everything else treated as plain text
    return "plain"


# ---------------------------------------------------------------------------
# Slice 04: suppression-aware line-level scanner
# ---------------------------------------------------------------------------

def _has_file_ignore_marker(text: str) -> bool:
    """Return True if *text* contains a per-file humanize:ignore-file marker."""
    return bool(_HUMANIZE_FILE_IGNORE_RE.search(text))


def _scan_lines_with_suppression(
    lines: List[str],
    file_path: str,
    compiled: List[Dict],
) -> List[Dict]:
    """Scan *lines* with suppression markers applied.

    Lines between <!-- humanize:ignore --> and <!-- /humanize:ignore --> are
    skipped. A missing closing marker suppresses to end of file.
    The marker lines themselves are also skipped (no findings on them).

    Parameters
    ----------
    lines:
        List of raw line strings (result of splitlines or readlines).
    file_path:
        Path to report in findings.
    compiled:
        Pre-compiled lexicon entries from _compile_lexicon().

    Returns
    -------
    Unsorted list of findings (caller must sort).
    """
    findings: List[Dict] = []
    suppressed = False

    for lineno, raw in enumerate(lines, start=1):
        # Toggle suppression — check BEFORE scanning this line so marker
        # lines themselves never produce findings.
        if _HUMANIZE_OPEN_RE.search(raw):
            suppressed = True
        if suppressed:
            if _HUMANIZE_CLOSE_RE.search(raw):
                suppressed = False
            continue

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
    return findings


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
        #
        # Optional inflection (entry key "inflect": true): the trailing \b is
        # replaced by \w*\b so additive suffixes are captured. This is meant
        # for German adjectives/participles whose declension endings are purely
        # additive (nahtlos → nahtlose/nahtlosen/nahtloser …). It is NOT enabled
        # by default and deliberately not used for English, where common forms
        # drop a stem letter (leverage → leveraging) and \w* would miss them
        # anyway while over-matching unrelated words. inflect is ignored for
        # multi-word phrases (it only makes sense on a single token).
        inflect = bool(entry.get("inflect", False)) and " " not in raw_pattern
        suffix = r"\w*\b" if inflect else r"\b"
        regex = re.compile(
            r"\b" + re.escape(raw_pattern) + suffix,
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

    Note: suppression markers (<!-- humanize:ignore --> etc.) are honoured.
    For filetype-aware scanning (.html/.astro/.ts) use scan_file_with_language().
    """
    compiled = _compile_lexicon(lexicon)
    if not compiled:
        return []

    with open(file_path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    # Per-file suppression: skip entire file
    if _has_file_ignore_marker(text):
        return []

    lines = text.splitlines(keepends=True)
    findings = _scan_lines_with_suppression(lines, file_path, compiled)

    # Deterministic sort: (file_path, line_number, pattern_id)
    findings.sort(key=lambda f: (f["file_path"], f["line_number"], f["pattern_id"]))
    return findings


def _scan_file_typed(
    file_path: str,
    compiled: List[Dict],
    strategy: str,
) -> List[Dict]:
    """Scan *file_path* using the strip strategy determined by *strategy*.

    Strategies:
      'plain'  — plain text / markdown (suppression markers only)
      'html'   — blank <script>/<style> blocks, strip tags per line
      'ts'     — extract summary { de, en } string values only
      'astro'  — apply HTML strategy on body + extract summary fields

    Parameters
    ----------
    file_path:
        Path to the file to scan.
    compiled:
        Pre-compiled lexicon entries.
    strategy:
        One of 'plain', 'html', 'ts', 'astro'.

    Returns
    -------
    Unsorted findings list.
    """
    with open(file_path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    # Per-file suppression: skip entire file
    if _has_file_ignore_marker(text):
        return []

    findings: List[Dict] = []

    if strategy == "plain":
        lines = text.splitlines(keepends=True)
        findings = _scan_lines_with_suppression(lines, file_path, compiled)

    elif strategy in ("html", "astro"):
        # Step 1: blank <script>/<style> contents (preserves line count)
        cleaned = _strip_script_style_preserving_lines(text)
        # Step 2: split into lines and apply suppression + tag stripping
        raw_lines = cleaned.splitlines(keepends=True)
        suppressed = False
        for lineno, raw in enumerate(raw_lines, start=1):
            if _HUMANIZE_OPEN_RE.search(raw):
                suppressed = True
            if suppressed:
                if _HUMANIZE_CLOSE_RE.search(raw):
                    suppressed = False
                continue
            # Strip HTML tags for matching
            line = _strip_tags(raw)
            for spec in compiled:
                for m in spec["regex"].finditer(line):
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
        # For .astro: also extract summary { de, en } fields
        if strategy == "astro":
            for lineno, value in _extract_summary_lines(text):
                for spec in compiled:
                    for m in spec["regex"].finditer(value):
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

    elif strategy == "ts":
        # Only scan summary { de, en } string values
        for lineno, value in _extract_summary_lines(text):
            for spec in compiled:
                for m in spec["regex"].finditer(value):
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

    return findings


# ---------------------------------------------------------------------------
# Structure / punctuation pattern loading and scanning (slice 03)
# ---------------------------------------------------------------------------

# Em-dash regex — matches exactly U+2014 (each occurrence independently)
_EM_DASH_RE = re.compile(r"—")

# Tricolon / rule-of-three:
# A genuine rhetorical tricolon ("A, B and C") cannot be reliably distinguished
# from an ordinary three-item enumeration ("Python, JavaScript and TypeScript")
# with surface heuristics — any regex narrow enough to avoid those false
# positives also misses most genuine tricolons. We therefore do NOT surface an
# individual finding for it; the tell is recorded in structure_patterns.json as
# a tier-3, density-only weak hint (surfaced=false) for a future aggregate pass.
# No regex/detection runs here by design.

# Negative parallelism:
# DE: "nicht nur ... sondern (auch) ..."
# EN: "not just ... but (also) ..." / "not only ... but (also) ..."
_NEG_PARALLEL_RE = re.compile(
    r"(?:"
    r"nicht\s+nur\b.{1,80}?\bsondern\s+auch\b"      # DE
    r"|"
    r"not\s+just\b.{1,80}?\bbut\s+(?:also\s+)?\b"   # EN variant 1
    r"|"
    r"not\s+only\b.{1,80}?\bbut\s+(?:also\s+)?\b"   # EN variant 2
    r")",
    re.IGNORECASE | re.DOTALL,
)


def _load_structure_patterns(structure_dir: Optional[Path] = None) -> List[Dict]:
    """Load structure_patterns.json from *structure_dir* (defaults to skill data dir)."""
    if structure_dir is None:
        structure_dir = Path(__file__).resolve().parent.parent
    path = Path(structure_dir) / "structure_patterns.json"
    if not path.is_file():
        raise FileNotFoundError(f"structure_patterns.json not found: {path}")
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def scan_file_with_structure(
    file_path: str,
    structure_dir: Optional[str] = None,
) -> List[Dict]:
    """Scan *file_path* for structure/punctuation tells.

    Loads structure_patterns.json from *structure_dir* (or the skill's own
    data dir), applies em-dash and structure heuristics line-by-line, and
    returns a sorted findings list using the canonical 8-key shape.

    The result can be merged with word/phrase findings from scan_file().

    Parameters
    ----------
    file_path:
        Path to the file to scan.
    structure_dir:
        Directory containing structure_patterns.json.
        Defaults to the skill's own data directory.

    Returns
    -------
    List of finding dicts sorted by (file_path, line_number, pattern_id).
    """
    sp_dir = Path(structure_dir) if structure_dir else None
    patterns = _load_structure_patterns(sp_dir)

    # Build lookup by pattern_id
    by_id: Dict[str, Dict] = {p["pattern_id"]: p for p in patterns}

    em_dash_spec = by_id.get("punct_em_dash", {})
    neg_par_spec = by_id.get("struct_neg_parallelism", {})

    with open(file_path, encoding="utf-8", errors="replace") as f:
        lines = f.readlines()

    findings: List[Dict] = []

    for lineno, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")

        # --- Em-dash (U+2014): one finding per occurrence ---
        if em_dash_spec:
            for m in _EM_DASH_RE.finditer(raw):
                findings.append({
                    "file_path": file_path,
                    "line_number": lineno,
                    "match": m.group(0),
                    "pattern_id": em_dash_spec["pattern_id"],
                    "type": em_dash_spec["type"],
                    "tier": int(em_dash_spec.get("tier", 1)),
                    "suggested_replacement": em_dash_spec.get("suggested_replacement", ""),
                    "rationale": em_dash_spec.get("rationale", ""),
                })

        # --- Tricolon / rule-of-three ---
        # Intentionally NOT surfaced as an individual finding (tier-3 weak hint).
        # See structure_patterns.json struct_tricolon (surfaced=false) and the
        # module-level note above for the rationale (false-positive avoidance).

        # --- Negative parallelism ---
        if neg_par_spec:
            for m in _NEG_PARALLEL_RE.finditer(line):
                findings.append({
                    "file_path": file_path,
                    "line_number": lineno,
                    "match": m.group(0),
                    "pattern_id": neg_par_spec["pattern_id"],
                    "type": neg_par_spec["type"],
                    "tier": int(neg_par_spec.get("tier", 2)),
                    "suggested_replacement": neg_par_spec.get("suggested_replacement", ""),
                    "rationale": neg_par_spec.get("rationale", ""),
                })

    findings.sort(key=lambda f: (f["file_path"], f["line_number"], f["pattern_id"]))
    return findings


def scan_file_with_language(
    file_path: str,
    lang: str,
    lexicon_dir: Optional[str] = None,
) -> Dict:
    """Scan *file_path*, auto-detect or force *lang*, return envelope dict.

    Filetype detection (slice 04): the file extension determines the strip
    strategy applied before matching:
      .md / unknown  → plain text (suppression markers honoured)
      .html / .htm   → <script>/<style> blanked, tags stripped per line
      .astro         → HTML strategy + summary { de, en } extraction
      .ts            → summary { de, en } string values extracted only

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

    compiled = _compile_lexicon(lexicon)
    strategy = _detect_file_strategy(file_path)
    word_findings = _scan_file_typed(file_path, compiled, strategy)

    # Merge structure/punctuation findings (slice 03) if structure_patterns.json exists
    structure_patterns_path = lexicon_dir / "structure_patterns.json"
    if structure_patterns_path.is_file():
        struct_findings = scan_file_with_structure(
            file_path=file_path,
            structure_dir=str(lexicon_dir),
        )
    else:
        struct_findings = []

    all_findings = word_findings + struct_findings
    all_findings.sort(
        key=lambda f: (f["file_path"], f["line_number"], f["pattern_id"])
    )

    return {"language": chosen_lang, "findings": all_findings}


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
