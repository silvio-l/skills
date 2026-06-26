#!/usr/bin/env python3
"""Pure brand-conflict module (slice 05 P3).

Resolves, parses, and detects brand-glossar conflicts against scored
keywords. Never mutates the target repo — detection + reporting only.

Four building blocks:

1. **resolver** — discover a glossar by convention or CLI flag.
2. **parser** — extract {forbidden, canonical} from a glossar file
   (brand-glossary.ts, .brandignore, BRAND_WORDS.md).
3. **conflict detector** — case-insensitive, substring-aware,
   deterministic conflict records for a keyword list + glossar.
4. **strategy set** — descriptions only, never auto-applied.
"""

from __future__ import annotations

import pathlib
import re
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# Strategy set (descriptions — NEVER auto-applied)
# ---------------------------------------------------------------------------

STRATEGIES: Dict[str, str] = {
    "keyword-field-only": (
        "Hide the forbidden term in the 100-character hidden keyword field "
        "(Apple) to capture search volume without it appearing in visible "
        "listing text."
    ),
    "alternative phrasing": (
        "Replace the forbidden term with its canonical replacement in all "
        "listing text — preserve the brand voice while still targeting the "
        "underlying search intent."
    ),
    "non-brand landingpage": (
        "Capture the forbidden term on a dedicated landing page outside the "
        "core brand surface — isolate the ranking page from the main brand "
        "pages so the brand voice stays clean."
    ),
    "accept deliberately": (
        "Use the forbidden term knowingly — override the brand rule with "
        "eyes open, accepting the dilution risk because the search-volume "
        "gain justifies it."
    ),
}

# ---------------------------------------------------------------------------
# Glossar discovery — convention list (ordered; first match wins)
# ---------------------------------------------------------------------------

_GLOSSAR_BY_CONVENTION = (
    "brand-glossary.ts",
    "brand-glossary.js",
    ".brandignore",
    "BRAND_WORDS.md",
    "docs/brand-glossary.ts",
    "docs/brand-glossary.js",
    "docs/.brandignore",
)


def resolve_glossar(cwd: str, *, flag_path: Optional[str] = None) -> Optional[str]:
    """Discover a brand glossar by convention or flag.

    Returns the absolute path of the first matching file, or ``None`` when
    nothing is found (silent — the caller decides whether to skip).

    *flag_path* overrides convention discovery. If the flag points to a
    non-existent file ``None`` is returned.

    Walks up from *cwd* to root, checking each directory for glossar
    filenames. The closest ancestor wins (cwd first, then parent, etc.).
    """
    if flag_path:
        p = pathlib.Path(flag_path)
        return str(p.resolve()) if p.is_file() else None

    base = pathlib.Path(cwd).resolve()
    for ancestor in (base, *base.parents):
        for name in _GLOSSAR_BY_CONVENTION:
            candidate = ancestor / name
            if candidate.is_file():
                return str(candidate.resolve())
    return None


# ---------------------------------------------------------------------------
# Parser — brand-glossary.ts / .brandignore / BRAND_WORDS.md
# ---------------------------------------------------------------------------

def parse_glossar(path: str) -> Dict:
    """Parse a glossar file into ``{forbidden: [...], canonical: {term: replacement}}``.

    *forbidden* is a list of lowercase forbidden terms. *canonical* maps
    each lowercase forbidden term to its replacement string ("" when the
    term should simply be avoided with no direct substitute).
    """
    p = pathlib.Path(path)
    if p.suffix == ".ts":
        return _parse_ts_glossar(p)
    if p.name == ".brandignore":
        return _parse_brandignore(p)
    return _parse_brandignore(p)  # BRAND_WORDS.md fallback


# -- TS parser ---------------------------------------------------------------

def _extract_constants(text: str) -> Dict[str, str]:
    r"""Extract ``export const X = "value" as const;`` from TypeScript.

    Returns a dict mapping constant names to their string values.
    """
    pattern = r'export\s+const\s+(\w+)\s*=\s*"((?:[^"\\]|\\.)*)"\s+as\s+const;'
    constants: Dict[str, str] = {}
    for m in re.finditer(pattern, text):
        constants[m.group(1)] = m.group(2)
    return constants


def _find_brace_depth(s: str, start: int, open_c: str, close_c: str) -> int:
    """Bracket-count from *start* (pointing at *open_c*) to matching close.

    Returns the index just past the matching *close_c*.
    """
    depth = 1
    i = start + 1
    while i < len(s) and depth > 0:
        if s[i] == open_c:
            depth += 1
        elif s[i] == close_c:
            depth -= 1
        i += 1
    return i


def _split_objects(array_text: str) -> List[str]:
    """Split ``[ {obj1}, {obj2}, ... ]`` into individual object strings."""
    # Find first {
    brace = array_text.find("{")
    if brace < 0:
        return []
    objects: List[str] = []
    i = brace
    while i < len(array_text):
        if array_text[i] == "{":
            end = _find_brace_depth(array_text, i, "{", "}")
            objects.append(array_text[i:end])
            i = end
        else:
            i += 1
    return objects


