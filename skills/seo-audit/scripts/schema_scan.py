#!/usr/bin/env python3
"""Schema.org structured-data scanner for seo-audit.

Walks an HTML directory (typically the build output ``dist/``), extracts
all ``<script type="application/ld+json">`` blocks, and checks them for
common structural issues. Returns Finding lists with
``dimension='schema'``.

Checked signals:

* **Presence** — pages with no JSON-LD at all.
* **Tolerant extraction** — broken/partly-broken JSON-LD is flagged as
  a finding rather than causing an exception.
* **Required-field completeness** — Organization, Person, Article,
  Product, WebSite, WebPage, FAQPage must carry their mandatory fields;
  missing fields are reported before Rich Results can reject them.
* **Deprecated types** — known-deprecated Schema.org types are flagged.
* **sameAs consistency** (GEO signal) — social profile URLs declared in
  JSON-LD ``sameAs`` that are not linked anywhere in the page HTML are
  reported as a contradiction.

Versioned data tables (``REQUIRED_FIELDS_V1``, ``DEPRECATED_TYPES_V1``)
are embedded here and reviewable in git history.

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
# Versioned data tables  (schema v1.0.0  2026-06-24)
# ---------------------------------------------------------------------------

# Minimum required fields for Rich Results eligibility per Schema.org type.
# Update the version comment and bump audit.py GENERATOR_VERSION when changed.
# Source: https://developers.google.com/search/docs/appearance/structured-data
REQUIRED_FIELDS_V1: Dict[str, List[str]] = {
    "Organization": ["name", "url"],
    "Person":       ["name"],
    "Article":      ["headline", "author", "datePublished"],
    "Product":      ["name", "description"],
    "WebSite":      ["name", "url"],
    "WebPage":      ["name"],
    "FAQPage":      ["mainEntity"],
}

# Schema.org types that are deprecated and must not be used in new markup.
# Update the version comment and bump audit.py GENERATOR_VERSION when changed.
# Source: https://schema.org (each type page carries a deprecation notice)
DEPRECATED_TYPES_V1: frozenset = frozenset({
    "WPFooter",       # WordPress-specific, deprecated on schema.org
    "WPHeader",       # WordPress-specific, deprecated on schema.org
    "WPSideBar",      # WordPress-specific, deprecated on schema.org
    "WPAdBlock",      # WordPress-specific, deprecated on schema.org
    "DataFeedItem",   # deprecated; use ListItem
    "UserComments",   # deprecated; use Comment/UserReview
})

# ---------------------------------------------------------------------------
# Compiled patterns
# ---------------------------------------------------------------------------

# Frontmatter flag: pages that carry this inside an HTML comment are
# excluded from all schema findings (same convention as brand_scan).
_FRONTMATTER_FLAG_RE = re.compile(
    r"contrastiveVocabulary\s*:\s*true",
    re.IGNORECASE,
)

# Match <script type="application/ld+json"> blocks (captures inner text).
_JSON_LD_RE = re.compile(
    r'<script\b[^>]*\btype\s*=\s*["\']application/ld\+json["\'][^>]*>'
    r'(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)

# Extract href values from anchor tags for sameAs reconciliation.
_HREF_RE = re.compile(
    r'<a\b[^>]*\bhref\s*=\s*["\']([^"\']+)["\']',
    re.IGNORECASE,
)

# Detects social-network profile URLs by domain.
_SOCIAL_RE = re.compile(
    r'https?://(?:www\.)?(?:'
    r'twitter\.com|x\.com|facebook\.com|fb\.com|linkedin\.com|'
    r'instagram\.com|youtube\.com|youtu\.be|pinterest\.com|'
    r'tiktok\.com|github\.com|xing\.com|mastodon\.[a-z]+'
    r')/',
    re.IGNORECASE,
)

# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _iter_html_files(root: str) -> Iterable[str]:
    for dirpath, dirs, files in os.walk(root):
        dirs.sort()  # deterministic traversal order
        for name in sorted(files):
            if name.lower().endswith((".html", ".htm")):
                yield os.path.join(dirpath, name)


def _has_contrastive_flag(html: str) -> bool:
    """Return True when the page carries ``contrastiveVocabulary: true``.

    Only the first 2 kB is examined, and only inside HTML comment blocks —
    matching the same convention as brand_scan so that contrastive
    comparison pages are excluded from all schema findings.
    """
    head = html[:2048]
    for m in re.finditer(r"<!--(.*?)-->", head, re.DOTALL):
        if _FRONTMATTER_FLAG_RE.search(m.group(1)):
            return True
    return False


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
    """Build a Schema finding dict with all required fields."""
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
        "dimension": "schema",
        "track": track,
    }


def _extract_json_ld(html: str) -> List[Tuple[int, str, object]]:
    """Extract all JSON-LD blocks from HTML.

    Returns a list of ``(line_number, raw_text, parsed_or_None)`` tuples.
    ``parsed_or_None`` is ``None`` for blocks that fail JSON parsing —
    callers must never raise on ``None``; flag it as a finding instead.

    Line numbers are computed from the character offset of the opening
    ``<script>`` tag so that findings can reference the source line.
    """
    # Build offset → line-number index.
    lines = html.splitlines(keepends=True)
    offsets: List[Tuple[int, int]] = []
    pos = 0
    for lineno, line in enumerate(lines, start=1):
        offsets.append((pos, lineno))
        pos += len(line)

    def _offset_to_lineno(off: int) -> int:
        lo, hi = 0, len(offsets) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if offsets[mid][0] <= off:
                lo = mid
            else:
                hi = mid - 1
        return offsets[lo][1]

    results: List[Tuple[int, str, object]] = []
    for m in _JSON_LD_RE.finditer(html):
        raw = m.group(1).strip()
        lineno = _offset_to_lineno(m.start())
        try:
            parsed: object = json.loads(raw)
        except json.JSONDecodeError:
            parsed = None
        results.append((lineno, raw, parsed))
    return results


def _iter_nodes(parsed: object) -> Iterable[Dict]:
    """Yield all Schema.org node dicts from a parsed JSON-LD object.

    Handles:
    - A plain ``{"@type": "…"}`` object.
    - A ``{"@graph": […]}`` wrapper.
    - A top-level list of objects.
    """
    if isinstance(parsed, dict):
        if "@graph" in parsed and isinstance(parsed["@graph"], list):
            for item in parsed["@graph"]:
                yield from _iter_nodes(item)
        else:
            yield parsed
    elif isinstance(parsed, list):
        for item in parsed:
            yield from _iter_nodes(item)


def _schema_type(node: Dict) -> str:
    """Return the plain type name, stripping any full URL prefix."""
    type_val = node.get("@type", "")
    if isinstance(type_val, list):
        type_val = type_val[0] if type_val else ""
    return str(type_val).rsplit("/", 1)[-1]


def _collect_sameas_urls(parsed: object) -> List[str]:
    """Recursively collect all sameAs values from a parsed JSON-LD object."""
    urls: List[str] = []
    if isinstance(parsed, dict):
        same = parsed.get("sameAs")
        if isinstance(same, str) and same:
            urls.append(same)
        elif isinstance(same, list):
            urls.extend(str(v) for v in same if v)
        for v in parsed.values():
            if isinstance(v, (dict, list)):
                urls.extend(_collect_sameas_urls(v))
    elif isinstance(parsed, list):
        for item in parsed:
            urls.extend(_collect_sameas_urls(item))
    return urls


def _html_links(html: str) -> List[str]:
    """Return all href values from anchor tags in the HTML."""
    return [m.group(1) for m in _HREF_RE.finditer(html)]


def _is_social_url(url: str) -> bool:
    """Return True when url points to a known social-network profile page."""
    return bool(_SOCIAL_RE.match(url))


# ---------------------------------------------------------------------------
# Per-file checks
# ---------------------------------------------------------------------------


def check_no_json_ld(path: str, html: str) -> List[Dict]:
    """Flag pages that have no JSON-LD block at all."""
    if _JSON_LD_RE.search(html):
        return []
    return [_make_finding(
        file_path=path,
        line_number=0,
        match="kein JSON-LD",
        suggested_replacement=(
            'Mindestens einen <script type="application/ld+json">-Block '
            "ergänzen (z. B. WebSite oder Organization)"
        ),
        rationale=(
            "Ohne strukturierte Daten können Suchmaschinen Typ und "
            "Relevanz dieser Seite nicht maschinell bestimmen."
        ),
        category="schema-missing",
        severity="high",
        user_impact=3,
        fix_effort=2,
        track="technical",
    )]


def check_broken_json_ld(
    path: str,
    blocks: List[Tuple[int, str, object]],
) -> List[Dict]:
    """Flag JSON-LD blocks whose content is not valid JSON."""
    findings: List[Dict] = []
    for lineno, _raw, parsed in blocks:
        if parsed is None:
            findings.append(_make_finding(
                file_path=path,
                line_number=lineno,
                match="ungültiges JSON-LD",
                suggested_replacement=(
                    "JSON-Syntax prüfen und korrigieren "
                    "(z. B. mit schema.org/validator)"
                ),
                rationale=(
                    "Ein fehlerhafter JSON-LD-Block wird von Suchmaschinen "
                    "ignoriert und kann Rich-Result-Eligibility kosten."
                ),
                category="schema-broken",
                severity="high",
                user_impact=3,
                fix_effort=1,
                track="technical",
            ))
    return findings


def check_required_fields(
    path: str,
    blocks: List[Tuple[int, str, object]],
) -> List[Dict]:
    """Check that core Schema.org types carry all fields from REQUIRED_FIELDS_V1."""
    findings: List[Dict] = []
    for lineno, _raw, parsed in blocks:
        if parsed is None:
            continue  # broken blocks are reported by check_broken_json_ld
        for node in _iter_nodes(parsed):
            schema_type = _schema_type(node)
            required = REQUIRED_FIELDS_V1.get(schema_type)
            if not required:
                continue
            for field in required:
                if not node.get(field):
                    findings.append(_make_finding(
                        file_path=path,
                        line_number=lineno,
                        match=f"{schema_type}: Pflichtfeld „{field}“ fehlt",
                        suggested_replacement=(
                            f"Feld „{field}“ in den "
                            f"{schema_type}-Block ergänzen"
                        ),
                        rationale=(
                            f"{schema_type} ohne „{field}“ wird von "
                            f"Google Rich Results abgelehnt "
                            f"(Quelle: REQUIRED_FIELDS_V1)."
                        ),
                        category="schema-incomplete",
                        severity="high",
                        user_impact=3,
                        fix_effort=2,
                        track="technical",
                    ))
    return findings


def check_deprecated_types(
    path: str,
    blocks: List[Tuple[int, str, object]],
) -> List[Dict]:
    """Flag uses of known-deprecated Schema.org types from DEPRECATED_TYPES_V1."""
    findings: List[Dict] = []
    for lineno, _raw, parsed in blocks:
        if parsed is None:
            continue
        for node in _iter_nodes(parsed):
            schema_type = _schema_type(node)
            if schema_type in DEPRECATED_TYPES_V1:
                findings.append(_make_finding(
                    file_path=path,
                    line_number=lineno,
                    match=f"veralteter Schema-Typ „{schema_type}“",
                    suggested_replacement=(
                        f"„{schema_type}“ durch einen aktuellen "
                        f"Schema.org-Typ ersetzen "
                        f"(schema.org/version/latest)"
                    ),
                    rationale=(
                        f"Der Typ „{schema_type}“ ist auf schema.org "
                        f"als deprecated markiert und wird von Suchmaschinen "
                        f"möglicherweise nicht mehr ausgewertet "
                        f"(Quelle: DEPRECATED_TYPES_V1)."
                    ),
                    category="schema-deprecated",
                    severity="med",
                    user_impact=2,
                    fix_effort=2,
                    track="technical",
                ))
    return findings


def check_sameas_consistency(
    path: str,
    html: str,
    blocks: List[Tuple[int, str, object]],
) -> List[Dict]:
    """Flag sameAs social-profile URLs that are not linked anywhere in the HTML.

    Logic: collect all sameAs values from parsed JSON-LD; collect all
    ``href`` values from ``<a>`` tags; report sameAs entries that point to
    a social-network profile but have no corresponding anchor in the HTML.
    Non-social sameAs entries (e.g. Wikidata, DBpedia) are ignored.
    """
    sameas_urls: List[str] = []
    for _lineno, _raw, parsed in blocks:
        if parsed is not None:
            sameas_urls.extend(_collect_sameas_urls(parsed))

    if not sameas_urls:
        return []

    html_hrefs = set(_html_links(html))
    findings: List[Dict] = []

    for url in sameas_urls:
        if not _is_social_url(url):
            continue
        url_norm = url.rstrip("/")
        linked = any(
            link.rstrip("/") == url_norm
            or link.rstrip("/").startswith(url_norm + "/")
            or link.rstrip("/").startswith(url_norm + "?")
            for link in html_hrefs
        )
        if not linked:
            findings.append(_make_finding(
                file_path=path,
                line_number=0,
                match=f"sameAs-Profil nicht verlinkt: {url}",
                suggested_replacement=(
                    f'<a href="{url}">-Link im HTML ergänzen oder '
                    f"sameAs-Eintrag entfernen"
                ),
                rationale=(
                    f"Die sameAs-URL „{url}“ ist im JSON-LD "
                    f"deklariert, aber nirgends im HTML verlinkt — "
                    f"Suchmaschinen könnten die Verbindung anzweifeln."
                ),
                category="schema-sameas",
                severity="med",
                user_impact=2,
                fix_effort=1,
                track="technical",
            ))
    return findings


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def scan_file(path: str, html: str) -> List[Dict]:
    """Run all schema checks on a single HTML file and return findings.

    Files whose first HTML comment contains ``contrastiveVocabulary: true``
    are excluded entirely (same convention as brand_scan).

    Findings are NOT sorted here; ``scan_directory`` performs the final sort.
    """
    if _has_contrastive_flag(html):
        return []

    findings: List[Dict] = []

    # Presence check (AC2).
    findings.extend(check_no_json_ld(path, html))

    # Extract all blocks once (AC1 — tolerant).
    blocks = _extract_json_ld(html)

    # Broken-block check (AC1).
    findings.extend(check_broken_json_ld(path, blocks))

    # Required-field completeness (AC3).
    findings.extend(check_required_fields(path, blocks))

    # Deprecated type check (AC4).
    findings.extend(check_deprecated_types(path, blocks))

    # sameAs consistency (AC5 / GEO signal).
    findings.extend(check_sameas_consistency(path, html, blocks))

    return findings


def scan_directory(dist_root: str) -> List[Dict]:
    """Walk ``dist_root``, run all schema checks, return sorted findings.

    Args:
        dist_root: Built HTML directory (e.g. ``dist/``).

    Returns:
        Sorted list of finding dicts, each with ``dimension='schema'``.
        Two calls with the same ``dist_root`` return byte-identical lists.
    """
    if not os.path.isdir(dist_root):
        return []

    all_findings: List[Dict] = []
    for path in _iter_html_files(dist_root):
        html = _read_html(path)
        all_findings.extend(scan_file(path, html))

    # Deterministic sort — matches geo_scan convention.
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
        prog="schema_scan",
        description=(
            "Schema.org scanner: extracts and validates JSON-LD "
            "from built HTML."
        ),
    )
    p.add_argument("dist", help="Built HTML directory to scan.")
    args = p.parse_args(argv)

    findings = scan_directory(args.dist)
    print(json.dumps(findings, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
