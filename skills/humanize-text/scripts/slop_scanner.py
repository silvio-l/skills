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
  - .ts: every quoted string-literal VALUE is extracted and scanned (i18n
    dictionaries, SEO maps, summary blocks…); identifiers, object keys, and
    comments are ignored. .astro applies the HTML body strategy plus string-
    literal extraction over the leading `---` frontmatter fence.
  All detectors (lexicon + structure) run over the same extracted prose
  segments, so em-dashes inside comments, code, or HTML tags are never flagged.
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
# TypeScript/Astro string-literal extraction
# ---------------------------------------------------------------------------
# Prose in TS-based projects lives in string *values* — i18n dictionaries
# (`export const de = { hero: { title: '…' } }`), SEO maps, content collections,
# and `summary: { de, en }` blocks alike. We therefore extract every quoted
# string literal value and scan it as text, which is a strict superset of the
# earlier summary-only strategy: summary values are string literals too, while
# identifiers, object keys, and bare code tokens (not quoted) are never matched.
#
# Matches single-quoted, double-quoted, and backtick (template) literals. The
# inner text is scanned verbatim; `${…}` interpolations inside template
# literals are left in place (rare in prose dictionaries). Object keys like
# `summary:` are identifiers, not quoted, so they never match. Import paths and
# type-literal strings can match in principle but almost never contain slop
# vocabulary, so the false-positive cost is negligible.
#
# Limits (documented): a stray apostrophe inside a // or /* */ comment could be
# mis-read as a string delimiter. For clean prose dictionaries (the target use
# case) this does not occur; JSDoc headers are matched as block comments and
# their content is not treated specially. See module docstring.

_STRING_LITERAL_RE = re.compile(
    r"'(?:[^'\\]|\\.)*'"
    r'|"(?:[^"\\]|\\.)*"'
    r"|`(?:[^`\\]|\\.)*`",
    re.DOTALL,
)

# Astro frontmatter: the leading `---` … `---` fence at the very top of the file.
_ASTRO_FRONTMATTER_RE = re.compile(r"\A\s*---\n(.*?)\n---", re.DOTALL)


def _extract_string_literals(source: str) -> List[tuple]:
    """Extract (line_number, value) tuples for every quoted string literal.

    Scans *source* for single-, double-, and backtick-quoted string literals
    and returns the 1-based line number where each literal begins together with
    its inner text (quotes stripped). Empty/whitespace-only strings are skipped.

    This replaces the earlier summary-only extractor: it is a strict superset
    that also captures i18n dictionary values, SEO strings, and content fields,
    which is what real TS-based sites actually store prose in.
    """
    results = []
    for m in _STRING_LITERAL_RE.finditer(source):
        value = m.group(0)[1:-1]  # strip the surrounding quote characters
        if not value.strip():
            continue
        line_number = source[: m.start()].count("\n") + 1
        results.append((line_number, value))
    return results


def _extract_astro_frontmatter_literals(source: str) -> List[tuple]:
    """Extract string literals from a .astro file's leading `---` frontmatter.

    Only the frontmatter (TS-like code fence) is scanned for string literals;
    the HTML body is handled separately by the tag-stripping strategy, so HTML
    attribute values are not mis-scanned as prose.
    """
    m = _ASTRO_FRONTMATTER_RE.match(source)
    if not m:
        return []
    fm = m.group(1)
    # Offset of the frontmatter body within source, for correct line numbers.
    base_offset = m.start(1)
    base_line = source[:base_offset].count("\n")
    return [(base_line + ln, value) for (ln, value) in _extract_string_literals(fm)]


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