def _extract_anti_vocabulary_entries(text: str) -> List[tuple]:
    """Extract (term, replacement_raw) pairs from the antiVocabulary array.

    Finds the ``antiVocabulary`` declaration and extracts each object's
    ``term`` and ``replacement`` fields. Replacement is kept raw (may be a
    variable reference, template literal, or string literal).
    """
    # Locate antiVocabulary then find "= [" (skip AntiVocabularyEntry[] type bracket)
    idx = text.find("antiVocabulary")
    if idx < 0:
        return []
    eq_bracket = text.find("= [", idx)
    if eq_bracket < 0:
        return []
    bracket = eq_bracket + 2  # position of the opening '['

    array_end = _find_brace_depth(text, bracket, "[", "]")
    array_text = text[bracket:array_end]

    entries: List[tuple] = []
    for obj in _split_objects(array_text):
        tm = re.search(r'term:\s*"((?:[^"\\]|\\.)*)"', obj)
        if not tm:
            continue
        term = tm.group(1)

        # Extract replacement — one of: string literal, template literal,
        # or a bare identifier, all terminated by a comma (before the next
        # field or closing brace).
        rm = re.search(
            r'replacement:\s*("(?:[^"\\]|\\.)*"|`[^`]*`|\w+)\s*,',
            obj,
        )
        replacement_raw = rm.group(1).strip() if rm else ""

        entries.append((term, replacement_raw))
    return entries


def _resolve_replacement(raw: str, constants: Dict[str, str]) -> str:
    """Resolve a raw replacement expression to a string.

    Handles:
    - Empty / "" → ""
    - String literal → unquoted value
    - Template literal with ``${var}`` → substitution via constants
    - Variable reference → lookup in constants (fallback: raw string)
    """
    raw = raw.strip()
    if not raw or raw == '""':
        return ""
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    if raw.startswith("`") and raw.endswith("`"):
        inner = raw[1:-1]

        def _sub_var(m: re.Match) -> str:
            return constants.get(m.group(1), m.group(1))

        return re.sub(r'\$\{(\w+)\}', _sub_var, inner)
    # Plain identifier — resolve from constants if possible
    return constants.get(raw, raw)


def _parse_ts_glossar(path: pathlib.Path) -> Dict:
    """Parse a TypeScript brand-glossary.ts."""
    text = path.read_text(encoding="utf-8")
    constants = _extract_constants(text)
    entries = _extract_anti_vocabulary_entries(text)

    forbidden: List[str] = []
    canonical: Dict[str, str] = {}
    seen: set = set()

    for term, replacement_raw in entries:
        fterm = term.strip().lower()
        if not fterm:
            continue
        resolved = _resolve_replacement(replacement_raw, constants)
        if fterm not in seen:
            seen.add(fterm)
            forbidden.append(fterm)
        canonical[fterm] = resolved

    return {"forbidden": forbidden, "canonical": canonical}


# -- .brandignore / plain-text parser ---------------------------------------


def _parse_brandignore(path: pathlib.Path) -> Dict:
    """Parse a newline-delimited forbidden-terms file.

    One term per line. Lines starting with ``#`` are comments.
    Replacements are always empty (the file carries no canonical mapping).
    """
    text = path.read_text(encoding="utf-8")
    forbidden: List[str] = []
    canonical: Dict[str, str] = {}
    seen: set = set()

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        fterm = line.lower()
        if fterm not in seen:
            seen.add(fterm)
            forbidden.append(fterm)
        canonical[fterm] = ""

    return {"forbidden": forbidden, "canonical": canonical}


# ---------------------------------------------------------------------------
# Conflict detector
# ---------------------------------------------------------------------------

def detect_conflicts(keywords: List[Dict], glossar: Dict) -> List[Dict]:
    """Detect brand conflicts in scored keywords.

    For each keyword, checks whether any forbidden term is a substring
    (case-insensitive). Returns conflict records sorted deterministically
    by ``(forbidden_match, term)``.

    Each record:
        ``{term, forbidden_match, replacement, opportunity, relevance,
           platform, strategies: [...]}``
    """
    if not glossar or not keywords:
        return []

    forbidden: List[str] = [f.lower() for f in (glossar.get("forbidden") or [])]
    canonical: Dict[str, str] = glossar.get("canonical") or {}
    strategies = list(STRATEGIES.keys())

    conflicts: List[Dict] = []
    for k in keywords:
        term_lower = (k.get("term") or "").lower()
        for fb in forbidden:
            if fb in term_lower:
                conflicts.append({
                    "term": k.get("term", ""),
                    "forbidden_match": fb,
                    "replacement": canonical.get(fb, ""),
                    "opportunity": k.get("opportunity", 0),
                    "relevance": k.get("relevance", 0),
                    "platform": k.get("platform", "apple"),
                    "strategies": strategies,
                })
                break  # one match per keyword (first forbidden-term wins)

    conflicts.sort(key=lambda c: (c["forbidden_match"], c["term"]))
    return conflicts
