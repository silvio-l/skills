---
name: seo-audit
description: "Local-first, free-tier-only SEO audit for any repo with a built website. Phase pipeline: inventory (framework, pages, SEO assets, app-store listings, domain doc) → brand-consistency scan (anti-vocabulary table from CONTEXT.md/CLAUDE.md matched against built HTML, with contrastive-marker and frontmatter-flag suppression) → synthesis (dedup, score by severity × user_impact / fix_effort, deterministic tiebreaker) → write Markdown report under .scratch/<feature>/seo-audit-<date>.md. v1 is offline — external probes (Lighthouse, pa11y, GSC, W3C, Schema, Observatory) land in slice 02, push (IndexNow, Bing, llms.txt) in slice 03. Use when the user says \"SEO audit\", \"check the brand voice on the site\", \"scan dist for anti-vocabulary\", \"is our site consistent with CONTEXT.md\", \"prep an SEO report\", or runs /seo-audit."
metadata:
  argument-hint: "[--root <path>] [--dist <path>] [--report-dir <path>] [--quick] [--compare-last]"
---

# seo-audit — Local-First SEO Audit

You are the **auditor**. You inventory the repo, scan the built HTML
for brand-consistency violations, synthesize the findings into a
prioritized list, and write a single Markdown report. You do **not**
fix the findings — that is the user's call after they read the report.

## Where things live

| Concern | File |
|---|---|
| Inventory phase — framework / pages / SEO assets / app-store / domain doc | [inventory.md](inventory.md) |
| Brand-consistency phase — glossary parser, scanner, suppression rules | [brand.md](brand.md) |
| External-probes phase — seven adapters, parallel runner, live-smoke | [probes.md](probes.md) |
| Synthesis phase — weights, score formula, dedup, tiebreaker | [synthesis.md](synthesis.md) |
| Report phase — sections, template, diff mode | [report.md](report.md) |
| Report template (Markdown) | [templates/report.md](templates/report.md) |
| Dispatcher (single entry point) | [scripts/audit.py](scripts/audit.py) |
| Glossary parser | [scripts/glossary_parser.py](scripts/glossary_parser.py) |
| HTML scanner | [scripts/brand_scan.py](scripts/brand_scan.py) |
| Inventory scanner | [scripts/inventory.py](scripts/inventory.py) |
| External-probes adapters | [scripts/probes/](scripts/probes/) |
| Synthesis (pure logic) | [scripts/synthesis.py](scripts/synthesis.py) |

Read the phase doc when you enter that phase. `SKILL.md` is the
always-on layer — keep it minimal.

## Quick start

```bash
S=~/.claude/skills/seo-audit/scripts/audit.py

# Audit the current repo, write into .scratch/seo-audit/.
python3 "$S" --root .

# Audit a different repo, custom dist, diff against the prior report.
python3 "$S" --root ~/code/whispaste --dist ~/code/whispaste/build \
             --report-dir ~/code/whispaste/.scratch/seo-overhaul \
             --compare-last
```

The dispatcher prints the absolute path of the written report on
stdout. Read it back to summarize for the user.

## Phase order

1. **Inventory** — `inventory.py` walks the repo root. Output drives
   the report header and tells the brand scan where the built HTML lives.
2. **Brand scan** — `glossary_parser.py` reads the first
   `Begriff | Stattdessen | Grund` table from `CONTEXT.md` →
   `CLAUDE.md` → `README.md`. `brand_scan.py` matches every term
   case-insensitively against `dist/` (or `--dist`) on a word-boundary,
   excluding `<script>` / `<style>` blocks. Per-file frontmatter flag
   `contrastiveVocabulary: true` and per-section
   `<!-- seo-audit:contrastive -->` markers suppress matches.
3. **Synthesis** — `synthesis.py` dedups, scores each finding by
   `severity × user_impact / fix_effort`, sorts by score then by
   `(file_path, line_number, match)` for determinism.
4. **Report** — `audit.py` renders `templates/report.md` with the
   synthesis output and writes
   `.scratch/<feature>/seo-audit-<YYYY-MM-DD>.md`.

## Arguments

