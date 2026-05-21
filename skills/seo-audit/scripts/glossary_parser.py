#!/usr/bin/env python3
"""Anti-vocabulary table parser for seo-audit.

Extracts the brand-glossary table from a Markdown document (typically
`CONTEXT.md`). Two shapes are accepted:

    | Begriff | Stattdessen | Grund |
    | ------- | ----------- | ----- |
    | App     | Web App     | …     |

or, without leading/trailing pipes:

    Begriff   | Stattdessen | Grund
    App       | Web App     | …

The first 3-column table whose header reads `Begriff | Stattdessen | Grund`
(case-insensitive) wins. Cells may wrap values in inline-code backticks
(`` `App` ``); we strip them. Separator rows (`| --- | --- | --- |` and
left/right-aligned variants `:---`, `---:`, `:---:`) are skipped.

This module has no dependencies outside the standard library.
"""

from __future__ import annotations

import json
import re
import sys
from typing import List, Dict, Optional

HEADER_TERMS = ("begriff", "stattdessen", "grund")
SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")


def _split_pipe_row(line: str) -> List[str]:
    """Split a pipe-delimited row into cells. Tolerates leading/trailing pipes."""
    stripped = line.strip()
    if stripped.startswith("|"):
        stripped = stripped[1:]
    if stripped.endswith("|"):
        stripped = stripped[:-1]
    return [cell.strip() for cell in stripped.split("|")]


def _is_separator_row(cells: List[str]) -> bool:
    if not cells:
        return False
    return all(SEPARATOR_CELL_RE.match(c.strip()) for c in cells if c.strip())


def _unwrap_inline_code(cell: str) -> str:
    """Strip surrounding backticks so `` `App` `` becomes `App`."""
    m = re.match(r"^`(.+)`$", cell.strip())
    return m.group(1).strip() if m else cell.strip()


def _is_glossary_header(cells: List[str]) -> bool:
    if len(cells) != 3:
        return False
    lowered = [c.strip().lower() for c in cells]
    return tuple(lowered) == HEADER_TERMS


def parse_glossary(markdown: str) -> List[Dict[str, str]]:
    """Return a list of `{term, replacement, rationale}` entries.

    Empty list if no glossary table is found. The parser scans the
    document line-by-line, identifies a header row matching the three
    glossary columns, then consumes subsequent rows until the table ends
    (blank line or non-pipe content).
    """
    if not markdown:
        return []

    entries: List[Dict[str, str]] = []
    lines = markdown.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if "|" not in line:
            i += 1
            continue
        cells = _split_pipe_row(line)
        if not _is_glossary_header(cells):
            i += 1
            continue

        # Found a header; consume the table body.
        i += 1
        while i < len(lines):
            row = lines[i]
            if not row.strip() or "|" not in row:
                break
            row_cells = _split_pipe_row(row)
            if _is_separator_row(row_cells):
                i += 1
                continue
            if len(row_cells) != 3:
                break
            term = _unwrap_inline_code(row_cells[0])
            replacement = _unwrap_inline_code(row_cells[1])
            rationale = row_cells[2].strip()
            if term:
                entries.append({
                    "term": term,
                    "replacement": replacement,
                    "rationale": rationale,
                })
            i += 1
        # Only first glossary table wins.
        return entries

    return entries


def load_glossary_from_repo(repo_root: str) -> List[Dict[str, str]]:
    """Convenience: try CONTEXT.md, then CLAUDE.md, then README.md."""
    import os
    for name in ("CONTEXT.md", "CLAUDE.md", "README.md"):
        path = os.path.join(repo_root, name)
        if os.path.isfile(path):
            with open(path, "r", encoding="utf-8") as f:
                entries = parse_glossary(f.read())
            if entries:
                return entries
    return []


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("usage: glossary_parser.py {parse|from-repo <root>}")
    cmd = sys.argv[1]
    if cmd == "parse":
        entries = parse_glossary(sys.stdin.read())
    elif cmd == "from-repo":
        if len(sys.argv) < 3:
            sys.exit("from-repo requires <root>")
        entries = load_glossary_from_repo(sys.argv[2])
    else:
        sys.exit(f"unknown subcommand: {cmd}")
    print(json.dumps(entries, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
