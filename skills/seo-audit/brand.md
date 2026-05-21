# Phase 2 — Brand Consistency

This phase is the heart of v1: match the project's anti-vocabulary
table against the built HTML.

## The glossary table

The parser looks for the **first** Markdown table whose header reads
exactly `Begriff | Stattdessen | Grund` (case-insensitive) in the
first existing domain doc (`CONTEXT.md` → `CLAUDE.md` → `README.md`).
Both pipe-table forms are accepted:

```md
| Begriff | Stattdessen | Grund |
| ------- | ----------- | ----- |
| App     | Web App     | Marke ist Web-first |
```

```md
Begriff   | Stattdessen | Grund
App       | Web App     | Marke ist Web-first
```

Cells may wrap values in inline code (`` `App` ``); we strip the
backticks. Separator rows (`---`, `:---`, `---:`, `:---:`) are
skipped. Blank lines or non-pipe content end the table.

## The scan

For every `.html`/`.htm` file under `--dist`:

1. **Pre-flight suppression.** If the first 2 KB contain an HTML
   comment with `contrastiveVocabulary: true`, skip the file entirely.
2. **Strip `<script>` and `<style>` blocks** to blank lines so JS
   variable names and CSS selectors do not count as violations. Line
   numbers stay aligned with the source file.
3. **Walk line-by-line.** Toggle suppression on a line containing
   `<!-- seo-audit:contrastive -->`; resume on a line containing
   `<!-- /seo-audit:contrastive -->`. Lines inside a suppressed
   section never produce findings, including the marker lines themselves.
4. **Strip tags** to plain text per line, then match each glossary
   term with `\b<term>\b`, case-insensitive. Word boundaries prevent
   `App` from matching inside `Apple` or `Happy`.

Each match produces one finding:

```json
{
  "file_path": "<absolute path>",
  "line_number": 42,
  "match": "App",
  "suggested_replacement": "Web App",
  "rationale": "Marke ist Web-first"
}
```

Findings are returned sorted by `(file_path, line_number, match)` so
two runs over the same input are byte-identical.

## Suppression cheat sheet

| Where | Marker | Scope |
|---|---|---|
| Per file | HTML comment containing `contrastiveVocabulary: true` in the first 2 KB | Whole file |
| Per section | `<!-- seo-audit:contrastive -->` … `<!-- /seo-audit:contrastive -->` | From open marker line to close marker line (inclusive) |
| Per section (open only) | `<!-- seo-audit:contrastive -->` with no closing marker | From the open marker to end of file |

If you need a single-line escape, just wrap that line in both markers
on adjacent lines.

## What this phase does *not* do

- Score findings (that is synthesis).
- Apply fixes — the audit only reports.
- Touch source files (only built HTML under `--dist`).
- Call any network resources. Slice 02 adds Lighthouse/pa11y/GSC/etc.

## CLI surface

```bash
# 1) Parse the glossary table to JSON
python3 skills/seo-audit/scripts/glossary_parser.py from-repo <root> > glossary.json

# 2) Scan the built HTML
python3 skills/seo-audit/scripts/brand_scan.py <dist-dir> glossary.json
```

`audit.py` wires both calls together — the standalone CLIs exist for
debugging and for shell-pipeline use.
