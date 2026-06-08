# Phase: Setup (onboarding)

Three modes that turn a fresh checkout into a working setup. None of
the three is "the audit" — they configure the tools the audit relies
on. All operations are deterministic, fully injectable in tests, and
free-tier-safe (no SaaS, no hosted dependencies, no real submissions).

| Mode | Mutually compatible | Side effects |
|---|---|---|
| `--doctor`           | with `--verify` | none — read-only |
| `--setup <tool>`     | alone (not with --doctor / --verify) | writes key file (indexnow only), opens browser (darwin only) |
| `--verify`           | with `--doctor` | one HTTP call per configured tool |

### Providing API keys

The keys below (`PAGESPEED_API_KEY`, `BING_WEBMASTER_API_KEY`, `INDEXNOW_KEY`, …)
can come straight from the environment, or — to avoid re-`export`-ing them every
run — from a dotenv file. On every invocation the dispatcher auto-loads
`<root>/admin.env` and `<root>/.env` (in that order); pass `--env-file <path>`
(repeatable) to add more, loaded ahead of the auto-detected ones. A key already
set in the live shell always wins, and missing files are skipped silently. Keep
real keys in `<root>/admin.env` (git-ignored) — never commit them.

## Mode 1 — `--doctor`

Pure read-only diagnostic. Seven check areas, in fixed order:

1. **npx tools** — `npx --version`, `npx lighthouse --version`,
   `npx pa11y --version`.
2. **IndexNow** — `INDEXNOW_KEY` env + `<public>/<key>.txt` presence
   + content match.
3. **PageSpeed** — `PAGESPEED_API_KEY` env (no probe call in doctor —
   use `--verify` for that).
4. **Bing Webmaster** — `BING_WEBMASTER_API_KEY` env.
5. **GSC MCP** — `claude mcp list` contains `mcp__gsc__*`.
6. **Domain file** — `CONTEXT.md` / `CLAUDE.md` / `README.md` exists
   and contains an Anti-Vokabular table
   (`| Begriff | Stattdessen | Grund |`).
7. **public/-path** — exists and is writable.

Output:

- A Markdown report on stdout. The top carries a **Top fix-first** list
  drawn from the `✗`-rows.
- One `### <icon> <area>` block per check area, each with a small
  status table and a one-sentence summary.

Status icons:

| Icon | Meaning |
|---|---|
| `✓` | ready |
| `⚠` | partial / fallback present |
| `✗` | missing / unconfigured |

The doctor never crashes on a missing tool: a missing `claude` CLI is
rendered as `✗ claude CLI not found`, not as a Python exception.

## Mode 2 — `--setup <tool>`

One tool at a time. Valid tool names: `indexnow`, `pagespeed`, `bing`,
`gsc`. Combining `--setup` with `--doctor` or `--verify` is a usage
error (exit code 2). The wizards do **not** call `input()` — the agent
handles confirmation per the SKILL.md prose contract.

### `--setup indexnow`

1. Detects `<public>` via `inventory.py` (Astro `dist/`, Next `out/`,
   static `public/`).
2. If `INDEXNOW_KEY` is set and `<public>/<key>.txt` matches it, the
   plan is `already_configured: True` — second run is a no-op. Use
   `--force` to regenerate.
3. Otherwise: generates `uuid.uuid4().hex.lower()`, writes the file,
   prints a `.env`-snippet.

### `--setup pagespeed`

Prints the two relevant Cloud Console URLs (credentials + API library)
and the 4-step process. On `sys.platform == "darwin"` opens both URLs
in the user's browser via `subprocess.run(["open", url])`. On every
other platform, only the URLs are emitted to the plan output.

### `--setup bing`

Prints the Bing Webmaster Tools URL and a 5-step process covering
site-verification, API-key fetch under "Settings → API access", and
the optional `BING_DAILY_LIMIT` env override for verified sites. Opens
the URL on darwin.

### `--setup gsc`

Detects whether `claude mcp list` is reachable and whether `mcp__gsc__*`
tools are registered. Prints the GSC Search Console URL, the MCP repo
URL, and the next-step command:

```bash
claude mcp call mcp__gsc__reauthenticate
```

The script never runs that command itself — the agent does, after
asking the user, per SKILL.md.

## Mode 3 — `--verify`

One minimal HTTP probe per configured tool. Quota-aware:

| Tool | Probe |
|---|---|
| PageSpeed | `GET runPagespeed?url=https://example.com&strategy=mobile&key=...` (1 call) |
| Bing | `GET GetUrlInfo?apikey=...&siteUrl=https://www.example.com&url=...` (1 call) |
| IndexNow | `HEAD https://<public_host>/<key>.txt` — **never submits a URL** |
| GSC | `mcp__gsc__list_properties` (read-only) — only when wired in |

Output is a Markdown table with one row per tool. The status field is
`OK · 200` / `401 unauthorized · 401` / `403 forbidden · 403` /
`404 not found · 404` / `429 rate-limited · 429` /
`5xx server error · <code>` / `network-error · 0`. The diagnose column
is pulled from the frozen mapping in `scripts/setup/diagnoses.py`.

IndexNow verify needs a host — pass `--url https://<host>/` so the
verifier knows where the key file should live. Without `--url`, the
IndexNow row is rendered as `_skipped_`.

## URL registry

All console-, docs- and API-endpoint URLs are constants in
`scripts/setup/urls.py`. When an upstream restructures its console,
exactly one file changes. The snapshot test
(`tests/seo-audit/test_setup_urls.py`) freezes the registry — drift
shows up as a deliberate test edit.

## Testability split

* **Unit-tested** (`tests/seo-audit/test_setup_*.py`):
  - `urls.py` — invariants + snapshot.
  - `diagnoses.py` — frozen mapping for (tool × status) ∈
    {indexnow, pagespeed, bing, gsc} × {401, 403, 404, 429}.
  - `doctor.py` — seven check areas with injected runners.
  - `setup_indexnow.py` — plan + execute + idempotency + `--force`.
  - `setup_pagespeed.py` / `setup_bing.py` / `setup_gsc.py` — plan +
    execute, darwin-vs-non-darwin browser-opener split.
  - `verify.py` — injected HTTP / MCP clients; assertion that
    IndexNow HEADs the key file URL and never POSTs to the IndexNow
    endpoint.
  - `audit.py` dispatcher — argparse cross-validation.
* **Not unit-tested**: `setup/_mcp.py` and the real `urllib`-based
  HTTP client. The `--verify` live wiring exercises both in the
  Live-Smoke section below.

## Live-Smoke

**No real keys required for doctor.** Verify uses real network calls
against minimal endpoints — safe within quotas, but counts as one
ping each. Run against a placeholder repo first:

```bash
# Pick any throwaway directory.
mkdir -p /tmp/seo-onboard-smoke && cd /tmp/seo-onboard-smoke
git init >/dev/null
mkdir public

S=~/.claude/skills/seo-audit/scripts/audit.py

# 1. Diagnose what is missing.
python3 "$S" --root . --doctor

# 2. Generate an IndexNow key (writes /tmp/seo-onboard-smoke/public/<uuid>.txt).
python3 "$S" --root . --dist public --setup indexnow

# 3. Open the PageSpeed credentials console (on darwin) or print
#    the URLs to copy-paste (elsewhere).
python3 "$S" --root . --setup pagespeed

# 4. Same for Bing.
python3 "$S" --root . --setup bing

# 5. Confirm the GSC MCP wiring.
python3 "$S" --root . --setup gsc

# 6. Verify what is reachable now.
export INDEXNOW_KEY=<the-key-from-step-2>
export PAGESPEED_API_KEY=<your-key>
export BING_WEBMASTER_API_KEY=<your-key>
python3 "$S" --root . --url https://example.com/ --verify
```

Expected for a fresh repo:

- Doctor reports `✗ indexnow`, `✗ pagespeed`, `✗ bing`, `✗ gsc`
  unless the user already exported the env vars.
- `--setup indexnow` writes one `<uuid>.txt` file and emits the
  `export INDEXNOW_KEY=...` line.
- `--setup pagespeed/bing/gsc` print step-by-step Markdown plans
  with the current URLs.
- `--verify` produces one row per tool. Rows for tools without env
  vars are rendered as `_skipped_`.

If `--verify` returns 4xx for a configured tool, the diagnose column
explains the most common cause and links to the relevant console.

## Free-tier discipline

The setup module adds **no new** SaaS / hosted dependencies. Every URL
in `urls.py` points at a free-tier-eligible service:

- PageSpeed Insights API: 25 000 requests/day free.
- Bing Webmaster URL Submission: 10 URLs/day default (10 000 verified).
- IndexNow: free, user-hosted key file, no provider quota.
- Google Search Console API via MCP: 30 000 queries/day per project.

`--verify` issues exactly **one** call per configured tool — the
smallest possible (HEAD where available, single GET otherwise). This
budget fits inside every free tier above.