def _build_segments(file_path: str, strategy: str) -> List[tuple]:
    """Return (line_number, prose_text) segments honouring strategy + suppression.

    This is the single source of truth for "what counts as scannable prose" in a
    file. Both the lexicon matcher and the structure (em-dash / negative
    parallelism) matcher run over these segments, so comments, code tokens, HTML
    tags, and suppressed regions are excluded consistently for every detector.

    Strategies:
      'plain'  — every line is prose (suppression markers honoured)
      'html'   — <script>/<style> blanked, tags stripped, suppression honoured
      'ts'     — only quoted string-literal values (comments/code excluded)
      'astro'  — HTML body segments + frontmatter string literals

    Returns an empty list when a per-file ignore marker is present.
    """
    with open(file_path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    if _has_file_ignore_marker(text):
        return []

    segments: List[tuple] = []

    if strategy == "plain":
        suppressed = False
        for lineno, raw in enumerate(text.splitlines(keepends=True), start=1):
            if _HUMANIZE_OPEN_RE.search(raw):
                suppressed = True
            if suppressed:
                if _HUMANIZE_CLOSE_RE.search(raw):
                    suppressed = False
                continue
            segments.append((lineno, raw))

    elif strategy in ("html", "astro"):
        cleaned = _strip_script_style_preserving_lines(text)
        suppressed = False
        for lineno, raw in enumerate(cleaned.splitlines(keepends=True), start=1):
            if _HUMANIZE_OPEN_RE.search(raw):
                suppressed = True
            if suppressed:
                if _HUMANIZE_CLOSE_RE.search(raw):
                    suppressed = False
                continue
            segments.append((lineno, _strip_tags(raw)))
        if strategy == "astro":
            segments.extend(_extract_astro_frontmatter_literals(text))

    elif strategy == "ts":
        segments.extend(_extract_string_literals(text))

    return segments


# Minimum word count for a segment to count as "prose" rather than a UI label.
# Below this, a string is treated as a label ("EN", "App laden", "Premium") and
# excluded from the scoring denominators (density / rhythm) so a slop-dense
# paragraph is not diluted by dozens of one-word nav strings.
_PROSE_MIN_WORDS: int = 5


def extract_prose_text(file_path: str, strategy: Optional[str] = None) -> str:
    """Return only the substantial prose of *file_path*, joined by newlines.

    Uses the same strip strategy + suppression as scanning, then keeps only
    segments with at least _PROSE_MIN_WORDS words. Short UI labels are dropped.
    The result is what the scorer should use for Rhythm (sentence burstiness)
    and Density (findings per word) so that fragment-heavy files (i18n .ts) are
    scored on their real copy, not on their nav vocabulary.

    Falls back to the full file text when no segment qualifies as prose (e.g. a
    pure label dictionary), so the scorer always has something to work with.
    """
    if strategy is None:
        strategy = _detect_file_strategy(file_path)
    segments = _build_segments(file_path, strategy)
    prose = [text.strip() for _ln, text in segments
             if len(text.split()) >= _PROSE_MIN_WORDS]
    if not prose:
        with open(file_path, encoding="utf-8", errors="replace") as f:
            return f.read()
    return "\n".join(prose)


def _match_lexicon_in_segments(
    segments: List[tuple],
    file_path: str,
    compiled: List[Dict],
) -> List[Dict]:
    """Match every compiled lexicon entry against each prose segment."""
    findings: List[Dict] = []
    for lineno, text in segments:
        for spec in compiled:
            for m in spec["regex"].finditer(text):
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


def _scan_file_typed(
    file_path: str,
    compiled: List[Dict],
    strategy: str,
) -> List[Dict]:
    """Scan *file_path* for lexicon matches using the given strip *strategy*.

    Thin wrapper over _build_segments + _match_lexicon_in_segments. Returns an
    unsorted findings list (caller sorts).
    """
    segments = _build_segments(file_path, strategy)
    return _match_lexicon_in_segments(segments, file_path, compiled)


# ---------------------------------------------------------------------------
# Structure / punctuation pattern loading and scanning (slice 03)
# ---------------------------------------------------------------------------

# Em-dash regex — matches exactly U+2014 (each occurrence independently)
_EM_DASH_RE = re.compile(r"—")

# Generic tricolon / rule-of-three:
# A genuine rhetorical tricolon ("A, B and C") cannot be reliably distinguished
# from an ordinary three-item enumeration ("Python, JavaScript and TypeScript")
# with surface heuristics — any regex narrow enough to avoid those false
# positives also misses most genuine tricolons. We therefore do NOT surface an
# individual finding for the GENERIC form. Instead, the two HIGH-confidence
# sub-variants are detected below: adjective tricola (struct_adj_tricolon) and
# anaphora (struct_anaphora). Both avoid the enumeration false-positive.

# ---------------------------------------------------------------------------
# Anaphora — repeated sentence openers ("Kein X. Kein Y. Nur Z." / "No … No …")
# ---------------------------------------------------------------------------
# Split a prose segment into sentence-ish chunks, then look for runs of
# consecutive chunks that open with the same word. This is the staccato
# marketing tell; it does NOT fire on ordinary enumerations because those live
# in a single sentence, not across several with a shared first word.

_SENT_SPLIT_RE = re.compile(r"[.!?]+(?:\s+|$)")

# Negation openers that make a 2-run already suspicious (DE + EN).
_NEGATION_OPENERS = frozenset(
    ["kein", "keine", "keinen", "keinem", "keiner", "keines",
     "nicht", "nie", "niemals", "no", "not", "never"]
)

# Stop-list of openers too generic to count as a deliberate anaphora even when
# repeated (articles/conjunctions that recur by chance). Negations are NOT here.
_ANAPHORA_OPENER_STOPLIST = frozenset(
    ["der", "die", "das", "ein", "eine", "und", "oder", "the", "a", "an",
     "and", "or", "to", "of", "in", "es", "it", "is", "ist"]
)

_OPENER_WORD_RE = re.compile(r"[^\W\d_][\w'’-]*", re.UNICODE)


def _first_word(sentence: str) -> Optional[str]:
    """Return the lowercased first alphabetic word of *sentence*, or None."""
    m = _OPENER_WORD_RE.search(sentence)
    return m.group(0).lower() if m else None


def _detect_anaphora(text: str) -> List[tuple]:
    """Return (match_excerpt, opener) tuples for anaphora runs in *text*.

    A run is reported when:
      - ≥3 consecutive sentences share the same opening word, OR
      - ≥2 consecutive sentences open with the same NEGATION word
        (kein*/nicht/no/not …) — the 'Kein X. Kein Y.' staccato.

    Generic openers in _ANAPHORA_OPENER_STOPLIST are ignored (they recur by
    chance). Ordinary enumerations never match: they are a single sentence.
    """
    parts = [p.strip() for p in _SENT_SPLIT_RE.split(text) if p.strip()]
    if len(parts) < 2:
        return []
    openers = [_first_word(p) for p in parts]

    results: List[tuple] = []
    i = 0
    n = len(parts)
    while i < n:
        op = openers[i]
        if not op:
            i += 1
            continue
        j = i + 1
        while j < n and openers[j] == op:
            j += 1
        run_len = j - i
        is_negation = op in _NEGATION_OPENERS
        threshold = 2 if is_negation else 3
        if run_len >= threshold and op not in _ANAPHORA_OPENER_STOPLIST:
            excerpt = ". ".join(parts[i:j])
            if len(excerpt) > 90:
                excerpt = excerpt[:87] + "…"
            results.append((excerpt, op))
        i = j if j > i else i + 1
    return results


# ---------------------------------------------------------------------------
# Adjective tricolon — clause-final three-word burst ("groß, klar, motivierend")
# ---------------------------------------------------------------------------
# Two tight shapes, both excluding ordinary enumerations (which are embedded in
# a longer phrase rather than standing alone as a clause-final adjective triple):
#   (1) a dash/colon, then exactly three single-word items, then clause end.
#   (2) a whole short segment that is nothing but three comma-separated words.

_ADJ = r"[^\W\d_][\w'’-]*"  # a single letter-initial word (hyphens allowed)
# Separator between the 2nd and 3rd item: a comma (optionally + und/and/&) OR a
# bare und/and/&. Crucially it can NEVER be just whitespace — that would let
# "verschlüsselt, mit Passwort" (two items, second one multi-word) masquerade as
# a three-item triple. Item 1→2 is always a plain comma.
_SEP3 = r"(?:,\s*(?:(?:und|and|&)\s+)?|(?:und|and|&)\s+)"

# (1) "… — groß, klar, motivierend." / "…: einfach, visuell, motivierend"
_ADJ_TRICOLON_DASH_RE = re.compile(
    r"[—–:]\s*"
    rf"({_ADJ})\s*,\s*({_ADJ})\s*{_SEP3}({_ADJ})"
    r"\s*(?=[.!?…—–]|$)",
    re.UNICODE,
)

# (2) whole segment == three bare comma/und-separated single words
_ADJ_TRICOLON_WHOLE_RE = re.compile(
    rf"^\s*({_ADJ})\s*,\s*({_ADJ})\s*{_SEP3}({_ADJ})\s*$",
    re.UNICODE,
)


def _items_lowercase(m: "re.Match") -> bool:
    """True when the 2nd and 3rd captured items both start lowercase.

    In German, nouns are capitalised and adjectives/adverbs are not, so a
    lowercase 2nd+3rd item marks an adjective triple ('groß, klar, motivierend')
    and a capitalised one marks a noun enumeration ('Lebensmittel, Mobilität,
    Freizeit') that must NOT be flagged. The 1st item is ignored because it is
    often capitalised merely by sitting at the start of a segment.
    """
    return m.group(2)[:1].islower() and m.group(3)[:1].islower()


def _detect_adj_tricolon(text: str, lang: Optional[str] = None) -> List[str]:
    """Return matched excerpts for clause-final / whole-segment adjective triples.

    A bare three-word comma list is ambiguous: 'groß, klar, motivierend' is an
    AI tell, but 'Lebensmittel, Mobilität, Freizeit' / 'groceries, transport,
    leisure' is a legitimate enumeration. German disambiguates by capitalisation
    (nouns are capitalised); English does not. So:

      - whole-segment bare triples are only detected for German, and only when
        the 2nd+3rd items are lowercase (= adjectives, not nouns);
      - the dash/colon form runs for every language (a dash/colon before a triple
        is a stronger signal), but in German it also requires lowercase items so
        'Kategorien: Lebensmittel, Mobilität, Freizeit' is not flagged.

    English thus relies on the dash/colon form and skips the most ambiguous bare
    list — a deliberate precision-over-recall choice (see patterns.md).
    """
    is_de = lang == "de"
    results: List[str] = []
    whole = _ADJ_TRICOLON_WHOLE_RE.match(text)
    if whole:
        if is_de and _items_lowercase(whole):
            results.append(whole.group(0).strip())
        return results  # whole-segment match is exclusive
    for m in _ADJ_TRICOLON_DASH_RE.finditer(text):
        if is_de and not _items_lowercase(m):
            continue  # German noun enumeration after a dash/colon → not a tell
        results.append(m.group(0).strip())
    return results

# Negative parallelism — a rhetorical template LLMs over-use to perform balance.
# Sources (2026): Wikipedia "Signs of AI writing" lists "not just X but Y",
# "it's not X, it's Y", and "not a X, but a Y" as hallmark constructions.
# DE: "nicht nur ... sondern (auch) ...", "es geht nicht (nur) um ... sondern um ..."
# EN: "not just/only ... but ...", "it's not X, it's Y", "not a X, but a Y"
_NEG_PARALLEL_RE = re.compile(
    r"(?:"
    r"nicht\s+nur\b.{1,80}?\bsondern\s+(?:auch\b)?"           # DE "nicht nur … sondern auch"
    r"|"
    r"es\s+geht\s+nicht\s+(?:nur\s+)?um\b.{1,80}?\bsondern\s+um\b"  # DE "es geht nicht um … sondern um"
    r"|"
    r"not\s+just\b.{1,80}?\bbut\s+(?:also\s+)?\b"             # EN "not just … but (also)"
    r"|"
    r"not\s+only\b.{1,80}?\bbut\s+(?:also\s+)?\b"             # EN "not only … but (also)"
    r"|"
    r"it['’]?s\s+not\s+(?:just|only|merely|simply|about)\b.{1,80}?\bit['’]?s\b"  # EN "it's not just X, it's Y"
    r"|"
    r"\bnot\s+(?:a|an|the)\b.{1,50}?,\s*but\s+(?:a|an|the)\b"  # EN "not a X, but a Y"
    r")",
    re.IGNORECASE | re.DOTALL,
)


def _spec_finding(spec: Dict, file_path: str, lineno: int, match: str,
                  default_tier: int) -> Dict:
    """Build a canonical 8-key finding from a structure-pattern *spec*."""
    return {
        "file_path": file_path,
        "line_number": lineno,
        "match": match,
        "pattern_id": spec["pattern_id"],
        "type": spec.get("type", "structure"),
        "tier": int(spec.get("tier", default_tier)),
        "suggested_replacement": spec.get("suggested_replacement", ""),
        "rationale": spec.get("rationale", ""),
    }


def _structure_in_segments(
    segments: List[tuple],
    file_path: str,
    em_dash_spec: Dict,
    neg_par_spec: Dict,
    anaphora_spec: Optional[Dict] = None,
    adj_tricolon_spec: Optional[Dict] = None,
    lang: Optional[str] = None,
) -> List[Dict]:
    """Run structural-tell detection over prose *segments*.

    Detectors:
      - em-dash (tier-3, density-only — recorded, not surfaced individually)
      - negative parallelism (tier-2, cluster-gated)
      - anaphora (tier-2, always surfaced) — repeated sentence openers
      - adjective tricolon (tier-2, always surfaced) — clause-final 3-word burst

    Generic tricolon / rule-of-three is intentionally NOT detected here (it
    cannot be told apart from an ordinary enumeration); only the two
    high-confidence sub-variants above are surfaced. See structure_patterns.json.
    """
    findings: List[Dict] = []
    for lineno, text in segments:
        if em_dash_spec:
            for m in _EM_DASH_RE.finditer(text):
                findings.append(_spec_finding(em_dash_spec, file_path, lineno, m.group(0), 3))
        if neg_par_spec:
            for m in _NEG_PARALLEL_RE.finditer(text):
                findings.append(_spec_finding(neg_par_spec, file_path, lineno, m.group(0), 2))
        if anaphora_spec:
            for excerpt, _opener in _detect_anaphora(text):
                findings.append(_spec_finding(anaphora_spec, file_path, lineno, excerpt, 2))
        if adj_tricolon_spec:
            for excerpt in _detect_adj_tricolon(text, lang):
                findings.append(_spec_finding(adj_tricolon_spec, file_path, lineno, excerpt, 2))
    return findings


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

    by_id: Dict[str, Dict] = {p["pattern_id"]: p for p in patterns}
    em_dash_spec = by_id.get("punct_em_dash", {})
    neg_par_spec = by_id.get("struct_neg_parallelism", {})
    anaphora_spec = by_id.get("struct_anaphora", {})
    adj_tricolon_spec = by_id.get("struct_adj_tricolon", {})

    # Standalone behaviour: every raw line is a segment (no strip strategy, no
    # suppression). The strategy-aware path lives in scan_file_with_language.
    with open(file_path, encoding="utf-8", errors="replace") as f:
        segments = list(enumerate(f.readlines(), start=1))

    findings = _structure_in_segments(
        segments, file_path, em_dash_spec, neg_par_spec,
        anaphora_spec, adj_tricolon_spec,
    )
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

    # Build prose segments once; every detector runs over the SAME segments so
    # strip strategy + suppression apply uniformly (no em-dash hits in comments,
    # code, or HTML tags).
    segments = _build_segments(file_path, strategy)
    word_findings = _match_lexicon_in_segments(segments, file_path, compiled)

    # Merge structure/punctuation findings if structure_patterns.json exists
    structure_patterns_path = lexicon_dir / "structure_patterns.json"
    if structure_patterns_path.is_file():
        patterns = _load_structure_patterns(lexicon_dir)
        by_id = {p["pattern_id"]: p for p in patterns}
        struct_findings = _structure_in_segments(
            segments,
            file_path,
            by_id.get("punct_em_dash", {}),
            by_id.get("struct_neg_parallelism", {}),
            by_id.get("struct_anaphora", {}),
            by_id.get("struct_adj_tricolon", {}),
            lang=chosen_lang,
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
