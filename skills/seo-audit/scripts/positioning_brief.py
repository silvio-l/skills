#!/usr/bin/env python3
"""Positioning-brief loader for seo-audit.

Loads an optional Markdown brief that provides brand-specific context for the
recommendation layer. The brief NEVER influences the Finding list or score —
it is purely recommendation/report context.

Auto-discovery order (when --brief is absent or its path is unreadable):
  1. <root>/.seo/positioning.md
  2. A fenced section in <root>/CONTEXT.md, delimited by:
         <!-- seo:brief -->
         ...content...
         <!-- /seo:brief -->

Return value of load_brief():
    {"content": str, "source": str | None}

`source` is the resolved absolute path of the loaded file, None when not found.
`content` is the raw Markdown text of the brief (empty string when not found).

This module has no dependencies outside the standard library.
"""

from __future__ import annotations

import json
import os
import re
import sys

# Marker syntax for the CONTEXT.md section (HTML comment fences, invisible in
# rendered Markdown and unambiguous in plain text).
CONTEXT_MD_OPEN = "<!-- seo:brief -->"
CONTEXT_MD_CLOSE = "<!-- /seo:brief -->"

_SECTION_RE = re.compile(
    r"<!--\s*seo:brief\s*-->(.*?)<!--\s*/seo:brief\s*-->",
    re.DOTALL | re.IGNORECASE,
)


def _read_file(path: str) -> str | None:
    """Return file text, or None on any OS error (missing, permission, etc.)."""
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return fh.read()
    except OSError:
        return None


def _extract_context_md_section(text: str) -> str | None:
    """Return trimmed content between <!-- seo:brief --> fences, or None."""
    m = _SECTION_RE.search(text)
    return m.group(1).strip() if m else None


def _auto_discover(root: str) -> tuple[str, str] | tuple[None, None]:
    """Try auto-discovery; return (content, abs_source_path) or (None, None).

    Discovery order:
      1. <root>/.seo/positioning.md
      2. <!-- seo:brief --> section in <root>/CONTEXT.md
    """
    # 1. .seo/positioning.md
    seo_brief = os.path.join(root, ".seo", "positioning.md")
    text = _read_file(seo_brief)
    if text is not None:
        return text.strip(), os.path.abspath(seo_brief)

    # 2. Marked section in CONTEXT.md
    context_md = os.path.join(root, "CONTEXT.md")
    text = _read_file(context_md)
    if text is not None:
        section = _extract_context_md_section(text)
        if section:
            return section, os.path.abspath(context_md)

    return None, None


def load_brief(path: str | None, root: str) -> dict:
    """Load a positioning brief; never raises on missing/unreadable files.

    Args:
        path: Explicit path from --brief (may be None or empty).
        root: Repository root used for auto-discovery.

    Returns:
        {"content": str, "source": str | None}
        Falls back to auto-discovery when `path` is absent or unreadable.
        Returns content="" and source=None when nothing is found.
    """
    if path:
        abs_path = os.path.abspath(path)
        text = _read_file(abs_path)
        if text is not None:
            return {"content": text.strip(), "source": abs_path}
        # Explicit path was invalid — fall through to auto-discovery.

    content, source = _auto_discover(root)
    if content is not None:
        return {"content": content, "source": source}

    return {"content": "", "source": None}


def render_status(brief: dict) -> str:
    """Return the German-language brief status string for the report header.

    Examples:
        "geladen aus `/path/to/.seo/positioning.md`"
        "nicht gefunden"
    """
    if brief.get("source"):
        return f"geladen aus `{brief['source']}`"
    return "nicht gefunden"


def main() -> int:  # pragma: no cover — CLI convenience wrapper
    argv = sys.argv[1:]
    if not argv:
        print(
            "usage: positioning_brief.py <root> [--brief <path>]",
            file=sys.stderr,
        )
        return 2
    root = argv[0]
    path = None
    if len(argv) >= 3 and argv[1] == "--brief":
        path = argv[2]
    result = load_brief(path, root)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
