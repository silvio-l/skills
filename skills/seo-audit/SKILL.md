---
name: seo-audit
description: "Local-first, free-tier SEO + GEO/AEO audit: brand scan, entity/citability signals, JSON-LD schema, external probes (Lighthouse/GSC/PageSpeed), /100 scored report, optional --push. Use when you need an SEO audit, /seo-audit, GEO-Audit, Schema-Check."
metadata:
  argument-hint: "[--root <path>] [--dist <path>] [--report-dir <path>] [--brief <path>] [--quick] [--url <url>] [--push] [--dry-run] [--compare-last] [--doctor] [--setup <tool>] [--verify] [--force]"
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
| GEO/AEO scan phase — entity page, citable prose, FAQ, heading structure, llms.txt | [geo.md](geo.md) |
| Schema/JSON-LD audit phase — presence, required fields, deprecated types, sameAs | [schema.md](schema.md) |
| External-probes phase — seven adapters, parallel runner, live-smoke | [probes.md](probes.md) |
| Push phase — IndexNow, Bing Webmaster, llms.txt; confirmation flow | [push.md](push.md) |
| Setup-Onboarding phase — `--doctor` / `--setup <tool>` / `--verify` | [setup.md](setup.md) |
| Synthesis phase — weights, score formula, dedup, tiebreaker, headline score | [synthesis.md](synthesis.md) |
| Report phase — sections, template, diff mode, Strategisch/Technisch split | [report.md](report.md) |
| Report template (Markdown) | [templates/report.md](templates/report.md) |
| Dispatcher (single entry point) | [scripts/audit.py](scripts/audit.py) |
| Glossary parser | [scripts/glossary_parser.py](scripts/glossary_parser.py) |
| HTML scanner | [scripts/brand_scan.py](scripts/brand_scan.py) |
| Inventory scanner | [scripts/inventory.py](scripts/inventory.py) |
| GEO/AEO scanner | [scripts/geo_scan.py](scripts/geo_scan.py) |
| Schema/JSON-LD scanner | [scripts/schema_scan.py](scripts/schema_scan.py) |
| Positioning-brief loader (`--brief`) | [scripts/positioning_brief.py](scripts/positioning_brief.py) |
| External-probes adapters | [scripts/probes/](scripts/probes/) |
| Push adapters (IndexNow / Bing / llms.txt) | [scripts/push/](scripts/push/) |
| Setup-Onboarding (doctor + wizards + verify) | [scripts/setup/](scripts/setup/) |
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
stdout. **Open that file and verify it before declaring the run done** —
confirm it actually contains all four canonical sections (per
[report.md](report.md)) and the findings table; exit 0 alone is not proof
the report is well-formed. Only then read it back to summarize for the user.

## Phase order

1. **Inventory** — `inventory.py` walks the repo root. Output drives
   the report header and tells downstream phases where the built HTML lives.
2. **Brand scan** — `glossary_parser.py` reads the first
   `Begriff | Stattdessen | Grund` table from `CONTEXT.md` →
   `CLAUDE.md` → `README.md`. `brand_scan.py` matches every term
   case-insensitively against `dist/` (or `--dist`) on a word-boundary,
   excluding `<script>` / `<style>` blocks. Per-file frontmatter flag
   `contrastiveVocabulary: true` and per-section
   `<!-- seo-audit:contrastive -->` markers suppress matches.
3. **GEO/AEO scan** — `geo_scan.py` checks entity/citability signals:
   About-page presence, citable prose blocks (≥ 60 chars), FAQ/Q&A
   structures, heading structure (H1 count, hierarchy, pseudo-headings),
   and `llms.txt` / `llms-full.txt` presence. All checks are offline;
   findings carry `dimension=geo`. Heavy checks (prose, FAQ) are skipped
   under `--quick`.
4. **Schema/JSON-LD scan** — `schema_scan.py` extracts all
   `<script type="application/ld+json">` blocks, validates JSON, checks
   required-field completeness for 7 core types (via versioned
   `REQUIRED_FIELDS_V1`), flags deprecated types (`DEPRECATED_TYPES_V1`),
   and checks sameAs social-profile consistency. All checks are offline;
   findings carry `dimension=schema`. Files with `contrastiveVocabulary:
   true` in an HTML comment are excluded.
5. **Positioning brief (optional)** — `positioning_brief.py` loads brand
   context from `--brief <path>`, or auto-discovers from
   `<root>/.seo/positioning.md` or a `<!-- seo:brief -->` fenced section
   in `CONTEXT.md`. The brief is **never** used by finding-producing
   phases — it only flows into the report's recommendation section.
