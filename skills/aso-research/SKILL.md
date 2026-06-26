---
name: aso-research
description: "ASO research pipeline: a structured app-idea becomes a competitor + keyword report (Apple first). /aso-research procedure. Triggers: ASO Analyse, Konkurrenz-Recherche für meine App, Keywords für meine App, ASO-Recherche, App Store Optimierung"
disable-model-invocation: true
metadata:
  argument-hint: "[--input <seed.yaml|json>] [--app-name <name> --description <text>] [--seed-keyword <kw> ...] [--country <de>] [--language <de>] [--own-app-id <id>] [--output-dir <dir>] [--gate-token-limit <n>] [--fresh] [--max-queries <n>]"
---

# aso-research — Local-First ASO Pipeline

You are the **research orchestrator**. Given a structured app-idea input
(app name, description, category guess, country, language, optional own
app id, optional seed keywords), you run a staged, cacheable,
**deterministic** pipeline that collects public competitor intelligence,
extracts and scores keywords with transparent proxy metrics, and writes
an evidence-based ASO report. The LLM only interprets the compressed
result — it never does the data collection. No paid SaaS, no serverless,
no stealth scraping.

This is a **procedure** (`disable-model-invocation: true`): invoke it
deliberately via `/aso-research`. German trigger phrases are kept here
for readers but are not in the model's auto-load context (zero ambient
tokens), consistent with `ratchet-up` / `ship-to-*`.

## Where things live

| Concern | File |
|---|---|
| Pipeline stages, metadata schema, cache layout, run-id format | [pipeline.md](pipeline.md) |
| Dispatcher (single entry point; run via `uv run`) | [scripts/aso_research.py](scripts/aso_research.py) |
| Structured-input parsing + validation | [scripts/input_config.py](scripts/input_config.py) |
| Run-identity (`YYYYMMDD-HHMMSS-<app-slug>`) | [scripts/run_id.py](scripts/run_id.py) |
| HTTP response cache (~/.cache/aso-research/, 24h HTTP / 12h browser TTL) | [scripts/cache.py](scripts/cache.py) |
| Shared politeness rule-set (≤1 req/s + jitter, backoff, robots, no stealth) | [scripts/politeness.py](scripts/politeness.py) |
| iTunes Search + Lookup collector (Apple Core metadata) | [scripts/itunes.py](scripts/itunes.py) |
| Apple subtitle + similar-apps collector (Playwright, 12h cache) | [scripts/apple_browser.py](scripts/apple_browser.py) |
| Apple RSS Marketing-Tools charts collector | [scripts/apple_rss.py](scripts/apple_rss.py) |
| Reddit `.json` qualitative-signal collector | [scripts/reddit.py](scripts/reddit.py) |
| Apple Search-Suggest autocomplete collector | [scripts/search_suggest.py](scripts/search_suggest.py) |
| Google Play collector (google-play-scraper via npx; search/charts/similar/suggest) | [scripts/play.py](scripts/play.py) |
| Microsoft Store best-effort collector (Playwright, SPA-aware; qualitative-only) | [scripts/ms.py](scripts/ms.py) |
| Deep Apple collection orchestration (never-blocking, injectable) | [scripts/collect.py](scripts/collect.py) |
| Unified category taxonomy + raw→Core+Slots schema mapping | [scripts/schema.py](scripts/schema.py) |
| Keyword extraction (YAKE + TF-IDF position-weighted + suggest) | [scripts/extract.py](scripts/extract.py) |
| Scoring (Competition/Relevance proxy, opportunity, split, is_gap) | [scripts/score.py](scripts/score.py) |
| LLM-input prep (H1 raw profiles + token-gated S1 representation, Modus-A flag) | [scripts/condense.py](scripts/condense.py) |
| Token-Budget Gate (measure + auto-trim under ~70k, chars/4 estimate) | [scripts/llm_gate.py](scripts/llm_gate.py) |
| H2 contradiction rubric + per-store slot char-count validation (Apple + Play) | [scripts/crosscheck.py](scripts/crosscheck.py) |
| Stable serialization (byte-identical determinism) | [scripts/serialize.py](scripts/serialize.py) |
| Report assembly (full 8 sections from artefacts + subagent outputs) | [scripts/report.py](scripts/report.py) |

Read `pipeline.md` before running. `SKILL.md` is the always-on layer —
keep it minimal; push per-stage detail into phase docs.

## Quick start

```bash
S=~/.claude/skills/aso-research/scripts/aso_research.py

# Structured input (YAML or JSON).
uv run "$S" --input seed.yaml

# Or build the input from flags.
uv run "$S" --app-name "Habit Hero" \
            --description "A gamified habit tracker" \
            --seed-keyword habit --seed-keyword tracker \
            --country de --language de
```

