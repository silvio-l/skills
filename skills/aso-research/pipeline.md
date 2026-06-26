# aso-research — Pipeline

The staged, cacheable, resumable pipeline. Each slice of the PRD fills
in more stages; this document records the **current (slice 03)** state
and the contracts later slices build on.

## Stages (deterministic → artefacts)

```
Input (structured YAML/JSON)
  ├─ 10  Store Discovery   ── iTunes Search API + Lookup (slice 01/02)
  │                        ── google-play-scraper: search + charts + similar (slice 04)
  ├─ 20  Metadata Collect  ── Apple Core + Slots (slice 02): subtitle via
  │                          Playwright, description from iTunes,
  │                          keyword_hints by inversion; similar-apps hop
  │                          feeds niche competitors back into the corpus
  │                          Play Core + Slots (slice 04): short + full
  │                          description (tags dropped)
  ├ 2x  Deep channels      ── Apple RSS charts, Reddit .json,
  │                          Apple + Play Search-Suggest (slice 02/04) — never-blocking
  ├─ 30  Keyword Extract   ── YAKE phrases + TF-IDF position-weighted + suggest
  │                          (per-platform field tuples: Apple 5/3/1, Play 5/4/2)
  ├─ 40  Score             ── Competition/Relevance proxy + opportunity + split + gap
  │                          (shared engine, per-platform slot weights; unified table)
  ├─ 50  Token-Budget Gate ── Python: measure + auto-trim the condensed LLM
  │                          representation under ~70k tokens (slice 03)
  ├─ 60  LLM Interpret     ── Agent-performed H1/S1/S2/H2 subagents (slice 03/04);
  │                          Claude-native, no external paid API, pinned models;
  │                          S2/H2 emit a per-store listing (Apple + Play)
  └─ 80  Report            ── Python assembles the full 8-section report.md from
                              artefacts + subagent outputs (slice 03/04)
```

Slice 03 adds the **brain**: the token-budget gate, the four LLM
subagents (performed by the running agent, not Python), and the full
8-section report. Deterministic stages (gate, condensed-input prep,
report assembly, Modus-A flagging) stay Python; the agent performs the
subagent interpretation steps.

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

- **Play slots (slice 04):** `short_description` (80 chars, strong ranking
  factor) and `full_description` (4000 chars, fully indexed), collected via
  `google-play-scraper` (`summary` → short, `description` → long, both
  HTML-stripped). **`tags` are dropped** — not reliably extractable (verified
  in the feasibility probe); the Play record carries no `tags` key.

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

## Scoring (slice 02/04 — Competition/Relevance proxy, NOT real volume)

The Competition/Relevance engine is **shared** across platforms. Each platform
maps its own slots into the same math via a per-platform slot-weight map
(``score.APPLE_SLOT_WEIGHTS`` / ``score.PLAY_SLOT_WEIGHTS``); the extraction
engine mirrors those weights (``extract.APPLE_FIELDS`` / ``PLAY_FIELDS``) so
Play's TF-IDF position weighting follows Play's model, not Apple's.

- **Competition (0–100):** ``round(100 * Σ(weight_slot * hits_slot / n_docs) / Σweights)``.
  - Apple weights: Title ×5 · Subtitle ×3 · Description ×1 (sum 9) — Apple's
    description is only *weakly* indexed.
  - Play weights: Title ×5 · Short ×4 · Long ×2 (sum 11) — Play's Short
    Description is a strong ranking factor and the Long Description is *fully*
    indexed, so both outweigh Apple's weakly-indexed description. Documented
    under the slice-04 ``decisions:`` block.
- **Relevance (0–100):** cosine TF-IDF similarity to the seed
  description, scaled to 100, **+15** if the term appears in Apple **or** Play
  Search-Suggest autocomplete; clamped to [0, 100].
- **Opportunity:** ``round(Relevance × (100 − Competition) / 100)``,
  **+10 niche bonus** if `Competition < 20 AND Relevance > 50` (strict).
- **Split:** `primary-candidate` (Relevance ≥ 50) vs `long-tail-candidate`.
- **`is_gap`:** competitors own the term in their Title but the seed
  concept lacks it.

Every scored row is tagged ``platform`` (``"apple"`` / ``"play"``) so the
**unified** ``keywords.json`` carries both verticals in one table. The table
is sorted by ``(-opportunity, -relevance, term, platform)`` — a total
deterministic order (a term may appear once per platform).

