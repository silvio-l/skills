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
| Deep Apple collection orchestration (never-blocking, injectable) | [scripts/collect.py](scripts/collect.py) |
| Unified category taxonomy + raw→Core+Slots schema mapping | [scripts/schema.py](scripts/schema.py) |
| Keyword extraction (YAKE + TF-IDF position-weighted + suggest) | [scripts/extract.py](scripts/extract.py) |
| Scoring (Competition/Relevance proxy, opportunity, split, is_gap) | [scripts/score.py](scripts/score.py) |
| Stable serialization (byte-identical determinism) | [scripts/serialize.py](scripts/serialize.py) |
| Report assembly (Competitive Landscape + Keyword Report + Sources) | [scripts/report.py](scripts/report.py) |

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

## Current scope (slice 02 — deep Apple spine)

Slice 02 deepens the deterministic spine end to end on **Apple only**:
real keyword extraction (YAKE phrases + TF-IDF with position weighting
Title ×5 · Subtitle ×3 · Description ×1, DE+EN stopwords, generics
filter, min frequency ≥2, light morphology grouping, Apple Search-Suggest
enrichment) and the real scoring engine (Competition = position-weighted
share, Relevance = cosine TF-IDF + Search-Suggest boost, Opportunity +
niche bonus, primary/long-tail split, `is_gap`). Collectors: iTunes
Search + Lookup, Apple subtitle + similar-apps (Playwright), Apple RSS
charts, Reddit `.json`, Apple Search-Suggest — all under the politeness
rule-set, **never-blocking** (a failing source is marked "unavailable"),
**no stealth plugins**. The report gains a real **Keyword Report**
section labelled "Competition/Relevance signal" (never search volume).
No Google Play, no Microsoft, no LLM yet (slices 03–05).
