# Phase: External Probes

Seven adapters that fetch SEO/quality data from external tools, normalise
the output into the shared `Finding` shape, and feed it into the same
synthesis pipeline as the brand-consistency findings (Slice 01).

The runtime is `scripts/probes/probe.py`:

```python
from probes import probe
findings = probe.run(urls, quick=False)   # adapters in parallel
```

`probe.run` uses `concurrent.futures.ThreadPoolExecutor` so the seven
adapters fan out concurrently. Each adapter is wrapped in a try/except
— one network blip cannot nuke a whole audit.

## Adapter inventory

| Adapter | Shell-out / SDK | Fixture | Heavy? |
|---|---|---|---|
| `lighthouse` | `npx --yes lighthouse <url> --output=json --quiet --chrome-flags="--headless=new --no-sandbox"` | `tests/seo-audit/fixtures/probes/lighthouse/sample.json` | yes |
| `pa11y` | `npx --yes pa11y <url> --runner axe --reporter json` | `tests/seo-audit/fixtures/probes/pa11y/sample.json` | yes |
| `w3c` | `curl -sS -X POST 'https://validator.w3.org/nu/?out=json'` with the page HTML | `tests/seo-audit/fixtures/probes/w3c/sample.json` | no |
| `schema` | `curl 'https://validator.schema.org/validate' --data-urlencode url=<url>` | `tests/seo-audit/fixtures/probes/schema/sample.json` | no |
| `observatory` | `curl -X POST 'https://http-observatory.security.mozilla.org/api/v1/analyze?host=<host>'` + poll + `getScanResults` | `tests/seo-audit/fixtures/probes/observatory/sample.json` | no |
| `gsc` | MCP tools `mcp__gsc__get_performance_overview`, `mcp__gsc__check_indexing_issues`, `mcp__gsc__get_search_by_page_query` | `tests/seo-audit/fixtures/probes/gsc/sample.json` | no |
| `pagespeed` | `curl 'https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url=<url>&key=$PAGESPEED_API_KEY'` | `tests/seo-audit/fixtures/probes/pagespeed/sample.json` | no |

"Heavy" adapters are skipped when the user passes `--quick`. The
remaining ones still run.

`pagespeed` is skipped silently when `PAGESPEED_API_KEY` is not set in
the environment — `run()` returns `[]` and logs the skip on stderr.

## Normaliser contract

Each adapter exposes a pure function `normalise(raw, url=…)` that takes
the parsed tool output and returns a `list[dict]` shaped like the
`Finding` dataclass consumed by `synthesis.synthesize` (Slice 01) — see
`scripts/probes/__init__.py` for the keys. The adapters do **not** set
the `score` key; synthesis fills it in.

Unit tests live in `tests/seo-audit/test_probe_<adapter>.py`. They use
the frozen fixtures listed above (a small subset of a real tool run,
with the shape source documented in the fixture header). No external
network call is made during tests.

## GSC adapter — MCP wiring

The GSC adapter consumes a single composite shape:

```json
{
  "performance":   { /* mcp__gsc__get_performance_overview */ },
  "indexing":      { /* mcp__gsc__check_indexing_issues */ },
  "low_ctr_pages": [ /* derived from mcp__gsc__get_search_by_page_query */ ]
}
```

Live wiring: write a small wrapper that runs the three MCP calls and
assembles the composite, then pass it as `gsc_client=` to
`gsc_adapter.run(url, gsc_client=...)`. The wrapper is intentionally not
part of the bundled scripts — it lives in the caller (a Claude session
with the `gsc` MCP server connected).

## Live-Smoke

Run against a real URL. Requires network and `npx` (Node) on PATH.

```bash
PAGESPEED_API_KEY=... python3 skills/seo-audit/scripts/audit.py \
  --root . --url https://whispaste.de \
  --report-dir .scratch/seo-audit-smoke
```

Expected:

* Completes in under 2 minutes.
* Produces a Markdown report under
  `.scratch/seo-audit-smoke/seo-audit-<date>.md` containing the four
  standard sections (Executive Summary, Findings nach Kategorie, Diff
  zum letzten Lauf, Empfehlungen).
* Findings include at least one entry from each available adapter.
* Adapters whose tool is missing (e.g. `npx` not installed) or whose key
  is unset (PageSpeed) are logged on stderr and contribute zero
  findings — the run still succeeds.

If the run exceeds 2 minutes, suspect `npx lighthouse` (it dominates
the budget). Try `--quick` to confirm the other six adapters complete
quickly on their own.
