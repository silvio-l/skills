# Phase: Push (opt-in)

Three push operations, all opt-in via `--push`, all confirmable per
operation by the agent, all `--dry-run`-safe.

| Operation | Endpoint / output | Env vars |
|---|---|---|
| `indexnow`     | `POST https://api.indexnow.org/IndexNow` | `INDEXNOW_KEY` |
| `bing`         | `POST https://ssw.live.com/webmaster/api.svc/json/SubmitUrl?apikey=<k>` | `BING_WEBMASTER_API_KEY`, optional `BING_DAILY_LIMIT` |
| `llms`         | writes `<public>/llms.txt` + `<public>/llms-full.txt` | _none_ |

The orchestrator lives in `scripts/push/push.py`. Each adapter exposes
`plan(...)` and `execute(...)`. The real HTTP client (urllib stdlib) is
in `scripts/push/_http.py` — adapters take an injected client so unit
tests stay fully offline.

## Operation 1 — IndexNow

Submits a batch of URLs in a single POST. Setup contract:

1. The user generates a key (any UUID-like string — IndexNow accepts
   8-128 hex chars). Set it as `INDEXNOW_KEY` in the deploy environment.
2. The user creates a key file at `<public_dir>/<key>.txt` containing
   exactly the key. After the next deploy this file is reachable at
   `https://<host>/<key>.txt` and IndexNow uses it to verify ownership.
3. The adapter never writes this file. If it is missing, `plan()`
   returns `ready: False` with a `first_setup_hint`.

Body shape POSTed:

```json
{
  "host":        "<bare host>",
  "key":         "<INDEXNOW_KEY>",
  "keyLocation": "https://<host>/<key>.txt",
  "urlList":     ["https://<host>/page-a", "..."]
}
```

200/202 means accepted. 422 typically means key file missing or
mismatched — re-check the setup contract.

## Operation 2 — Bing Webmaster URL Submission

One POST per URL. Endpoint:

```
https://ssw.live.com/webmaster/api.svc/json/SubmitUrl?apikey=<BING_WEBMASTER_API_KEY>
```

Body:

```json
{"siteUrl": "<site_url>", "url": "<page_url>"}
```

Quota safety lives **inside the skill**: a per-day counter file at
`<report-dir>/seo-audit-bing-counter-<YYYY-MM-DD>.json`. Defaults:

* `BING_DAILY_LIMIT` env var if set,
* otherwise 10/day (Bing's documented default for unverified sites).

If today's count + planned batch exceeds the limit, the batch is
clipped to the remaining budget and a warning is attached to the plan.
The counter is **only** incremented on a real `execute` — `dry-run`
leaves it untouched. The counter is local, optimistic, and resets at
midnight; it cannot detect submissions Bing accepted outside this
tool. Verified sites should set `BING_DAILY_LIMIT=10000`.

## Operation 3 — `llms.txt` / `llms-full.txt` generator

Per https://llmstxt.org/:

* `llms.txt` — Title, blockquote summary, `## Docs` list, optional
  `## Optional` section. Short, designed for the LLM to fetch first.
* `llms-full.txt` — concatenation of the domain doc plus every `*.md`
  file under `docs/`. Designed for one-shot ingestion.

Source priority: `CONTEXT.md` → `CLAUDE.md` → `README.md` (the same
domain-doc resolution as the inventory phase). Output lands in the
framework's public directory: `dist/` for Astro, `out/` for Next,
`public/` for static sites. Auto-detected by `audit.py`.

The generator is pure and idempotent — running it twice on the same
input yields byte-identical files.

## Setup checklist (per site, once)

| Step | What to do |
|------|------------|
| 1 | Generate a key for IndexNow (`uuidgen` or any 8-128 hex chars). |
| 2 | Place `<key>.txt` in `public/` (or your framework's static dir) containing the key. |
| 3 | Set `INDEXNOW_KEY=<key>` in your shell or `.envrc`. |
| 4 | Sign up for Bing Webmaster Tools, fetch the API key, set `BING_WEBMASTER_API_KEY`. |
| 5 | If your Bing site is verified, set `BING_DAILY_LIMIT=10000`. |

Steps 4 and 5 are independent of step 1-3. You can run IndexNow alone
(or vice versa); the skill plans them independently.

## Live-Smoke

**Real keys required. This hits production APIs and counts against
Bing quota.**

```bash
export INDEXNOW_KEY=<your-key>
export BING_WEBMASTER_API_KEY=<your-key>
# Optional, only if your Bing site is verified:
# export BING_DAILY_LIMIT=10000

S=~/.claude/skills/seo-audit/scripts/audit.py

# Dry run first — see the plan, no network, no writes.
python3 "$S" --root . --url https://example.com/ \
             --report-dir .scratch/seo-audit-push-smoke \
             --push --dry-run

# Real run — the dispatcher prints the plan; you then walk the agent
# through confirmation per module, and the agent calls
# push.execute_all() with the confirmations dict.
python3 "$S" --root . --url https://example.com/ \
             --report-dir .scratch/seo-audit-push-smoke \
             --push
```

Expected (real run):

* IndexNow POST returns 200 or 202.
* Bing POSTs each return 200 (or 4xx with a "URL submitted recently"
  body — still a successful no-op).
* `llms.txt` and `llms-full.txt` appear in the public dir.

If IndexNow returns 422: re-verify the key file is reachable at
`https://<host>/<key>.txt` and matches `$INDEXNOW_KEY` byte-for-byte.

If Bing returns "URL submission failed: Your daily quota has been
exceeded" before the local counter says you should be clipped, your
Bing account has its own server-side counter (or you've submitted
outside the skill). Wait until UTC midnight and try again.

## Testability split

* **Unit-tested** (`tests/seo-audit/test_push_*.py`):
  `plan()`, `execute()` with an injected fake client, the orchestrator,
  the dry-run renderer, and `llms_generator.generate()`. All offline.
* **Not unit-tested**: `scripts/push/_http.py` (the real urllib client).
  It is covered only by the live-smoke command above.
