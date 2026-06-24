#!/usr/bin/env python3
"""GEO/AEO scanner for seo-audit.

Walks an HTML directory (typically the build output `dist/`), checks
entity/citability signals, and returns Finding lists with
``dimension='geo'``.

Checked signals:

* **About/Entity-page presence** — a dedicated About page (by path) or a
  who-is-X heading anywhere in the site.  Absence is flagged as the
  biggest AEO miss.
* **Citable prose blocks** — coherent ``<p>`` paragraphs with
  ``>= MIN_PROSE_CHARS`` characters.  Thin/missing prose is flagged
  per-file.
* **FAQ/Q&A structures** in visible HTML (FAQPage schema belongs to
  slice 03 — not here).  ``<details>/<summary>``, ``<dl>/<dt>`` and
  FAQ-keyword headings all count.  Absence is flagged site-wide.
* **Heading structure** — per-file: exactly one H1; real ``h2``/``h3``
  instead of ``div``/``span`` styled as headings; no hierarchy skips.
* **``llms.txt`` / ``llms-full.txt`` presence** — checked once at the
  dist root.

Output is deterministic — findings are sorted by
``(file_path, line_number, match.lower())``.
"""

from __future__ import annotations

import json
import os
import re
import sys
from typing import Dict, Iterable, List, Tuple

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

# Minimum characters of plain text inside a <p> to count as citable prose.
MIN_PROSE_CHARS = 60

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# URL path fragments that identify an About/Entity page.
_ABOUT_PATH_RE = re.compile(
    r"(?:^|[/\\-])(about|ueber|uebermich|entity|team|about-us|"
    r"wer-wir-sind|profil|bios?)(?:[/\\.?#]|$)",
    re.IGNORECASE,
)

# Heading text that signals a who-is-X / About section.
_WHO_IS_RE = re.compile(
    r"(wer\s+(?:ist|bin|sind|wir|ich)"
    r"|what\s+(?:is|am|are)"
    r"|über\s+(?:uns|mich)"
    r"|about\s+(?:us|me)"
    r"|ich\s+bin"
    r"|we\s+are)",
    re.IGNORECASE,
)

# FAQ/Q&A keyword in heading text.
_FAQ_HEADING_RE = re.compile(
    r"(faq|häufig|haeufig|fragen|q\s*&\s*a|questions|antworten)",
    re.IGNORECASE,
)

# Styled div/span pseudo-heading: class attribute contains h1–h6 as a word.
_STYLED_HEADING_RE = re.compile(
    r'<(?:div|span)\b[^>]*\bclass\s*=\s*["\'][^"\']*\bh[1-6]\b[^"\']*["\']',
    re.IGNORECASE,
)

