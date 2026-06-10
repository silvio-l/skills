---
name: humanize-text
description: "DE tier-1 slop word scanner for text/markdown files. Reads a file and a lexicon JSON, matches patterns case-insensitively with word-boundary anchors, and emits one Finding per match — sorted deterministically by (file_path, line_number, pattern_id) — as JSON on stdout. Walking skeleton: DE tier-1 lexicon (five curated German AI-slop phrases), deterministic JSON findings, foundation for later slices (scoring, rewrite suggestions, EN lexicon, HTML support). Use when the user says \"scan for slop\", \"check for AI phrases\", \"humanize this text\", \"find overused KI-Floskeln\", \"detect slop patterns\", or runs /humanize-text."
---

# humanize-text — DE Slop Scanner

You are the **humanizer**. You scan text and markdown files for AI-generated slop patterns, report findings, and guide the user toward more natural language.

## Walking skeleton (this slice)

This is slice 01: deterministic DE tier-1 word scan. Full orchestration, scoring, and rewrite suggestions come in later slices.

### Scanner

```bash
python3 skills/humanize-text/scripts/slop_scanner.py <file_path> <lexicon_json>
```

Prints a JSON array of findings to stdout, sorted by `(file_path, line_number, pattern_id)`.

### Finding shape (canonical — reused by all later slices)

| Key | Type | Description |
|---|---|---|
| `file_path` | str | Path passed on the CLI |
| `line_number` | int | 1-based line number |
| `match` | str | Actual matched substring (case-preserved) |
| `pattern_id` | str | Lexicon entry id |
| `type` | str | `word` or `phrase` |
| `tier` | int | Severity tier (1 = always replace) |
| `suggested_replacement` | str | Replacement suggestion (may be empty) |
| `rationale` | str | Human-readable explanation |

### Lexicon

`skills/humanize-text/lexicon.de.json` — five curated DE tier-1 entries. Pure data, separate from the engine.

## Scope

- Offline / no network access required.
- Plaintext and markdown files (no HTML tag stripping in this slice).
- DE tier-1 only (EN lexicon in a later slice).
