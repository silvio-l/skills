# aso-research — Pipeline

The staged, cacheable, resumable pipeline. Each slice of the PRD fills
in more stages; this document records the **current (slice 01)** state
and the contracts later slices build on.

## Stages (deterministic → artefacts)

```
Input (structured YAML/JSON)
  ├─ 10  Store Discovery   ── iTunes Search API only (slice 01)
  ├─ 20  Metadata Collect  ── Apple Core only; slots empty (slice 01)
  ├─ 30  Keyword Extract   ── trivial title tokens (slice 01; real engine slice 02)
  ├─ 40  Score             ── placeholder signals (slice 01; real engine slice 02)
  ├─ 50  Token-Budget Gate ── slice 04 (no LLM in slice 01)
  ├─ 60  LLM Interpret     ── slice 04 (no LLM in slice 01)
  └─ 80  Report            ── 2 sections now (slice 01); 8 sections slice 03
```

Slice 01 deliberately de-risks the skeleton: input parsing, caching, run
identity, and the deterministic→artefact flow are proven **before** any
browser or LLM work lands.

## Per-app metadata schema (Core + Slots)

- **Core (all stores, populated in slice 01):** `id`, `platform`,
  `store_url`, `title`, `developer`, `category` (mapped to the unified
  taxonomy), `rating_avg`, `rating_count`, `last_updated`,
  `price_model`, `screenshot_count`.
- **Apple slots (emitted empty in slice 01):** `subtitle` (needs
  Playwright → slice 02 — the iTunes API does not return it),
  `description`, `keyword_hints`. They are present but empty so slice
  02 fills them in place rather than reshaping the artefact.
- **Discovery field:** `similar_app_ids[]` feeds the similar-apps
  channel (slice 02).

## Unified category taxonomy

A small explicit mapping lives in `scripts/schema.py` (`TAXONOMY`):
iTunes `primaryGenreName` → a stable slug (`music`,
`health_fitness`, `productivity`, `photo_video`, `social`, …). Unknown
genres fall back to `other` rather than passing an unmapped string
through. Add entries there as new genres surface; do not invent
synonyms downstream.

## Scoring (slice 01 — placeholder, NOT real volume)

- **Competition (0–100):** placeholder title-share — what fraction of
  discovered competitors carry the term in their title.
- **Relevance (0–100):** placeholder bias — 100 for a seed keyword, 60
  if the term appears in the seed description, else a flat 30 baseline.

Both are **deliberately coarse proxies** to prove the artefact flow. The
real Competition/Relevance formula (title×5 / subtitle×3 / desc×1
title-share, TF-IDF cosine relevance + Search-Suggest boost, niche
bonus, split flag, `is_gap`) lands in slice 02. The report labels these
as signals, never search volume.

## File layout, cache, run identity

- **HTTP response cache:** `~/.cache/aso-research/`, shared across runs,
  HTTP TTL 24h. One SHA-256-named file per canonical
  `(method, url, sorted params)` request. Freshness is mtime-based.
  Consulted before every live call; a second run within TTL makes no
  duplicate live call.
- **Run + report output:** `<output-dir>/<run-id>/` (default
  `<cwd>/.aso-research/`, overridable via `--output-dir` or the input's
  `output_dir`). Lives in the project → versionable, diffable.
- **Run-ID:** `YYYYMMDD-HHMMSS-<app-slug>`. Re-running the same seed
  produces a **new** run directory (the timestamp differs) — nothing is
  clobbered.
- **Artefacts per run:** `report.md`, `keywords.json`,
  `competition.json`, `run-config.yaml` (echoes the resolved input),
  `run-summary.json`.

## Determinism

`keywords.json` and `competition.json` are byte-identical across two
runs with identical input + warm cache (stable, key-sorted, sorted-list
serialization in `scripts/serialize.py`; no timestamps inside). The
`report.md` timestamp differs between runs — that is expected and the
only intentional non-determinism.

## ToS / free-tier discipline

Official APIs only (iTunes Search/Lookup, documented ~20/min honoured
with a 3s politeness sleep between live calls). No stealth plugins, no
proxy rotation, no aggressive crawling. A failing source is marked
unavailable and the pipeline continues — it never blocks. This honours
the repo-wide free-tier/ToS discipline.

## Dependencies

`uv` with PEP 723 inline script metadata on the dispatcher
(`scripts/aso_research.py`) — the sole third-party dependency is
`pyyaml` (for YAML input). All pure-logic modules are stdlib-only so
the offline unit tests run with plain `python3` and no installs. Later
slices add Playwright (already installed at
`~/Library/Caches/ms-playwright`).

## Testing

Offline-testable pure logic is covered by plain `unittest` at
`tests/aso-research/test_pipeline.py` (parsing, run-id, serialization,
cache-key/freshness, trivial extraction/scoring, schema mapping, and the
full collect→extract→score→serialize **determinism** path via a recorded
iTunes fixture). The live iTunes collector is **not** unit-tested — it
fails loud and its output format would rot tests (see `CLAUDE.md` →
"Tooling and testing"). Run:

```bash
python3 tests/aso-research/test_pipeline.py
```
