# Phase 3 — GEO / AEO Scan

Generative Engine Optimisation (GEO) and Answer Engine Optimisation
(AEO) signals. Runs fully offline over the built HTML in `dist/`; no
network call is made. Produces findings with `dimension='geo'`.

Script: `scripts/geo_scan.py`.

## What gets checked

### Site-level checks (always run)

| Check | Pass condition | Finding when absent |
|---|---|---|
| About / Entity page | An HTML file whose URL path contains an about-like keyword (`about`, `ueber`, `entity`, `team`, …), OR any heading on any page matches a who-is-X pattern (`Wer ist …`, `About us`, `Über uns`, …) | `geo-entity` — highest-priority AEO miss |
| `llms.txt` / `llms-full.txt` | Either file is present at the `dist/` root | `geo-llms` — low severity, one-line fix |

### Per-file checks (always run)

| Check | Pass condition | Finding when failing |
|---|---|---|
| Single H1 | Exactly one `<h1>` tag per page | `geo-headings` (missing or duplicate H1) |
| Heading hierarchy | No level skipped (e.g. h1 → h3 without h2) | `geo-headings` (hierarchy skip) |
| Semantic headings | No `<div>` / `<span>` with a heading-level CSS class acting as a pseudo-heading | `geo-headings` |

### Checks skipped under `--quick`

| Check | Pass condition | Finding when absent |
|---|---|---|
| Citable prose | At least one `<p>` tag with ≥ 60 stripped characters of plain text | `geo-prose` |
| FAQ / Q&A structure | Any `<details>/<summary>`, `<dl>/<dt>`, or heading whose text contains a FAQ keyword (`FAQ`, `Häufig`, `Q&A`, …) anywhere in the site | `geo-faq` |

## Tracks and their rationale

Each finding carries a `track` that controls which recommendation bucket
it lands in:

| Track | Rationale | Example findings |
|---|---|---|
| `strategic` | A content or editorial decision only the project owner can make | About-page missing, no citable prose, no FAQ |
| `technical` | A markup change that can be made without content decisions | Missing H1, hierarchy skip, pseudo-heading, `llms.txt` skeleton |

## Finding shape

```json
{
  "file_path": "<absolute path or dist_root>",
  "line_number": 0,
  "match": "keine About-/Entity-Seite",
  "suggested_replacement": "Eine dedizierte About-/Entity-Seite …",
  "rationale": "Eine 'Über uns'-Seite ist der wichtigste AEO-Hebel …",
  "category": "geo-entity",
  "severity": "high",
  "user_impact": 3,
  "fix_effort": 3,
  "dimension": "geo",
  "track": "strategic"
}
```

`line_number` is `0` for site-level checks (no single source line).

## Suppression

There is currently no per-file suppression for GEO findings — the
`contrastiveVocabulary: true` convention from `brand_scan` does not
apply here. If a page is deliberately thin (e.g. a legal disclaimer with
no prose), the finding will appear; the user must ignore it.

## Determinism contract

Two calls to `geo_scan.scan_directory(dist_root)` with the same
`dist_root` contents must return byte-identical JSON. The implementation
achieves this by:

1. Sorting `os.walk` traversal: `dirs.sort()` + `sorted(files)`.
2. Sorting the final finding list by `(file_path, line_number,
   match.lower())` — the same tiebreaker as `brand_scan`.

## CLI surface

```bash
# Standalone: print findings JSON to stdout
python3 skills/seo-audit/scripts/geo_scan.py <dist-dir>

# Skip heavy checks
python3 skills/seo-audit/scripts/geo_scan.py <dist-dir> --quick
```

`audit.py` calls `geo_scan.scan_directory(dist, quick=args.quick)`
directly; the standalone CLI exists for debugging.

## What this phase does *not* do

- FAQPage Schema.org markup — that belongs to the schema scan (slice 03
  / `schema_scan.py`).
- Score findings — that is synthesis.
- Apply fixes — the audit only reports.
- Make any network call.
