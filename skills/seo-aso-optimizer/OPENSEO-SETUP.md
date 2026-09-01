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
# compose.yaml — from https://github.com/every-app/open-seo/blob/main/compose.yaml,
# with one deliberate change: ports bound to 0.0.0.0 instead of 127.0.0.1, because this
# NAS has no public interface (LAN-only) and AUTH_MODE=local_noauth needs LAN reachability
# from other machines to be useful at all. Never do this on an internet-facing host.
# .env — cp .env.example .env, then set:
#   DATAFORSEO_API_KEY=<base64 of "login:password" from https://app.dataforseo.com/api-access>
#   PORT=3001
#   OPENSEO_TELEMETRY_DISABLED=1
docker compose up -d
curl http://192.168.0.222:3001/api/health   # {"status":"ok", "checks": {"dataforseo": {"status":"ok"}, ...}}
```

First start builds the app in-container (~1–2 min); later starts reuse a cached build
unless `VITE_*`/auth env values change. `AUTH_MODE=local_noauth` means **no login** —
this is only acceptable because the NAS sits entirely inside the trusted home LAN with no
port-forwarding; never expose this port to the internet as configured here.

Verified end-to-end: `docker compose up -d` → healthy → a real
`serp/google/organic/live/advanced` call against the configured DataForSEO account
returned real ranked results for $0.002.

## Wiring the MCP server into an agent session

```
claude mcp add --transport http --scope user openseo http://192.168.0.222:3001/mcp
```

Takes effect in new sessions (an already-running session doesn't pick up newly
registered MCP tools). No API key/header needed for the request itself — the container's
`local_noauth` mode trusts anything that reaches it on the LAN, and the DataForSEO key
lives server-side in the container's `.env`.

## Reusing this for another project/NAS

The container and `DATAFORSEO_API_KEY` are shared infrastructure, not per-project — one
running instance serves every project on the LAN. A new project just needs
`claude mcp add ... openseo http://<nas-ip>:3001/mcp` (or `claude mcp add --scope
project` to commit that wiring into the project's own `.mcp.json` instead of the user's
global config) — the OpenSEO container/DataForSEO account never need to be duplicated per
project.

## If OpenSEO/DataForSEO isn't configured

Step 4 must degrade gracefully, not fail the run: state plainly that AI-visibility and
backlink data weren't checked (name the missing piece — no `openseo` MCP connection, or
`dataforseo` health check not `ok`), and continue with Steps 5 onward using only what
Steps 1–3 already gathered. Never fabricate a citation/backlink finding to fill the gap.
