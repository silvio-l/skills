# Reference

Consulted on demand from `SKILL.md` Step 4 and Step 6 — not needed for orientation.

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
- **Ranks OK, converts badly** → rewrite title/meta description to match search intent more precisely.
- **Doesn't rank high enough** → the owning page needs more topical depth, better internal links pointing to it, or doesn't exist yet.

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
