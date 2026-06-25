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
| HTTP response cache (~/.cache/aso-research/, 24h TTL) | [scripts/cache.py](scripts/cache.py) |
| iTunes Search collector (Apple Core metadata) | [scripts/itunes.py](scripts/itunes.py) |
| Unified category taxonomy + raw→Core schema mapping | [scripts/schema.py](scripts/schema.py) |
| Keyword extraction (trivial in slice 01; real engine slice 02) | [scripts/extract.py](scripts/extract.py) |
| Placeholder scoring (real Competition/Relevance slice 02) | [scripts/score.py](scripts/score.py) |
| Stable serialization (byte-identical determinism) | [scripts/serialize.py](scripts/serialize.py) |
| Minimal report assembly (2 sections in slice 01; 8 sections slice 03) | [scripts/report.py](scripts/report.py) |

Read `pipeline.md` before running. `SKILL.md` is the always-on layer —
keep it minimal; push per-stage detail into phase docs that later
slices fill in.

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

## Current scope (slice 01 — skeleton)

This slice proves the whole loop on the thinnest possible end-to-end
path: **Apple only**, **iTunes Search API only** (no Playwright, no
charts, no Reddit), **trivial title-token extraction** with a
**placeholder** relevance/competition signal, and a **2-section**
report. The real engine (YAKE/TF-IDF), Apple subtitle, other stores,
and the LLM interpretation land in later slices. Do not over-build here.