# Script/style block (contents replaced with blank lines to preserve offsets).
_SCRIPT_STYLE_RE = re.compile(
    r"<(script|style)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Opening heading tag (for line-number scanning).
_H_OPEN_RE = re.compile(r"<(h[1-6])\b", re.IGNORECASE)

# Heading tag with content (for text extraction).
_H_TAG_RE = re.compile(
    r"<(h[1-6])\b[^>]*>(.*?)</\1>",
    re.IGNORECASE | re.DOTALL,
)

# Paragraph tag with content.
_P_TAG_RE = re.compile(r"<p\b[^>]*>(.*?)</p>", re.IGNORECASE | re.DOTALL)

# FAQ: <details> element.
_FAQ_DETAILS_RE = re.compile(r"<details\b", re.IGNORECASE)

# FAQ: <dl> containing at least one <dt>.
_FAQ_DL_DT_RE = re.compile(r"<dl\b.*?<dt\b", re.IGNORECASE | re.DOTALL)

# Tag stripping (lossy; for text-length and pattern matching only).
_TAG_RE = re.compile(r"<[^>]+>")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _strip_tags(text: str) -> str:
    return _TAG_RE.sub(" ", text)


def _strip_script_style(html: str) -> str:
    """Replace script/style block contents with blank lines."""
    def repl(m: re.Match) -> str:
        return "\n" * m.group(0).count("\n")
    return _SCRIPT_STYLE_RE.sub(repl, html)


def _iter_html_files(root: str) -> Iterable[str]:
    for dirpath, dirs, files in os.walk(root):
        dirs.sort()  # deterministic traversal order
        for name in sorted(files):
            if name.lower().endswith((".html", ".htm")):
                yield os.path.join(dirpath, name)


def _read_html(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        return fh.read()


def _make_finding(
    *,
    file_path: str,
    line_number: int,
    match: str,
    suggested_replacement: str,
    rationale: str,
    category: str,
    severity: str,
    user_impact: int,
    fix_effort: int,
    track: str,
) -> Dict:
    """Build a GEO finding dict with all required fields."""
    return {
        "file_path": file_path,
        "line_number": line_number,
        "match": match,
        "suggested_replacement": suggested_replacement,
        "rationale": rationale,
        "category": category,
        "severity": severity,
        "user_impact": user_impact,
        "fix_effort": fix_effort,
        "dimension": "geo",
        "track": track,
    }


# ---------------------------------------------------------------------------
# Per-file checks
# ---------------------------------------------------------------------------

def check_headings(path: str, html: str) -> List[Dict]:
    """Check heading structure in a single HTML file.

    Flags:
    - Zero or more-than-one H1 tags.
    - Heading hierarchy skips (e.g. h1 → h3 without h2).
    - ``div``/``span`` elements with a heading-level class (pseudo-headings).
    """
    findings: List[Dict] = []
    lines = html.splitlines()

    # Collect (level, line_number) for every opening h-tag.
    h_tags: List[Tuple[int, int]] = []
    for lineno, line in enumerate(lines, start=1):
        for m in _H_OPEN_RE.finditer(line):
            h_tags.append((int(m.group(1)[1]), lineno))

    # --- H1 count ---
    h1_lines = [ln for lvl, ln in h_tags if lvl == 1]
    if len(h1_lines) == 0:
        findings.append(_make_finding(
            file_path=path,
            line_number=0,
            match="kein H1-Tag",
            suggested_replacement="Einen <h1>-Tag mit dem Seiten-Haupttitel hinzufügen",
            rationale="Ohne H1-Tag fehlt KI-Parsern der primäre Seitentitel.",
            category="geo-headings",
            severity="high",
            user_impact=3,
            fix_effort=1,
            track="technical",
        ))
    elif len(h1_lines) > 1:
        findings.append(_make_finding(
            file_path=path,
            line_number=h1_lines[1],
            match="mehrfache H1-Tags",
            suggested_replacement="Genau einen <h1>-Tag pro Seite verwenden",
            rationale="Mehrere H1-Tags verwirren KI-Parser und Suchmaschinen.",
            category="geo-headings",
            severity="high",
            user_impact=3,
            fix_effort=1,
            track="technical",
        ))

    # --- Hierarchy skip ---
    seen_levels: set = set()
    for level, lineno in h_tags:
        if level > 1 and (level - 1) not in seen_levels:
            findings.append(_make_finding(
                file_path=path,
                line_number=lineno,
                match=f"Heading-Hierarchie-Sprung zu h{level}",
                suggested_replacement=(
                    f"<h{level - 1}>-Tag vor <h{level}> einfügen"
                ),
                rationale=(
                    "Eine übersprungene Heading-Ebene erschwert KI-Parsern "
                    "das Verstehen der Dokumentstruktur."
                ),
                category="geo-headings",
                severity="med",
                user_impact=2,
                fix_effort=1,
                track="technical",
            ))
        seen_levels.add(level)

    # --- Styled div/span pseudo-headings (one finding per matching line) ---
    for lineno, line in enumerate(lines, start=1):
        if _STYLED_HEADING_RE.search(line):
            findings.append(_make_finding(
                file_path=path,
                line_number=lineno,
                match="gestyltes div/span als Heading",
                suggested_replacement=(
                    "Semantische <h2>/<h3>-Tags statt div/span mit "
                    "Heading-Klasse verwenden"
                ),
                rationale=(
                    "Gestylte div/span-Elemente sind für KI-Parser nicht "
                    "als Überschriften erkennbar."
                ),
                category="geo-headings",
                severity="med",
                user_impact=2,
                fix_effort=2,
                track="technical",
            ))

    return findings


def check_prose(path: str, html: str) -> List[Dict]:
    """Flag pages with thin or missing citable prose.

    A page is thin when it has no ``<p>`` tag whose stripped text is at
    least ``MIN_PROSE_CHARS`` characters long.
    """
    cleaned = _strip_script_style(html)
    paragraphs = _P_TAG_RE.findall(cleaned)

    has_citable = any(
        len(_strip_tags(p).strip()) >= MIN_PROSE_CHARS
        for p in paragraphs
    )

    if not paragraphs:
        return [_make_finding(
            file_path=path,
            line_number=0,
            match="kein zitierbarer Inhalt",
            suggested_replacement=(
                "Zitierbaren Fließtext in <p>-Tags ergänzen"
            ),
            rationale=(
                "Ohne Absätze kann diese Seite nicht als Antwortquelle "
                "für KI-Suchen dienen."
            ),
            category="geo-prose",
            severity="med",
            user_impact=2,
            fix_effort=3,
            track="strategic",
        )]

    if not has_citable:
        return [_make_finding(
            file_path=path,
            line_number=0,
            match="dünner Inhalt",
            suggested_replacement=(
                f"Mindestens einen Absatz mit ≥ {MIN_PROSE_CHARS} Zeichen "
                f"Fließtext ergänzen"
            ),
            rationale=(
                "Kurze, fragmentierte Absätze sind schwerer zitierbar als "
                "zusammenhängende Erklärungen."
            ),
            category="geo-prose",
            severity="med",
            user_impact=2,
            fix_effort=3,
            track="strategic",
        )]

    return []


# ---------------------------------------------------------------------------
# Site-level checks
# ---------------------------------------------------------------------------

def check_about_page(
    dist_root: str,
    parsed_files: List[Tuple[str, str]],
) -> List[Dict]:
    """Return a finding when no About/Entity page is detected.

    Detection order:
    1. Path of any HTML file contains an about-like keyword.
    2. Any heading on any page matches a who-is-X pattern.
    """
    for path, html in parsed_files:
        rel = os.path.relpath(path, dist_root).replace("\\", "/")
        if _ABOUT_PATH_RE.search(rel):
            return []
        cleaned = _strip_script_style(html)
        for m in _H_TAG_RE.finditer(cleaned):
            if _WHO_IS_RE.search(_strip_tags(m.group(2))):
                return []

    return [_make_finding(
        file_path=dist_root,
        line_number=0,
        match="keine About-/Entity-Seite",
        suggested_replacement=(
            "Eine dedizierte About-/Entity-Seite erstellen mit einer "
            "Antwort auf 'Wer/Was ist …'"
        ),
        rationale=(
            "Eine 'Über uns'-Seite ist der wichtigste AEO-Hebel: "
            "KI-Suchmaschinen brauchen eine zitierbare Entitätsbeschreibung."
        ),
        category="geo-entity",
        severity="high",
        user_impact=3,
        fix_effort=3,
        track="strategic",
    )]


def check_faq_site(
    dist_root: str,
    parsed_files: List[Tuple[str, str]],
) -> List[Dict]:
    """Return a finding when no FAQ/Q&A structure is found across the site.

    Detects: ``<details>/<summary>``, ``<dl>/<dt>``, headings whose text
    contains a FAQ keyword.
    """
    for _path, html in parsed_files:
        cleaned = _strip_script_style(html)
        if _FAQ_DETAILS_RE.search(cleaned):
            return []
        if _FAQ_DL_DT_RE.search(cleaned):
            return []
        for m in _H_TAG_RE.finditer(cleaned):
            if _FAQ_HEADING_RE.search(_strip_tags(m.group(2))):
                return []

    return [_make_finding(
        file_path=dist_root,
        line_number=0,
        match="keine FAQ-/Q&A-Struktur",
        suggested_replacement=(
            "FAQ-Sektion mit <details>/<summary> oder strukturierten "
            "Frage-/Antwort-Paaren ergänzen"
        ),
        rationale=(
            "FAQ-Inhalte werden von KI-Suchen häufig als direkte "
            "Antwortquellen genutzt."
        ),
        category="geo-faq",
        severity="low",
        user_impact=1,
        fix_effort=2,
        track="strategic",
    )]


def check_llms_txt(dist_root: str) -> List[Dict]:
    """Return a finding when neither ``llms.txt`` nor ``llms-full.txt``
    is present in ``dist_root``."""
    if (os.path.isfile(os.path.join(dist_root, "llms.txt"))
            or os.path.isfile(os.path.join(dist_root, "llms-full.txt"))):
        return []

    return [_make_finding(
        file_path=dist_root,
        line_number=0,
        match="llms.txt fehlt",
        suggested_replacement=(
            "llms.txt im Dist-Root erstellen "
            "(kurze maschinenlesbare Zusammenfassung der Site)"
        ),
        rationale=(
            "llms.txt ermöglicht KI-Agenten eine strukturierte Übersicht "
            "der Site ohne vollständiges Crawling."
        ),
        category="geo-llms",
        severity="low",
        user_impact=1,
        fix_effort=1,
        track="technical",
    )]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def scan_directory(dist_root: str, quick: bool = False) -> List[Dict]:
    """Walk ``dist_root``, run all GEO checks, return sorted findings.

    Args:
        dist_root: Built HTML directory (e.g. ``dist/``).
        quick:     Skip heavy per-file checks (prose analysis) and the
                   site-wide FAQ scan.  Heading and site-level entity
                   checks still run.

    Returns:
        Sorted list of finding dicts, each with ``dimension='geo'``.
        Two calls with the same ``dist_root`` return byte-identical lists.
    """
    if not os.path.isdir(dist_root):
        return []

    html_files = list(_iter_html_files(dist_root))
    if not html_files:
        return []

    # Read each file once.
    parsed: List[Tuple[str, str]] = [
        (path, _read_html(path)) for path in html_files
    ]

    all_findings: List[Dict] = []

    # --- Site-level checks (always run) ---
    all_findings.extend(check_about_page(dist_root, parsed))
    all_findings.extend(check_llms_txt(dist_root))

    # --- Site-level FAQ (skipped under --quick) ---
    if not quick:
        all_findings.extend(check_faq_site(dist_root, parsed))

    # --- Per-file checks ---
    for path, html in parsed:
        all_findings.extend(check_headings(path, html))
        if not quick:
            all_findings.extend(check_prose(path, html))

    # Deterministic sort matching brand_scan convention.
    all_findings.sort(
        key=lambda f: (f["file_path"], f["line_number"], f["match"].lower())
    )
    return all_findings


# ---------------------------------------------------------------------------
# Standalone CLI
# ---------------------------------------------------------------------------

def main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(
        prog="geo_scan",
        description=(
            "GEO/AEO scanner: entity and citability signals from built HTML."
        ),
    )
    p.add_argument("dist", help="Built HTML directory to scan.")
    p.add_argument(
        "--quick",
        action="store_true",
        help="Skip heavy checks (prose analysis, site-wide FAQ scan).",
    )
    args = p.parse_args(argv)

    findings = scan_directory(args.dist, quick=args.quick)
    print(json.dumps(findings, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
