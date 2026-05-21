# Phase 4 — Report

The final phase. Takes the synthesis output, fills the template, and
writes one Markdown file to disk.

## Output path

```
<report-dir>/seo-audit-<YYYY-MM-DD>.md
```

Default `<report-dir>` is `<root>/.scratch/seo-audit/`. Override with
`--report-dir`. A repeated run on the same day overwrites the day's
report — there is intentionally **no append**, so re-runs converge on a
deterministic single artifact.

## Sections (in order)

1. **Header** — date, root, framework, domain doc.
2. **Executive Summary** — pages scanned, glossary size, total
   findings, top category, one-sentence prose lede pointing at the
   top-scoring finding.
3. **Findings nach Kategorie** — one subsection per category. Each
   carries a table with `Score | Datei:Zeile | Match | Vorschlag |
   Begründung`. Findings already arrive sorted by score; the table
   preserves that order.
4. **Diff zum letzten Lauf** — empty when no prior report exists or
   `--compare-last` was not passed. Even then, the header stays so the
   section ordering is stable.
5. **Empfehlungen (Hebel × Aufwand)** — the top 10 findings rephrased
   as bullet recommendations. A footer line counts the overflow.

## Diff mode

`--compare-last` looks for the most recent `seo-audit-<date>.md` in
`--report-dir` whose date prefix is **strictly less than today**. If
found, the *Diff* section names it; full diff rendering is a TODO for
slice 02 (it benefits from external-probe context). In v1 the section
is intentionally a placeholder — that is documented behaviour, not a
bug.

## Template substitution

The template at `templates/report.md` uses `{{key}}` placeholders. The
`audit.py` dispatcher fills them with:

| Placeholder | Source |
|---|---|
| `{{date}}` | `today` |
| `{{root}}` | `inventory.root` |
| `{{framework}}` | `inventory.framework` |
| `{{domain_doc}}` | `inventory.domain_doc` |
| `{{pages_count}}` | `len(inventory.pages)` |
| `{{glossary_count}}` | `len(glossary)` |
| `{{findings_count}}` | `len(synthesis.findings)` |
| `{{top_category}}` | highest-count category from `synthesis.groups` |
| `{{summary_prose}}` | computed sentence about top finding |
| `{{findings_by_category}}` | rendered tables, one per category |
| `{{diff_section}}` | diff placeholder or empty notice |
| `{{recommendations}}` | top 10 bullets + overflow line |
| `{{generator_version}}` | constant in `audit.py` |

## Idempotency contract

Running `audit.py` twice over the same input must yield two reports
whose contents differ only in the timestamped filename, never in the
body. The synthesis phase guarantees deterministic ordering; the
report phase guarantees no nondeterministic strings sneak in (no
`datetime.now()` inside the body — only the date in the header).

## CLI surface

The report phase has no standalone CLI; it is always reached via
`audit.py`. To inspect the template:

```bash
cat skills/seo-audit/templates/report.md
```