| Flag | Default | Behaviour |
|---|---|---|
| `--root <path>` | required | Repository root to audit. |
| `--dist <path>` | `<root>/dist` | Directory of built HTML to scan. |
| `--report-dir <path>` | `<root>/.scratch/seo-audit` | Output directory. |
| `--quick` | off | Skip the heavy probes (Lighthouse, pa11y). |
| `--url <url>` | none | Run external probes against this live URL. Repeatable. Requires network. |
| `--push` | off | Enable push module — slice 03; warns and ignores in v1. |
| `--compare-last` | off | Diff against the most recent prior report in `--report-dir`. |

## Definition of Done (single source of truth)

A `seo-audit` run is **DONE** only when **all** of the following hold:

1. The inventory section identified a framework (or `unknown` with a reason).
2. A glossary was loaded — or the report explicitly notes "no glossary found".
3. The brand scan produced a deterministic finding list — running it
   twice over the same input yields byte-identical results.
4. Suppression markers (`<!-- seo-audit:contrastive -->`,
   `contrastiveVocabulary: true` frontmatter flag) were honoured.
5. The synthesis output is sorted by score desc, with the
   `(file_path, line_number, match)` tiebreaker.
6. The report file exists under `<report-dir>/seo-audit-<YYYY-MM-DD>.md`
   with the four canonical sections: *Executive Summary*, *Findings
   nach Kategorie*, *Diff zum letzten Lauf*, *Empfehlungen*.
7. If `--url` is omitted, no external network call is made (the
   brand-scan + inventory pipeline stays fully offline). If `--url`
   is supplied, the probe layer (Slice 02) runs and its findings flow
   through the same synthesis pipeline.

## Free-tier discipline

This skill is **strictly local-first**. Without `--url`, the pipeline
makes zero network calls. With `--url`, the seven probe adapters run
through `npx` or `curl` against public endpoints with the quotas
documented below.

## Free-Tier — was kostet was?

| Tool | Cost | Quota / day | What happens past quota |
|---|---|---|---|
| Lighthouse (`npx lighthouse`) | free, runs locally | n/a — bound only by local CPU | n/a |
| pa11y (`npx pa11y`) | free, runs locally | n/a — local | n/a |
| W3C Nu validator (`validator.w3.org/nu/`) | free, no API key | no published hard cap; "polite use" — the documented guidance is ≤ 1 request/sec ([W3C Nu docs](https://github.com/validator/validator/wiki/Service-%C2%BB-HTTP-interface)) | requests rejected with HTTP 429 until the rate drops |
| Schema.org validator (`validator.schema.org`) | free, no published API contract | no published quota — polite-use convention | response throttled / shape may change without notice |
| Mozilla HTTP Observatory (`http-observatory.security.mozilla.org/api/v1/`) | free, no key | no published hard cap; results cached server-side for 24h per host ([Observatory docs](https://github.com/mozilla/http-observatory/blob/master/httpobs/docs/api.md)) | rescans before the 24h cache window return cached results |
| Google Search Console API (`mcp__gsc__*`) | free with a verified GSC property | 1 200 queries / minute, 30 000 queries / day per project ([GSC API quotas](https://developers.google.com/webmaster-tools/limits)) | HTTP 429 / quota-exceeded — wait until the next day |
| Google PageSpeed Insights API | free with API key | 25 000 requests / day, 240 requests / 100 s / user ([PSI API quotas](https://developers.google.com/speed/docs/insights/v5/get-started#quota)) | HTTP 429 — adapter logs the error and contributes `[]` |

Slice 03 adds push (IndexNow, Bing Webmaster, `llms.txt` generation),
opt-in only.

## Limitations (v1)

- **HTML-only scanning.** The scanner reads `.html`/`.htm` files under
  `--dist`. SPA-rendered content that only shows up after JS execution
  is invisible. Slice 02's Lighthouse adapter will cover that.
- **One glossary table per doc.** The parser picks the first table
  whose header reads `Begriff | Stattdessen | Grund`. If a project
  needs multiple tables, split them across the candidate files
  (`CONTEXT.md` wins over `CLAUDE.md` wins over `README.md`).
- **Markdown report only.** No HTML or PDF output. The report is
  designed to be skimmed in an editor and diffed in git.