The exact boundary decisions live in named pure functions
(``competition_score`` / ``competition_score_weighted``,
``niche_bonus_applies``, ``opportunity_score``, ``split_label``) so the strict
thresholds are unit-tested directly. The report labels these
**"Competition/Relevance signal"** — never search volume.

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

## LLM interpretation phase (slice 03) — agent-performed, Claude-native

The skill is a **procedure** that runs *inside* a Claude agent — that agent
**is** the LLM. So the four subagents are **not** external API calls (no
paid key — US19, repo-wide free-tier discipline). They are
**agent-performed**: the running Claude plays each role as a subagent call
with its **model pinned explicitly** (never inherited), reads the exact
JSON input Python prepared, and emits the exact JSON schema the next stage
consumes. Python only prepares, constrains, measures, and assembles.

### Run order (orchestrator)

1. **Collect** — `uv run scripts/aso_research.py --input seed.yaml`. Writes
   the deterministic spine + `llm-input/h1-input.json` (raw per-app
   metadata) + `reddit-threads.json` + `run-config.json` + a first
   `report.md` (data sections + deterministic fallbacks for the LLM
   sections).
2. **H1** (agent) — condense `llm-input/h1-input.json` → `llm/h1-condensed.json`.
3. **Gate** — `python3 scripts/aso_research.py --gate <run-dir>`. Builds the
   token-gated S1 representation → `llm/s1-input.json` + `llm/gate-report.json`.
4. **S1** (agent) — analyse `llm/s1-input.json` → `llm/s1-analysis.json`.
5. **S2** (agent) — listing from `llm/s1-input.json` + S1 → `llm/s2-listing.json`.
6. **H2** (agent) — cross-check S2 vs the score table → `llm/h2-crosscheck.json`.
7. **Assemble** — `python3 scripts/aso_research.py --assemble <run-dir>`.
   Stitches the final 8-section `report.md`.

### Subagents (model set explicitly per call — never inherited)

| # | Subagent | **Pinned model** | Reads | Emits |
|---|---|---|---|---|
| H1 | Metadata-Condenser | **Haiku** | `llm-input/h1-input.json` (raw per-app metadata) | `llm/h1-condensed.json` — one condensed profile per app |
| S1 | Niche & Positioning Analyst | **Sonnet** | `llm/s1-input.json` (condensed profiles + score table + Reddit) | `llm/s1-analysis.json` |
| S2 | Listing Strategist | **Sonnet** | S1 analysis + score table (Apple slot model) | `llm/s2-listing.json` |
| H2 | Cross-Checker (quality gate) | **Haiku** | S2 listing vs the score table | `llm/h2-crosscheck.json` |

### Token-Budget Gate (stage 50, deterministic)

`scripts/llm_gate.py`. The LLM-input representation (condensed profiles +
score table + Reddit summaries) is measured with a dependency-free
**chars/4** token estimate and auto-trimmed under the configured limit
(default **~70k**; honour the input's `gate-token-limit`). Trim order:
condensed-profiles tail (least-relevant) → score-table tail → Reddit tail;
the score table is kept whole unless profiles are exhausted. The gate is
the hard control on context quality (US13), not wall-clock time.

### Schemas (deterministic JSON in, defined JSON out)

**Condensed profile** (H1 output, one per app):

```json
{"app_id": "324684580", "title": "Spotify …",
 "positioning": "One sentence: what it is + who it targets + the wedge.",
 "top_keywords": ["musik", "podcasts", "spotify", "streamen", "playlists"],
 "tag": "music-streaming"}
```

Raw `description` reaches H1 but **never** the later representation (the
gate measures `s1-input.json`, which carries only condensed fields).

**S1 analysis** (`llm/s1-analysis.json`):

```json
{"niches": […], "dominant_themes": […], "leader_positioning": […],
 "audiences": […], "missing_themes": […], "threats": […],
 "own_app_audit": ["…", "…"]}   // only in Modus A
```

S1 must flag **missing themes** and **threats to monitor**, grounded in
the Reddit qualitative summaries (US14).

**S2 listing** (`llm/s2-listing.json`) — Apple slots. Exactly **1 recommended
+ 2 alternatives** per slot, each with an accurate `char_count` fitting
Apple's limits out of the box (Title 30 / Subtitle 30 / hidden Keyword Field
100):

