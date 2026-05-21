#!/usr/bin/env python3
"""llms.txt / llms-full.txt generator.

Format per https://llmstxt.org/:

    # <Title>            <- first H1 of the domain doc

    > <summary>           <- first blockquote ("> ...") of the domain doc

    ## Docs               <- bullet list of [Title](link): description

    ## Optional           <- secondary documents (audience etc.)

`llms.txt` is the short overview. `llms-full.txt` concatenates the
domain doc with any `docs/**.md` so an LLM can ingest the full corpus
in one read.

Idempotent — same inputs yield byte-identical output.
"""

from __future__ import annotations

import pathlib
import re
from typing import List, Optional


DOC_TITLE_FALLBACK = "Site"
DOMAIN_DOC_DESCRIPTION = "Anti-Vokabular und Markenkontext"
AUDIENCE_DOC_DESCRIPTION = "Zielgruppe und Personas"
DEFAULT_DOC_DESCRIPTION = "Zusätzliche Projektnotizen"


def _first_h1(text: str) -> str:
    for line in text.splitlines():
        m = re.match(r"#\s+(.*)", line)
        if m:
            return m.group(1).strip()
    return DOC_TITLE_FALLBACK


def _first_blockquote(text: str) -> str:
    """Return the first contiguous blockquote ("> …") joined to a single line."""
    lines = text.splitlines()
    in_block = False
    collected: List[str] = []
    for line in lines:
        if line.startswith(">"):
            in_block = True
            collected.append(line[1:].strip())
        elif in_block:
            break
    return " ".join(s for s in collected if s)


def _audience_doc(repo_root: pathlib.Path) -> Optional[pathlib.Path]:
    """Find optional audience doc under docs/, deterministic."""
    docs = repo_root / "docs"
    if not docs.is_dir():
        return None
    for name in ("audience.md", "zielgruppe.md"):
        p = docs / name
        if p.is_file():
            return p
    return None


def _all_docs(repo_root: pathlib.Path) -> List[pathlib.Path]:
    """List every Markdown file under docs/, sorted by relative path."""
    docs = repo_root / "docs"
    if not docs.is_dir():
        return []
    out = []
    for p in docs.rglob("*.md"):
        if p.is_file():
            out.append(p)
    return sorted(out, key=lambda p: str(p.relative_to(docs)))


def _describe_doc(rel_name: str) -> str:
    base = rel_name.lower()
    if base.endswith("audience.md") or base.endswith("zielgruppe.md"):
        return AUDIENCE_DOC_DESCRIPTION
    return DEFAULT_DOC_DESCRIPTION


def _render_short(title: str, summary: str,
                  ctx_rel: str,
                  audience: Optional[str]) -> str:
    parts: List[str] = [f"# {title}", ""]
    if summary:
        parts.append(f"> {summary}")
        parts.append("")
    parts.append("## Docs")
    parts.append("")
    parts.append(f"- [Domain Doc]({ctx_rel}): {DOMAIN_DOC_DESCRIPTION}")
    if audience:
        parts.append("")
        parts.append("## Optional")
        parts.append("")
        parts.append(
            f"- [Zielgruppe](docs/{audience}): {AUDIENCE_DOC_DESCRIPTION}"
        )
    # Trailing newline for POSIX-friendly files; no extra blank line.
    return "\n".join(parts) + "\n"


def _render_full(context_text: str,
                 extra_docs: List[pathlib.Path],
                 repo_root: pathlib.Path,
                 ctx_path: pathlib.Path) -> str:
    parts: List[str] = []
    parts.append(f"# {ctx_path.name}")
    parts.append("")
    parts.append(context_text.rstrip("\n"))
    for doc in extra_docs:
        parts.append("")
        parts.append("---")
        parts.append("")
        rel = doc.relative_to(repo_root)
        parts.append(f"# {rel.as_posix()}")
        parts.append("")
        parts.append(doc.read_text(encoding="utf-8").rstrip("\n"))
    return "\n".join(parts) + "\n"


def generate(context_path, output_dir, *, full: bool = False) -> pathlib.Path:
    """Generate llms.txt (or llms-full.txt) into `output_dir`.

    `context_path` — the domain doc (CONTEXT.md / CLAUDE.md / README.md).
    `output_dir`   — public/ or dist/ path; must already exist.
    `full=True`    — emit llms-full.txt instead.

    Returns the absolute path of the written file.
    """
    context_path = pathlib.Path(context_path)
    output_dir = pathlib.Path(output_dir)
    repo_root = context_path.parent

    text = context_path.read_text(encoding="utf-8")

    if full:
        body = _render_full(text, _all_docs(repo_root), repo_root, context_path)
        out_path = output_dir / "llms-full.txt"
    else:
        title = _first_h1(text)
        summary = _first_blockquote(text)
        audience_doc = _audience_doc(repo_root)
        audience_name = audience_doc.name if audience_doc else None
        body = _render_short(
            title=title,
            summary=summary,
            ctx_rel=context_path.name,
            audience=audience_name,
        )
        out_path = output_dir / "llms.txt"

    out_path.write_text(body, encoding="utf-8")
    return out_path
