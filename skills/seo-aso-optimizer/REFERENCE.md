# Reference

Consulted on demand from `SKILL.md` Step 2 onward — not needed for orientation.

## Core Web Vitals thresholds

Google's official "good" bar (web.dev/vitals) — what `scripts/pagespeed_check.py` checks each metric against:

| Metric | Good | Needs improvement | Poor |
|---|---|---|---|
| LCP (Largest Contentful Paint) | ≤ 2.5s | ≤ 4s | > 4s |
| CLS (Cumulative Layout Shift) | ≤ 0.1 | ≤ 0.25 | > 0.25 |
| INP (Interaction to Next Paint) | ≤ 200ms | ≤ 500ms | > 500ms |

INP needs real-user field data (CrUX), which a low-traffic site often doesn't have enough Chrome users to populate yet — the script reports "no field data" plainly rather than faking a number, and falls back to Total Blocking Time (lab data) as the closest available proxy.

## Free tools beyond GSC, no signup

| Tool | Gives you | Needs |
|---|---|---|
| Google + YouTube autocomplete (`scripts/keyword_expand.py`) | Real long-tail keyword phrases people actually type — the free version of what paid "keyword suggestion" tools sell | Nothing — undocumented public endpoint, used respectfully (rate-limited, capped, see the script's own risk note) |
| PageSpeed Insights API (`scripts/pagespeed_check.py`) | Core Web Vitals + Lighthouse performance/SEO/accessibility scores | A free API key (Google Cloud Console, no billing account) — verified by testing: the anonymous quota is 0 requests/day, not just rate-limited |
| W3C Nu Html Checker — `https://validator.w3.org/nu/?doc=<url>&out=json` | Real markup errors the crawl script's parser can miss | Nothing — plain HTTP GET, no key, no signup |
| `mcp__gsc__*` (this environment) | Real queries, clicks, impressions, position | A Google account with the property already verified |
| Bing Webmaster Tools | The same shape of data as GSC, for Bing | A free account plus its own separate site verification — not wired into this skill (no MCP tool for it here yet); if the user already has it set up, cross-check striking-distance queries there the same way as Step 3 |
| `scripts/audit_site.py` against a competitor's domain | Their page count, schema coverage, thin-content profile, technical health — a real side-by-side, not a guess | Nothing — the script is domain-agnostic already |

Skip paid tiers (Ahrefs, SEMrush, GTmetrix's deeper checks) unless the user already has access — this skill's job is doing the free tier well, not gatekeeping behind a subscription.

### Tested and rejected — don't retry these

Each of these looked like it should work and didn't, verified live rather than assumed:

| Tool | Verdict |
|---|---|
| Google Trends' internal API (`trends.google.com/trends/api/explore`) | 429 on the very first cold request — needs session handling this workflow doesn't have. Use the trends.google.com web UI manually instead, for relative-interest comparisons only. |
| Common Crawl CDX API | Documented and genuinely free, but errored (502) on a sanity-check query against `github.com` — infrastructure looked unstable when tested. Worth a retry another day for competitor-footprint research, not something to depend on. |
| OpenLinkProfiler.org | 404 even against `wikipedia.org` and `github.com` — the service itself is not responding correctly right now, not a "no data for a small site" result. |
| Bing's undocumented autosuggest endpoint | Returned an empty body on a plain query — either deprecated or needs parameters this workflow doesn't have. Google/YouTube autocomplete already covers this need. |

### Search volume, honestly

There is no free, precise, per-keyword search volume number. Anyone offering one for free is estimating. What's actually available:
- **GSC impressions** (already core to Step 3) are ground truth — but only for queries the site already surfaces for at all. Useless for a keyword the site has never ranked for once.
- **Google Ads Keyword Planner** gives real (if bucketed) volume ranges, genuinely free — but needs a Google Ads account (no ad spend required) and has no simple scriptable path (OAuth + a developer token with an approval process). Treat it as a manual, occasional cross-check, not something this skill automates.
- **Autocomplete presence/ordering** (`keyword_expand.py`) and SERP "related searches" (visible via `WebSearch`) are directional only — a phrase showing up at all, or showing up early, means real people search it, not how many.

Say this plainly to the user rather than presenting a volume-flavored number that's actually a guess.

### Backlinks

No free, reliable, programmatic backlink source exists (see "tested and rejected" above). The free web UIs some tools offer (Ahrefs' capped backlink checker, Moz's limited free tier) are manual, one-off lookups a human runs in a browser — not something to script into this workflow.

## Meta-length thresholds

Match the constants in `scripts/audit_site.py`; if you tighten one, tighten both.

| Field | Flagged outside | Practical sweet spot |
|---|---|---|
| `<title>` | < 30 or > 65 chars | ~50–60 chars — enough for a keyword + brand, short of Google's truncation point |
| meta description | < 70 or > 160 chars | ~150–160 chars — a full, compelling sentence that doesn't get cut |

A title/description outside range isn't automatically wrong (a two-word brand name is a legitimate 15-char title) — the script flags it for a human decision, it doesn't fail the page.

## Striking distance, precisely

A **striking-distance** query is one search visibility push away from page 1: position roughly 5–15 in `mcp__gsc__get_search_analytics`, with real impressions (a query with 1–2 impressions over 28 days is noise, not a target), and a CTR visibly below what that position normally earns (position 1 typically clears 25–30% CTR, position 10 is closer to 2–3% — a query sitting at position 6 with 1% CTR is under-converting for its rank, meaning the *title/description*, not the ranking, is the fix; a query at position 12 with average CTR for that position needs a *ranking* fix instead).

Distinguish the two failure modes before prescribing a fix:
- **Ranks OK, converts badly** → rewrite the title and meta description. See "Writing the fix" below — "rewrite the title" is not a fix, the rewritten title is.
- **Doesn't rank high enough** → the owning page needs more topical depth, better internal links pointing to it, or doesn't exist yet.

### Writing the fix, not just naming it

"Rewrite the title to match intent better" is not a deliverable — it's a restatement of the problem. For every "ranks OK, converts badly" query, produce the actual replacement title and meta description text, plus one sentence on why each specific change earns the click that the old one didn't. Check the length against the thresholds above before presenting it.

Rewriting the snippet does not cost reach — ranking position drives impressions, not the title text, so nobody who currently sees the listing stops seeing it. The only question is which of those impressions become clicks. That means there's no real tension between "I want more visitors" and "fix the snippet": a clearer snippet keeps the same audience and converts more of it, it doesn't narrow who's reached.

When the striking-distance query collides with a competitor's product name (someone else's tool ranks for the literal words, and this site's page is being served instead or alongside it), don't assume the audience is simply "the same, just needs convincing" — check what that competitor's product actually is (its own site or repo usually says platform, category, pricing in the first paragraph) before writing the fix. If it turns out to solve a genuinely different problem (a batch file-processing tool vs. a live-input tool, a Windows-only tool vs. a cross-platform one), an honest snippet that names the difference outperforms a vague one that lets the searcher assume a match: it correctly draws the click from whoever actually wants what this page offers, instead of wasting the impression on a click that bounces in three seconds either way.

## Short-tail vs. long-tail

- **Short-tail**: 1–2 generic words ("learn piano"). Massive search volume, near-impossible competition, and often the wrong intent for a specific product.
- **Long-tail**: a specific phrase matching what one user actually typed ("learn to recognize piano notes by ear"). Far fewer searches, far less competition, and a much higher chance both of ranking and of the visitor actually converting.

Favor long-tail for any page targeting a specific feature, use case, location, or problem. Reserve short-tail ambition for the homepage/brand terms only.

## Schema.org types by page kind

| Page | Primary `@type` |
|---|---|
| Homepage (business/product site) | `Organization` + `WebSite` |
| Homepage (app companion site) | `SoftwareApplication` (desktop apps too) or `MobileApplication` (mobile only) |
| Guide / how-to page | `Article` or `HowTo` |
| FAQ page or FAQ section | `FAQPage` |
| Service + location page (local business) | `LocalBusiness` (or the closer subtype, e.g. `AutoRepair`) |
| Blog post | `Article` |

One JSON-LD block per page is normal; a page can combine types (e.g. `WebSite` + `Organization` via `@graph`) but shouldn't carry contradictory types for the same entity.

## GSC dimension combinations

`mcp__gsc__get_search_analytics` dimensions, by question:

| Question | `dimensions` |
|---|---|
| Which queries drive traffic overall? | `query` |
| Which page ranks for which query? (needed for striking-distance → owning-page mapping) | `query,page` |
| Is a page underperforming on mobile specifically? | `page,device` |
| Is a query strong in one market but not another? | `query,country` |
| Is a change (fix, new page) moving the needle over time? | `date` alongside a fixed `query` or `page` filter, compared across two `days` windows |

## Page templates

**Hero → How it works → Guides → FAQ → CTA** (companion site for an app, or any product with distinct use cases):
1. **Hero** — product name and primary keyword in the headline (the first thing both Google and the visitor read), download/CTA buttons, a screenshot, a review or two.
2. **How it works** — short, concrete, talks to both the visitor and the crawler about what the product actually does.
3. **Guides** — one page per long-tail keyword, structured as: the user's actual problem → how to solve it → how the product does that step for them. This is where most of the indexable long-tail surface area lives.
4. **FAQ** — one entry per specific query a user would type into Google, a short answer, a "learn more" link into the matching guide.
5. **CTA + footer** — repeat the download/contact action; footer carries the standard legal/nav links.

**Service × location depth** (local business with multiple services and/or service areas): one page per service-location combination, each with genuine local detail (landmarks, locally common problems, area-specific FAQs) rather than a templated mad-lib — thin, near-duplicate location pages are a Step 2 `thin_content` finding waiting to happen, and Google treats them as low-value.