```json
{"store": "apple", "slots": [
  {"slot": "title",        "recommended": {"text": "…", "char_count": N},
                           "alternatives": [{"text": "…", "char_count": N}, …]},
  {"slot": "subtitle",     "recommended": {…}, "alternatives": […, …]},
  {"slot": "keyword_field","recommended": {…}, "alternatives": […, …]}
]}
```

Slice 04 adds a **second** listing for the Play slot model
(`llm/s2-listing-play.json`), optimised for Play's own ranking model (Title 30
/ Short 80 / Long 4000):

```json
{"store": "play", "slots": [
  {"slot": "title", "recommended": {…}, "alternatives": […, …]},
  {"slot": "short", "recommended": {…}, "alternatives": […, …]},
  {"slot": "long",  "recommended": {…}, "alternatives": […, …]}
]}
```

**H2 cross-check** (`llm/h2-crosscheck.json`) — a real gate, not a rubber
stamp (US17, DoD criterion 10). The deterministic contradiction rubric
(`scripts/crosscheck.py`) is applied **plus** semantic contradiction
checks at runtime:

```json
{"status": "ok"|"rejected",
 "findings": [{"slot", "source", "keyword", "reasons": […], "severity"}],
 "note": "…"}
```

A recommended keyword is a contradiction when its Opportunity < 20 **or**
Competition > 70 **or** (Apple Keyword Field only) it is absent from the scored
set. Play has no keyword-list slot, so an unscored word in a Play prose slot is
branding, not a contradiction. Rejected contradictions are reported, not
silently passed. The Play cross-check writes `llm/h2-crosscheck-play.json`.

### Modus A / B (no separate code path)

When the input carries `own-app-id` (Modus A), the own app is flagged
`is_own_app` and carried as **just another reference entry** in the
condensed profiles — S1/S2 compare it against the competitors and emit an
`own_app_audit`. Without it (Modus B, canonical) the self-audit is simply
absent. The flag is deterministic (`condense.own_app_is_referenced`).

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
- **Artefacts per run:** `report.md` (8 sections), `keywords.json`,
  `competition.json`, `reddit-threads.json`, `run-config.yaml`
  (human echo) + `run-config.json` (machine round-trip),
  `run-summary.json` (includes `source_status`),
  `llm-input/h1-input.json` (raw profiles for H1), and the agent-written
  `llm/{h1-condensed,s1-input,gate-report,s1-analysis,s2-listing,
  h2-crosscheck}.json`.

## Determinism

`keywords.json` and `competition.json` are byte-identical across two
runs with identical input + warm cache (stable, key-sorted, sorted-list
serialization in `scripts/serialize.py`; no timestamps inside). The gated
representation (`llm/s1-input.json`) is likewise deterministic for a given
H1 output. The `report.md` timestamp differs between runs — that is
expected and the only intentional non-determinism (besides the LLM stages
themselves, which vary within reason). Proven by `tests/aso-research/
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
- `test_llm_gate.py` — token estimation, the measure + auto-trim boundary,
  trim order (profiles before score table).
- `test_condense.py` — H1 raw-profile prep, the gated representation
  carrying no raw descriptions, Modus-A flagging.
- `test_crosscheck.py` — the H2 contradiction rubric (reject low-opp /
  high-comp / unscored Keyword-Field term; accept clean) + Apple char-count
  validation.
- `test_report_llm.py` — full 8-section assembly (all sections present,
  methodology proxy/source honesty, Modus A/B self-audit, listing
  1+2-per-slot char counts, Play listing section).
- `test_play.py` — Play schema mapping (short/full description populated,
  tags absent), Play slot weighting in the shared engine (Apple unchanged),
  unified score-table keying, Play listing char-count validation (Title 30 /
  Short 80 / Long 4000), Play Search-Suggest, Play collection orchestration
  (injectable fakes), and Apple+Play determinism.

The LLM subagent steps (H1/S1/S2/H2) are **not** unit-tested
(non-deterministic by design); their I/O schemas are asserted via the
assembly tests. The live collectors are **not** unit-tested either — they
fail loud and their output formats would rot tests (see `CLAUDE.md` →
"Tooling and testing"); they are verified by manual live-smoke runs. Run:

```bash
python3 -m unittest discover -s tests/aso-research
```
