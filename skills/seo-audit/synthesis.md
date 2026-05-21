# Phase 3 — Synthesis

Pure logic. Takes a flat list of findings from any audit module
(brand_scan, inventory hints, later: external-probes) and produces a
ranked, deduplicated, grouped `AuditReport`.

## Weights (versioned with the skill)

| Field | Allowed values | Numeric weight |
|---|---|---|
| `severity` | `high` | 3 |
| | `med` / `medium` | 2 |
| | `low` | 1 |
| `user_impact` | `1` (cosmetic) | 1 |
| | `2` (visible to most readers) | 2 |
| | `3` (blocks understanding) | 3 |
| `fix_effort` | `1` (one-line replace) | 1 |
| | `2` (touch one file) | 2 |
| | `3` (refactor across pages) | 3 |

Defaults when a field is missing: `severity=med`, `user_impact=2`,
`fix_effort=2`. These are conservative — a missing value never lifts a
finding to "top priority" by accident.

## Score formula

```
score = severity_weight * user_impact / max(fix_effort, 1)
```

Result is rounded to 4 decimal places to keep the JSON readable. The
maximum theoretical score is `9.0` (high severity × impact 3 / effort
1); the minimum is `~0.33`.

## Dedup key

`(file_path, line_number, match, category)` — two findings with the
same coordinates collapse to one. The **first** occurrence wins; that
keeps the weights from the original producer.

## Sort key

```
(-score, file_path, line_number, match.lower())
```

Score descending; then file alphabetic; then line number; then match
case-insensitive. Two runs over identical input must produce
byte-identical output — this is the **single most important property**
of the synthesis phase, because the audit report goes into git and
spurious diffs erode trust in the skill.

## Category groups

The output's `groups` field counts findings per category:

```json
[
  {"category": "brand", "count": 7},
  {"category": "seo-asset", "count": 1}
]
```

Sorted alphabetically by category for the same determinism reason.

## What this phase does *not* do

- Render Markdown. That is the report phase.
- Decide which findings to drop — every input becomes either a
  surviving finding or is collapsed via dedup.
- Mutate the inputs. The function is pure.

## CLI surface

```bash
# Read findings JSON from stdin, print synthesis JSON to stdout
cat findings.json | python3 skills/seo-audit/scripts/synthesis.py -

# Or take it from a file
python3 skills/seo-audit/scripts/synthesis.py findings.json
```