6. **External probes** — run when `--url <url>` is passed. Seven adapters
   (Lighthouse, pa11y, W3C, Schema.org validator, Observatory, GSC,
   PageSpeed) fan out concurrently. Requires network.
7. **Synthesis** — `synthesis.py` dedups (key: `file_path, line_number,
   match, category, dimension`), scores each finding by
   `severity × user_impact / fix_effort`, computes a per-dimension
   breakdown and a `/100` headline score via versioned
   `DIMENSION_WEIGHTS_V1`, and sorts deterministically.
8. **Report** — `audit.py` renders `templates/report.md` with the
   synthesis output and writes
   `.scratch/<feature>/seo-audit-<YYYY-MM-DD>.md`. Recommendations are
   split into **Strategisch** (track=strategic, content/entity decisions)
   and **Technisch** (track=technical, automatable fixes) sections, with
   copy-paste-ready fix snippets for JSON-LD and llms.txt findings.

## Arguments

| Flag | Default | Behaviour |
|---|---|---|
| `--root <path>` | required | Repository root to audit. |
| `--dist <path>` | `<root>/dist` | Directory of built HTML to scan. |
| `--report-dir <path>` | `<root>/.scratch/seo-audit` | Output directory. |
| `--brief <path>` | none | Path to a Markdown positioning brief. Provides brand context for the recommendation section only — never affects findings or score. Auto-discovered from `<root>/.seo/positioning.md` or a `<!-- seo:brief -->` fenced section in `CONTEXT.md` when absent or unreadable. |
| `--quick` | off | Skip heavy per-file GEO checks (prose analysis) and the site-wide FAQ scan; skip the heavy probes (Lighthouse, pa11y). |
| `--url <url>` | none | Run external probes against this live URL. Repeatable. Requires network. |
| `--push` | off | Enable push module (IndexNow, Bing Webmaster, llms.txt). Opt-in; the agent confirms each operation with the user before firing it. |
| `--dry-run` | off | Only valid with `--push`: render the push plan to stdout without performing any submissions or writes. |
| `--compare-last` | off | Diff against the most recent prior report in `--report-dir`. |
| `--doctor` | off | Setup-Onboarding diagnostic — read-only env / file / probe inspection. Mutually compatible with `--verify`. See [setup.md](setup.md). |
| `--setup <tool>` | none | Single-tool setup wizard. Valid tools: `indexnow`, `pagespeed`, `bing`, `gsc`. Not combinable with `--doctor` / `--verify`. See [setup.md](setup.md). |
| `--verify` | off | One minimal probe call per configured tool, returning per-tool OK/4xx/5xx status. Mutually compatible with `--doctor`. See [setup.md](setup.md). |
| `--force` | off | Force-regenerate setup artefacts (currently only honoured by `--setup indexnow`). |

## Definition of Done (single source of truth)

A `seo-audit` run is **DONE** only when **all** of the following hold:

1. The inventory section identified a framework (or `unknown` with a reason).
2. A glossary was loaded — or the report explicitly notes "no glossary found".
3. The brand scan produced a deterministic finding list — running it
   twice over the same input yields byte-identical results.
4. Suppression markers (`<!-- seo-audit:contrastive -->`,
   `contrastiveVocabulary: true` frontmatter flag) were honoured by both
   the brand scan and the schema scan.
5. The GEO/AEO scan ran over the same `--dist` directory and produced
   findings with `dimension=geo`. Two runs over identical input yield
   byte-identical results.
6. The Schema/JSON-LD scan ran over the same `--dist` directory and
   produced findings with `dimension=schema`. Two runs over identical
   input yield byte-identical results.
7. The synthesis output carries a `/100` `headline_score` and a
   per-dimension `dimensions_breakdown` (one score per dimension in
   `DIMENSION_WEIGHTS_V1`). The findings are sorted by score desc, with
   the `(file_path, line_number, match, dimension)` tiebreaker.
8. The report file exists under `<report-dir>/seo-audit-<YYYY-MM-DD>.md`
   with these canonical sections: *Executive Summary* (headline score +
   dimensions breakdown), *Findings nach Kategorie*, *Diff zum letzten
   Lauf*, *Empfehlungen* (Strategisch / Technisch / Fix-Snippets).
9. The positioning brief (if loaded) appears only in the
   *Positionierungs-Kontext* subsection of the report — it never alters
   the finding list, scores, or synthesis output.
10. Recommendations are split: *Strategisch (du entscheidest)* lists
    findings with `track=strategic` (content/entity decisions the human
    must make); *Technisch (umsetzbar)* lists `track=technical` findings
    (automatable one-file or copy-paste fixes).
