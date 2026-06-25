# aso-research — Pipeline

The staged, cacheable, resumable pipeline. Each slice of the PRD fills
in more stages; this document records the **current (slice 02)** state
and the contracts later slices build on.

## Stages (deterministic → artefacts)

```
Input (structured YAML/JSON)
  ├─ 10  Store Discovery   ── iTunes Search API + Lookup (slice 01/02)
  ├─ 20  Metadata Collect  ── Apple Core + Slots (slice 02): subtitle via
  │                          Playwright, description from iTunes,
  │                          keyword_hints by inversion; similar-apps hop
  │                          feeds niche competitors back into the corpus
  ├ 2x  Deep channels      ── Apple RSS charts, Reddit .json,
  │                          Apple Search-Suggest (slice 02) — never-blocking
  ├─ 30  Keyword Extract   ── YAKE phrases + TF-IDF position-weighted + suggest
  ├─ 40  Score             ── Competition/Relevance proxy + opportunity + split + gap
  ├─ 50  Token-Budget Gate ── slice 04 (no LLM yet)
  ├─ 60  LLM Interpret     ── slice 03/04 (no LLM yet)
  └─ 80  Report            ── Competitive Landscape + Keyword Report + Sources
                             (slice 02); full 8 sections slice 03
```

Slice 02 deepens the deterministic spine: real extraction + scoring, the
Apple subtitle + similar-apps niche channel, and the chart/Reddit/suggest
collectors — all under the politeness rule-set, never-blocking.

## Per-app metadata schema (Core + Slots)

- **Core (all stores, populated):** `id`, `platform`, `store_url`,
  `title`, `developer`, `category` (mapped to the unified taxonomy),
  `rating_avg`, `rating_count`, `last_updated`, `price_model`,
  `screenshot_count`.
- **Apple slots (populated in slice 02):**
  - `subtitle` — scraped via Playwright (the iTunes API does **not**
    return it); filled by `schema.merge_apple_slots`.
  - `description` — from the iTunes `description` field (HTML stripped).
  - `keyword_hints` — inferred by **inversion** (distinctive title/
    subtitle terms), never the hidden 100-char field.
- **Discovery field:** `similar_app_ids[]` feeds the similar-apps hop;
  discovered niche competitors carry `discovery: "niche_similar"`.

## Unified category taxonomy

A small explicit mapping lives in `scripts/schema.py` (`TAXONOMY`):
iTunes `primaryGenreName` → a stable slug (`music`, `health_fitness`,
`productivity`, `photo_video`, `social`, …). Unknown genres fall back
to `other`. Add entries there as new genres surface; do not invent
synonyms downstream.

## Keyword extraction (slice 02 — real, no LLM)

Three deterministic layers (`scripts/extract.py`):

1. **Position-weighted single terms** — Title ×5, Subtitle ×3,
   Description ×1; per-doc field hit sets feed the scorer's Competition.
2. **YAKE phrases** — dependency-free YAKE ranks bigram/trigram
   candidates from the high-signal fields (single words are weak for
   ASO); used only to *select* a bounded phrase set.
3. **Search-Suggest enrichment** — autocomplete terms merged in as
   first-class candidates.

Processing: DE + EN stopwords, lowercasing, min frequency ≥2, generics
filter ("app", "iphone", "android", category name), light morphology
grouping (singular/plural/declension merged via variant-set stemming +
umlaut normalisation; most frequent original form kept as the display
term).

## Scoring (slice 02 — Competition/Relevance proxy, NOT real volume)

- **Competition (0–100):** `round(100 × (5×title_share + 3×sub_share + 1×desc_share) / 9)`.
- **Relevance (0–100):** cosine TF-IDF similarity to the seed
  description, scaled to 100, **+15** if the term appears in Apple
  Search-Suggest autocomplete; clamped to [0, 100].
- **Opportunity:** `round(Relevance × (100 − Competition) / 100)`,
  **+10 niche bonus** if `Competition < 20 AND Relevance > 50` (strict).
- **Split:** `primary-candidate` (Relevance ≥ 50) vs `long-tail-candidate`.
- **`is_gap`:** competitors own the term in their Title but the seed
  concept lacks it.

The exact boundary decisions live in named pure functions
(`competition_score`, `niche_bonus_applies`, `opportunity_score`,
`split_label`) so the strict thresholds are unit-tested directly. The
report labels these **"Competition/Relevance signal"** — never search
volume.

## Bot-detection & rate-limit policy (politeness rule-set)

- Official APIs (iTunes Search/Lookup ~20/min, Apple RSS, Reddit `.json`
  ~60/min) are the default.
- Playwright-scraped parts (Apple subtitle/similar) run under
  `scripts/politeness.py`: realistic UA + locale `de-DE`; **≤1 req/s/
  domain + 0.5–2s jitter**; HTTP cache 24h / browser cache 12h;
  exponential backoff on 429/503 (max 3, then skip); `robots.txt`
  respected; retry-budget then **never-blocking** (failing source →
  "unavailable", pipeline continues).
- **No stealth plugins** (no playwright-stealth/Camoufox/fingerprint
  spoof/proxy). Moderation over extraction.

## File layout, cache, run identity

- **HTTP response cache:** `~/.cache/aso-research/`, shared across runs,
  HTTP TTL 24h / browser TTL 12h. One SHA-256-named file per canonical
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
  `run-summary.json` (includes `source_status`).

## Determinism

`keywords.json` and `competition.json` are byte-identical across two
runs with identical input + warm cache (stable, key-sorted, sorted-list
serialization in `scripts/serialize.py`; no timestamps inside). The
`report.md` timestamp differs between runs — that is expected and the
only intentional non-determinism. Proven by `tests/aso-research/
test_determinism.py` (fixture) and by paired live runs over a warm cache.

## Dependencies

`uv` with PEP 723 inline script metadata on the dispatcher
(`scripts/aso_research.py`) and the browser collector
(`scripts/apple_browser.py`): `pyyaml` (YAML input) + `playwright`
(Chromium is already installed at `~/Library/Caches/ms-playwright`).
All pure-logic modules are stdlib-only so the offline unit tests run
with plain `python3` and no installs.

## Testing

Offline-testable pure logic is covered by plain `unittest` under
`tests/aso-research/` (outside `skills/`):

- `test_pipeline.py` — parsing, run-id, serialization, cache, schema
  Core mapping, extract/score smoke, and the full collect→extract→score
  →serialize **determinism** path via a recorded iTunes fixture.
- `test_extraction.py` — umlauts, hyphenation, contractions, morphology
  grouping, stopwords/generics, min-frequency, position weighting, YAKE
  phrases, Search-Suggest enrichment.
- `test_scoring.py` — Competition normalisation + division-by-zero,
  Opportunity off-by-one, the **strict niche-bonus boundary** (both
  sides of Competition<20 / Relevance>50), suggest boost, split, is_gap.
- `test_schema.py` — description HTML stripping, subtitle mis-fielding,
  keyword_hints inversion, browser-slot merge.
- `test_collect.py` — deep-collection orchestration with injected
  fakes: source-status tracking, never-blocking, niche merge/dedup.
- `test_determinism.py` — feed fixture Apple metadata through
  extract→score→serialize twice, byte-identical.

The live collectors are **not** unit-tested — they fail loud and their
output formats would rot tests (see `CLAUDE.md` → "Tooling and
testing"); they are verified by manual live-smoke runs. Run:

```bash
python3 tests/aso-research/test_*.py
```
