# OpenSEO / DataForSEO setup (optional, paid)

Loaded from `SKILL.md` Step 4 the first time it's needed — this is setup documentation,
not orientation. Everything in this skill's Steps 1–3, 5–8 works with zero cost and zero
setup; this file only applies to the AI-Search/GEO + backlinks + rank-tracking layer.

## What this adds

[every-app/open-seo](https://github.com/every-app/open-seo) is a self-hostable
TypeScript app (Cloudflare Workers stack, runs fine in plain Docker) that wraps the
[DataForSEO](https://dataforseo.com) API behind an MCP server and a small web dashboard.
It has no data of its own — every keyword/SERP/backlink/AI-visibility number comes from
DataForSEO, pay-per-call. OpenSEO's own value-add is the MCP tool surface (agent-callable)
plus a dashboard for manual inspection.

This is what closes the two gaps the free-tier steps of this skill cannot: **backlinks**
(no reliable free source exists — see `REFERENCE.md`) and **AI Search / GEO visibility**
(whether ChatGPT/Gemini/Perplexity/Google AI Overviews actually cite a page — not
observable at all without a real LLM-with-web-search call).

## Cost — say this plainly to the user before enabling

Pure pay-as-you-go against a DataForSEO account, no OpenSEO subscription needed for
self-hosting. A DataForSEO account needs a **minimum $50 top-up**; a single SERP/keyword
call costs roughly $0.002–$0.01, a `llm_responses` call (the AI-visibility check) a few
cents depending on `max_output_tokens`. $50 covers many hundreds of audit runs at this
skill's usage pattern. There is no free tier for real calls (a sandbox mode exists for
testing request shapes only, not real data). Never enable Step 4 silently — tell the user
what a run will roughly cost before making calls that spend money, and skip the step
entirely if no `DATAFORSEO_API_KEY` is configured.

## NAS deployment (already done for this environment — reference only)

Deployed on `silvio222` (`ssh silvio222`, see
`~/.claude/infrastructure/nas-silvio222.md`), Docker Compose, port `3001` (80/443 already
taken by other services on this NAS).

```
mkdir -p ~/docker/open-seo
# compose.yaml — from https://github.com/every-app/open-seo/blob/main/compose.yaml.
# .env — cp .env.example .env, then set at minimum:
#   DATAFORSEO_API_KEY=<base64 of "login:password" from https://app.dataforseo.com/api-access>
#   PORT=3001
#   OPENSEO_TELEMETRY_DISABLED=1
docker compose up -d
curl http://192.168.0.222:3001/api/health   # {"status":"ok", "checks": {"dataforseo": {"status":"ok"}, ...}}
```

First start builds the app in-container (~1–2 min); later starts reuse a cached build
unless `VITE_*`/auth env values change.

**Auth model (since 2026-09-01): `AUTH_MODE=cloudflare_access`, not `local_noauth`.** The
container sits behind the existing Cloudflare Tunnel (`ugreen_nas`) and a Cloudflare
Access application at `https://openseo.silvio-lindstedt.de`, with Access's Managed OAuth
enabled so MCP clients (Claude Code) can authenticate via Dynamic Client Registration —
the same public hostname works both from the LAN and from anywhere else, always behind
Access login (email allowlist: `silvio-lindstedt@outlook.com`,
`lindstedt.online@gmail.com`). No unauthenticated LAN-only mode is running anymore. Full
setup (tunnel ingress, Access app/policy, Managed OAuth config, propagation-delay gotcha):
`~/.claude/infrastructure/cloudflare.md` → „Zero Trust Access — App OpenSEO".

`.env` additionally carries `GOOGLE_CLIENT_ID`/`GOOGLE_CLIENT_SECRET`/
`BETTER_AUTH_SECRET` for OpenSEO's built-in Google Search Console integration (Connect
under the dashboard's Integrations tab) — OAuth client details in
`~/.claude/infrastructure/google-cloud-silvio-infra-tools.md`.

Verified end-to-end: `docker compose up -d` → healthy → a real
`serp/google/organic/live/advanced` call against the configured DataForSEO account
returned real ranked results for $0.002.

## Wiring the MCP server into an agent session

```
claude mcp add --transport http --scope user openseo https://openseo.silvio-lindstedt.de/mcp
claude mcp login openseo   # opens a browser for the Cloudflare Access (OTP) login
```

Takes effect in new sessions (an already-running session doesn't pick up newly
registered MCP tools). The login step is required once per machine/credential-store —
`claude mcp list` shows `Needs authentication` until then. If `claude mcp login` runs
non-interactively (no TTY), wrap it: `script -q /dev/null claude mcp login openseo` in
the background, then open the printed authorization URL in a browser to complete it.

## Reusing this for another project/NAS

The container and `DATAFORSEO_API_KEY` are shared infrastructure, not per-project — one
running instance serves every project. A new project just needs `claude mcp add
--transport http openseo https://openseo.silvio-lindstedt.de/mcp` (`--scope user` for
global, `--scope project` to commit that wiring into the project's own `.mcp.json`)
followed by `claude mcp login openseo` — the OpenSEO container/DataForSEO account never
need to be duplicated per project. A genuinely separate deployment (different NAS/account)
would need its own Cloudflare Access app + Managed OAuth setup following the same pattern.

## If OpenSEO/DataForSEO isn't configured

Step 4 must degrade gracefully, not fail the run: state plainly that AI-visibility and
backlink data weren't checked (name the missing piece — no `openseo` MCP connection, or
`dataforseo` health check not `ok`), and continue with Steps 5 onward using only what
Steps 1–3 already gathered. Never fabricate a citation/backlink finding to fill the gap.
