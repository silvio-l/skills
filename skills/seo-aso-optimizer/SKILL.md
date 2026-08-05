---
name: seo-aso-optimizer
description: "Audit and optimize a website for SEO, AEO/GEO (AI search), and ASO — crawl checks, Search Console striking-distance keywords, page fixes, or an app's companion site. Use for 'SEO', 'ASO', 'bei Google ranken', 'Suchmaschinenoptimierung', 'GSC'."
---

# SEO / AEO / ASO Optimizer

Audits and improves an existing website's chances of ranking on Google/Bing and being cited by AI answer engines (ChatGPT, Gemini, Google AI Overviews). The object being optimized is always a **website** — either the site the user already has, or a companion site built for an app that doesn't have one yet (see the branch below). Optimizing an App Store/Play Store listing itself (title, subtitle, keyword field, store screenshots) is out of scope.

Work through the steps below in order. Each ends on a completion criterion — don't move to the next step until it's met.

## Step 1 — Identity and scope

Establish: the site's audience, its 2–3 core offerings/pages, and its brand voice (ask the user, or read existing About/positioning content). If the object is an **app without a marketing website** (or only a thin landing page), read `APP-TO-WEBSITE.md` first — it covers pulling keywords from the store listing and the hero/guides/FAQ page structure that gets built before this skill's steps apply — then continue at Step 2 once that site exists.

**Done when:** you can state the audience, the core offerings, and which path applies, in one sentence each.

## Step 2 — Technical audit (deterministic)

Run the crawl script — it hits every page in the sitemap and checks fixed rules (titles, meta descriptions, H1s, canonical, lang, viewport, structured data validity, alt text, thin content, orphan pages, broken internal links, robots.txt/sitemap/llms.txt presence). No LLM judgment happens inside it, so the same site always yields the same findings:

```
python3 skills/seo-aso-optimizer/scripts/audit_site.py https://example.com --out-dir <workdir>
```

Read the findings-first report (grouped by rule, most-violated first) printed to stdout and saved as `<workdir>/findings.md`. **Do not read `<workdir>/audit-data.json` up front** — it's the full per-page sidecar, meant for drilling into one specific rule or URL once you already know which one matters.

**Done when:** every rule group in `findings.md` has been triaged — fix now, defer with a reason, or false-positive with a reason.

## Step 3 — Search Console reality check

If the GSC MCP tools are connected, call them in this order:

1. `mcp__gsc__list_properties` — get the exact `site_url` (domain properties look like `sc-domain:example.com`).
2. `mcp__gsc__get_search_analytics` with `dimensions="query,page"`, `days=28`, `row_limit=200` — the real query and page data.
3. `mcp__gsc__get_sitemaps` — cross-check against what Step 2 found on disk.
4. `mcp__gsc__check_indexing_issues` for any URL Step 2 flagged as orphaned or broken.

From the query,page rows, find **striking-distance** queries: position roughly 5–15, with real impressions (not 1–2 flukes), and CTR below what that position normally earns. These are the site's highest-ROI targets — a small push moves them onto page 1. If GSC isn't connected yet, tell the user it would sharpen targeting, and continue with Step 4 using AI-suggested keywords only.

**Done when:** every striking-distance query is mapped to an owning page, or explicitly declined with a reason (e.g., off-topic, cannibalizes another page).

## Step 4 — Keyword-to-page map

Merge three inputs into one map — each target keyword owned by exactly one page (existing or "to create"):
- Step 3's striking-distance queries.
- Step 2's thin-content and orphan pages (they may just need a clearer keyword target).
- A fresh AI-generated list of 25–50 candidate keywords for the site's niche, sorted by intent (emergency/transactional/informational/local) and favoring long-tail over short-tail — a specific, low-competition phrase beats a generic, saturated one. See `REFERENCE.md` for the short-tail/long-tail split and page templates for new pages.

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