11. Fix snippets (copy-paste-ready JSON-LD blocks, llms.txt skeleton)
    are present in the report for every finding whose fix is
    deterministically derivable from the finding data.
12. If `--url` is omitted, no external network call is made (the entire
    brand/GEO/schema pipeline stays fully offline). If `--url` is
    supplied, the probe layer runs and its findings flow through the same
    synthesis pipeline.
13. If `--push` is passed, **no submission or file write happens until
    the agent has asked the user, per operation, and received an
    explicit confirmation.** The script never prompts; the agent does.
    `--push --dry-run` is side-effect-free.

## Push confirmation flow (binding for the agent)

When the user passes `--push`, the dispatcher prints a structured plan
to stdout. Before executing **any** operation, you (the agent) must:

1. Read the plan back to the user in plain prose — name each module,
   show what would be submitted, and surface every warning and
   `first_setup_hint`.
2. Ask **once per module**: "Should I run the IndexNow push to
   `<host>`?" — wait for an explicit yes/no.
3. Only call `push.execute_all(plans, clients=..., confirmations=...)`
   with `confirmations[module] = True` for the modules the user
   confirmed. Modules the user declined stay `False` and are skipped
   silently.
4. If a module's plan is `ready: False`, do not even ask — read the
   `reason` / `first_setup_hint` to the user and move on.

The script intentionally has no `input()` call. That keeps the
confirmation in your conversational control where it belongs.

## Free-tier discipline

This skill is **strictly local-first**. Without `--url`, the pipeline
makes zero network calls. With `--url`, the seven probe adapters run
through `npx` or `curl` against public endpoints with the quotas
documented below.

## Free-Tier — was kostet was?

| Tool | Cost | Quota / day | What happens past quota |
|---|---|---|---|
| GEO/AEO scanner (`geo_scan.py`) | free, runs locally | n/a — local HTML walk | n/a |
| Schema/JSON-LD scanner (`schema_scan.py`) | free, runs locally | n/a — local HTML walk | n/a |
| Positioning-brief loader (`positioning_brief.py`) | free, local file read | n/a — local | n/a |
| Lighthouse (`npx lighthouse`) | free, runs locally | n/a — bound only by local CPU | n/a |
| pa11y (`npx pa11y`) | free, runs locally | n/a — local | n/a |
| W3C Nu validator (`validator.w3.org/nu/`) | free, no API key | no published hard cap; "polite use" — the documented guidance is ≤ 1 request/sec ([W3C Nu docs](https://github.com/validator/validator/wiki/Service-%C2%BB-HTTP-interface)) | requests rejected with HTTP 429 until the rate drops |
| Schema.org validator (`validator.schema.org`) | free, no published API contract | no published quota — polite-use convention | response throttled / shape may change without notice |
| Mozilla HTTP Observatory (`http-observatory.security.mozilla.org/api/v1/`) | free, no key | no published hard cap; results cached server-side for 24h per host ([Observatory docs](https://github.com/mozilla/http-observatory/blob/master/httpobs/docs/api.md)) | rescans before the 24h cache window return cached results |
| Google Search Console API (`mcp__gsc__*`) | free with a verified GSC property | 1 200 queries / minute, 30 000 queries / day per project ([GSC API quotas](https://developers.google.com/webmaster-tools/limits)) | HTTP 429 / quota-exceeded — wait until the next day |
| Google PageSpeed Insights API | free with API key | 25 000 requests / day, 240 requests / 100 s / user ([PSI API quotas](https://developers.google.com/speed/docs/insights/v5/get-started#quota)) | HTTP 429 — adapter logs the error and contributes `[]` |
| IndexNow (`api.indexnow.org`) | free, no provider key — user generates and self-hosts the key file | no published per-day cap; one POST submits a batch of URLs ([IndexNow docs](https://www.indexnow.org/documentation)) | malformed requests rejected; missing key file → HTTP 4xx |
| Bing Webmaster URL Submission API | free, `BING_WEBMASTER_API_KEY` from Webmaster Tools | 10 URLs / day default for unverified sites; 10 000 / day for verified ([Bing docs](https://learn.microsoft.com/en-us/bingwebmaster/getting-access)) | HTTP 4xx; the skill clips the batch via a local date-rolled counter (`BING_DAILY_LIMIT` env overrides) |
| `llms.txt` / `llms-full.txt` (local file) | free; generated locally | n/a — purely local file write | n/a |

Push (IndexNow, Bing Webmaster, `llms.txt`) is opt-in via `--push` and
confirmed per operation. See [push.md](push.md).

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
