#!/usr/bin/env python3
"""Brand-consistency scanner for seo-audit.

Walks an HTML directory (typically the build output `dist/`), strips
`<script>` and `<style>` content, then matches every glossary term
case-insensitively against the remaining text, line by line. Emits one
finding per match — multiple matches on the same line produce multiple
findings, all carrying the same `line_number`.

Suppression:

* Per-file: an HTML comment in the first kB of the file whose text
  contains `contrastiveVocabulary: true` skips the entire file. This is
  how Astro/Markdown pages flag themselves as kontrastiv-allowed.
* Per-section: lines wrapped between `<!-- seo-audit:contrastive -->`
  and `<!-- /seo-audit:contrastive -->` are ignored. A missing closing
  marker suppresses through end of file.

Output is deterministic — findings are sorted by
`(file_path, line_number, match)`.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import List, Dict, Iterable

# Strip script/style blocks before matching so that JS variable names
# and CSS selectors do not count as brand violations.
SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)

OPEN_CONTRASTIVE_RE = re.compile(
    r"<!--\s*seo-audit:contrastive\s*-->",
    re.IGNORECASE,
)
CLOSE_CONTRASTIVE_RE = re.compile(
    r"<!--\s*/seo-audit:contrastive\s*-->",
    re.IGNORECASE,
)

FRONTMATTER_FLAG_RE = re.compile(
    r"contrastiveVocabulary\s*:\s*true",
    re.IGNORECASE,
)


def _has_frontmatter_flag(html: str) -> bool:
    """Detect `contrastiveVocabulary: true` in the first HTML comment block."""
    head = html[:2048]
    # Only honour the flag if it appears inside an HTML comment.
    for m in re.finditer(r"<!--(.*?)-->", head, re.DOTALL):
        if FRONTMATTER_FLAG_RE.search(m.group(1)):
            return True
    return False


def _strip_script_style_preserving_lines(html: str) -> str:
    """Replace <script>/<style> block contents with blank lines.

    Newlines inside the stripped block are kept so subsequent line
    numbers stay aligned with the source file.
    """
    def repl(m: re.Match) -> str:
        body = m.group(0)
        return "\n" * body.count("\n")
    return SCRIPT_STYLE_RE.sub(repl, html)


def _strip_tags(line: str) -> str:
    """Lossy tag stripping for line-level matching. Keeps text positions."""
    return re.sub(r"<[^>]+>", " ", line)


def _compile_patterns(glossary: List[Dict[str, str]]) -> List[Dict]:
    compiled = []
    for entry in glossary:
        term = entry.get("term", "").strip()
        if not term:
            continue
        # Word-boundary match, case-insensitive. `re.escape` handles
        # special characters in the term.
        pattern = re.compile(
            r"\b" + re.escape(term) + r"\b",
            re.IGNORECASE,
        )
        compiled.append({
            "pattern": pattern,
            "term": term,
            "replacement": entry.get("replacement", ""),
            "rationale": entry.get("rationale", ""),
        })
    return compiled


def _iter_html_files(root: str) -> Iterable[str]:
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name.lower().endswith((".html", ".htm")):
                yield os.path.join(dirpath, name)


def scan_file(path: str, glossary: List[Dict[str, str]]) -> List[Dict]:
    """Scan a single HTML file and return its findings (unsorted)."""
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        html = f.read()

    if _has_frontmatter_flag(html):
        return []

    compiled = _compile_patterns(glossary)
    if not compiled:
        return []

    cleaned = _strip_script_style_preserving_lines(html)
    findings: List[Dict] = []
    suppressed = False

    for lineno, raw in enumerate(cleaned.splitlines(), start=1):
        # Toggle suppression by markers BEFORE matching on this line so
        # the marker-line itself does not produce findings.
        if OPEN_CONTRASTIVE_RE.search(raw):
            suppressed = True
        if suppressed:
            if CLOSE_CONTRASTIVE_RE.search(raw):
                suppressed = False
            continue

        text = _strip_tags(raw)
        for spec in compiled:
            for m in spec["pattern"].finditer(text):
                findings.append({
                    "file_path": path,
                    "line_number": lineno,
                    "match": m.group(0),
                    "suggested_replacement": spec["replacement"],
                    "rationale": spec["rationale"],
                })
    return findings


def scan_directory(root: str, glossary: List[Dict[str, str]]) -> List[Dict]:
    """Walk `root`, scan every .html/.htm file, return sorted findings."""
    if not glossary:
        return []
    all_findings: List[Dict] = []
    for path in _iter_html_files(root):
        all_findings.extend(scan_file(path, glossary))
    all_findings.sort(
        key=lambda f: (f["file_path"], f["line_number"], f["match"].lower())
    )
    return all_findings


def main() -> int:
    if len(sys.argv) < 3:
        sys.exit("usage: brand_scan.py <dist-dir> <glossary-json-file>")
    root = sys.argv[1]
    glossary_path = sys.argv[2]
    with open(glossary_path, "r", encoding="utf-8") as f:
        glossary = json.load(f)
    findings = scan_directory(root, glossary)
    print(json.dumps(findings, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
