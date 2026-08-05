---
name: seo-aso-optimizer
description: "Audit and optimize a website for SEO, AEO/GEO (AI search), and ASO — crawl checks, Search Console striking-distance keywords, page fixes, or an app's companion site. Use for 'SEO', 'ASO', 'bei Google ranken', 'Suchmaschinenoptimierung', 'GSC'."
---

# SEO / AEO / ASO Optimizer

Audits and improves an existing website's chances of ranking on Google/Bing and being cited by AI answer engines (ChatGPT, Gemini, Google AI Overviews). The object being optimized is always a **website** — either the site the user already has, or a companion site built for an app that doesn't have one yet (see the branch below). Optimizing a native store listing itself (title, subtitle, keyword field, store screenshots — App Store, Play Store, Microsoft Store, or any other) is out of scope.

Work through the steps below in order. Each ends on a completion criterion — don't move to the next step until it's met.

## Step 1 — Identity and scope

Establish: the site's audience, its 2–3 core offerings/pages, and its brand voice (ask the user, or read existing About/positioning content). If the object is an **app without a marketing website** (or only a thin landing page), read `APP-TO-WEBSITE.md` first — it covers pulling keywords from the store listing and the hero/guides/FAQ page structure that gets built before this skill's steps apply — then continue at Step 2 once that site exists.

**Done when:** you can state the audience, the core offerings, and which path applies, in one sentence each.

## Step 2 — Technical audit (deterministic)

Run the crawl script — it hits every page in the sitemap and checks fixed rules (titles, meta descriptions, H1s, canonical, lang, viewport, structured data validity, alt text, thin content, orphan pages, broken internal links, accidental `noindex` directives, missing compression, robots.txt/sitemap/llms.txt presence). No LLM judgment happens inside it, so the same site always yields the same findings:

```
python3 skills/seo-aso-optimizer/scripts/audit_site.py https://example.com --out-dir <workdir>
```

Read the findings-first report (grouped by rule, most-violated first) printed to stdout and saved as `<workdir>/findings.md`. **Do not read `<workdir>/audit-data.json` up front** — it's the full per-page sidecar, meant for drilling into one specific rule or URL once you already know which one matters.

Then check page speed — the crawl script only covers correctness/structure, not load performance, and slow pages both rank worse and convert worse:

```
python3 skills/seo-aso-optimizer/scripts/pagespeed_check.py https://example.com/ --strategy mobile
```