The dispatcher prints the absolute path of the written run directory on
stdout. **Open `report.md` and verify it** before declaring the run
done. The canonical design source is the PRD at
`.scratch/aso-research/PRD.md`.

## The LLM phase (agent-performed, Claude-native)

This skill runs **inside** a Claude agent — that agent *is* the LLM, so
the four subagents are **not** external API calls (no paid key — US19).
The dispatcher prepares the deterministic spine + the token-gated
representation; **you** (the running agent) perform the subagent steps
with the **model pinned explicitly per call**:

- **H1 Metadata-Condenser — Haiku** → `llm/h1-condensed.json`
- **S1 Niche & Positioning Analyst — Sonnet** → `llm/s1-analysis.json`
- **S2 Listing Strategist — Sonnet** → `llm/s2-listing.json` (Apple: 1 + 2 per slot, char counts)
- **H2 Cross-Checker — Haiku** → `llm/h2-crosscheck.json` (reject contradictions)

Stitch between them with the deterministic stages:

```bash
S=~/.claude/skills/aso-research/scripts/aso_research.py
uv run "$S" --input seed.yaml        # spine + llm-input/h1-input.json
# … run H1 (Haiku) → llm/h1-condensed.json …
python3 "$S" --gate   <run-dir>      # token-gated s1-input.json
# … run S1 (Sonnet) → s1-analysis.json, S2 → s2-listing.json, H2 → h2-crosscheck.json …
python3 "$S" --assemble <run-dir>    # full 8-section report.md
```

The exact JSON schemas, the gate limits, the H2 thresholds
(Opportunity ≥ 20, Competition ≤ 70), and the Modus A/B handling are in
[pipeline.md](pipeline.md) → "LLM interpretation phase".

## Current scope (slice 04 — Google Play vertical)

Slice 04 adds **Google Play** as a complete second vertical alongside Apple,
reusing the shared scoring engine and the LLM listing path:

- **Play discovery + metadata** via `google-play-scraper` (Node, through
  `npx`): seed-keyword search, category charts, and the similar-apps graph.
  Play Core + Slots carry `short_description` (80, strong ranking factor) and
  `full_description` (4000, fully indexed). **`tags` are dropped** (not
  reliably extractable).
- **Shared scoring engine.** Play keywords flow into the SAME score table as
  Apple (`keywords.json` / `competition.json` carry `platform: apple` **and**
  `platform: play` rows), scored with Play's own position weighting
  (Title ×5 · Short ×4 · Long ×2 — distinct from Apple's 5/3/1). The engine
  is generalised over a per-platform slot-weight map; Apple's numeric outputs
  are unchanged.
- **Unified Search-Suggest.** Play autocomplete is collected alongside
  Apple's and merged into one suggest set (the +15 relevance boost applies to
  either store's terms).
- **Play listing (S2/H2).** The Listing Strategist emits a Play-specific
  listing (`llm/s2-listing-play.json`: 1 recommended + 2 alternatives per
  Play slot, char counts fitting Title 30 / Short 80 / Long 4000),
  cross-checked by H2 (`llm/h2-crosscheck-play.json`). The report renders
  both an Apple and a Google Play listing section.
- **Never-blocking.** A failing Play source is marked `"unavailable"` and the
  pipeline continues (Apple-only result when Play is down).

The LLM subagent mechanism itself (H1/S1/S2/H2 call flow, pinned models) is
unchanged from slice 03 — only the listing/crosscheck now also covers the
Play slot model.

- **Microsoft Store best-effort (slice 05).** `apps.microsoft.com` is a
  single-page app, so the MS collector ([scripts/ms.py](scripts/ms.py)) drives
  Playwright with `networkidle` + `wait_for_selector`. It collects MS Core
  metadata + the `description` slot only — there is **no MS ASO slot model**.
  MS is **qualitative-only and structurally isolated**: its entries
  (`ms-entries.json`) are kept OUT of the scoring `competitors` corpus and
  never reach keyword extraction/scoring; they are wired into the S1
  representation (`llm/s1-input.json` → `qualitative_ms`) as additional
  qualitative context. MS is the lowest-priority, most fragile source and is
  **never-blocking** — on failure it is marked `"unavailable"`, the report
  notes it, and Apple + Play results stay intact. Same shared politeness
  rule-set as the other Playwright collectors (≤1 req/s + jitter, backoff on
  429/503, robots.txt, no stealth). Resumability/diff remain a later slice.