Needs a free `PAGESPEED_API_KEY` (see the script's docstring) — the anonymous quota is 0 requests/day, not just rate-limited. Run it at minimum against the homepage and the page with the most GSC impressions; more pages if the user asks for a full performance pass. `REFERENCE.md` has the Core Web Vitals thresholds the script checks against.

**Done when:** every rule group in `findings.md` has been triaged — fix now, defer with a reason, or false-positive with a reason — and the page-speed check has run at least once, with any Core Web Vital outside Google's "good" threshold triaged the same way.

## Step 3 — Search Console reality check

If the GSC MCP tools are connected, call them in this order:

1. `mcp__gsc__list_properties` — get the exact `site_url` (domain properties look like `sc-domain:example.com`).
2. `mcp__gsc__get_search_analytics` with `dimensions="query,page"`, `days=28`, `row_limit=200` — the real query and page data.
3. `mcp__gsc__get_sitemaps` — cross-check against what Step 2 found on disk.
4. `mcp__gsc__check_indexing_issues` for any URL Step 2 flagged as orphaned or broken.

From the query,page rows, find **striking-distance** queries: position roughly 5–15, with real impressions (not 1–2 flukes), and CTR below what that position normally earns. These are the site's highest-ROI targets — a small push moves them onto page 1. If GSC isn't connected yet, tell the user it would sharpen targeting, and continue with Step 4 using AI-suggested keywords only.

For each one, classify it per `REFERENCE.md`'s two failure modes — but classify from evidence, not from the query text alone: fetch the owning page's actual current content (not just the audit script's title/meta/word-count fields) and run one `WebSearch` for the literal query to see what's really competing for it, before deciding why it under-converts. A "ranks OK, converts badly" query needs the actual replacement title/meta text and a one-sentence reason each change earns the click, grounded in what Steps 3 actually found on the page and in the SERP — see `REFERENCE.md`'s "Writing the fix". Never hand back "improve the title" as the answer, and never diagnose a mismatch you haven't confirmed by reading the page.

While you have a page's full query,page breakdown open, check whether it's actually the top query that needs the fix — a lower-ranked query on the same page can be the bigger opportunity (e.g. a transactional-intent query landing on a page that buries its call-to-action).

For competitor analysis: `audit_site.py` is domain-agnostic — run it against a real competitor found via the `WebSearch` calls above (`--out-dir` somewhere separate) to compare page count, schema coverage, and technical health side by side with no new tooling needed.

**Done when:** every striking-distance query is mapped to an owning page (or explicitly declined with a reason), every "converts badly" diagnosis cites the actual page content and SERP context that support it, and every one carries real replacement copy, not a description of what the copy should do.

## Step 4 — Keyword-to-page map

Merge three inputs into one map — each target keyword owned by exactly one page (existing or "to create"):
- Step 3's striking-distance queries.
- Step 2's thin-content and orphan pages (they may just need a clearer keyword target).
- A harvested candidate list from `scripts/keyword_expand.py <seed>` — real Google/YouTube autocomplete completions, not an invented brainstorm. Run it against 1–3 seed phrases central to the site, then sort what it returns by intent (emergency/transactional/informational/local) and favor long-tail over short-tail — a specific, low-competition phrase beats a generic, saturated one. Expect real noise in the output (autocomplete pulls in unrelated senses of ambiguous words); discard it rather than force-fitting it. See `REFERENCE.md` for the short-tail/long-tail split, page templates for new pages, and what "search volume" honestly means for a free workflow.

**Done when:** no target keyword is unmapped, and no single page is asked to own more than one primary keyword.

## Step 5 — Fix (gated on human sign-off)

Propose concrete diffs for every Step 2 finding not already deferred. Show them to the user before applying — never auto-publish. This is exactly the point where an unsupervised agent produces confident, wrong content; don't skip the gate even when the fix looks mechanical.

**Done when:** every FAIL entry in `findings.md` is either fixed or carries an explicit "declined: reason" note.

## Step 6 — Content

For each page in the Step 4 map that needs new or rewritten copy: lead with the answer to the target query in the first paragraph (this is what gets an AI answer engine to quote the page), then go deeper — real specifics, not generic filler. Run drafts through the `avoid-ai-writing` skill before finalizing; don't restate its rules here. Add structured data per `REFERENCE.md`'s schema-type table and confirm it parses (re-run Step 2's script, or check `https://validator.schema.org`).

**Done when:** every page in the Step 4 map has been written or explicitly skipped, and every new/changed page's structured data validates.

## Step 7 — Ship and verify

If Step 2/3 found no sitemap in Search Console, or a stale one, submit it with `mcp__gsc__submit_sitemap`. Re-run the Step 2 script and confirm the finding groups touched in Step 5 are gone (or still explicitly declined). For a recurring check (e.g. fortnightly striking-distance refresh), the `schedule` skill can run this workflow on a cron cadence.

**Done when:** the re-audit's `findings.md` shows no new regressions against Step 5's fixes.

## Reference

`REFERENCE.md` — meta-length thresholds, striking-distance thresholds in detail, the schema.org type table, GSC dimension combinations, and page templates. Load it at Step 4 or Step 6, not before — it's detail those steps need, not orientation.

`APP-TO-WEBSITE.md` — the branch for apps without a marketing site: pulling keywords from a store listing and the hero/guides/FAQ structure that turns them into indexable pages.
