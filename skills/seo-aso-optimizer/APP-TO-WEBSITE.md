# App-to-website bridge

For an app with no marketing website (or only a bare landing page). The problem: someone searching Google for what the app does will never type the app's name — they type their problem. An app store listing alone doesn't get crawled and ranked the way a website does. This branch builds the missing website, then hands off to `SKILL.md` Step 2 to audit and refine it like any other site.

Scope boundary: this produces a **marketing website** that ranks and converts. It does not touch the app's actual App Store/Play Store listing fields (title, subtitle, keyword field, store screenshots) — that's native store ASO and out of this skill.

## 1. Pull the source material

From the app's store listing, gather into one file: app name, current description, category, and existing screenshots/icon. This is the seed for keyword research — the listing already names the problem the app solves, even if it doesn't use the words a searcher would.

## 2. Keyword research: primary + long-tail

Ask for both:
- **Primary keywords** — short-tail terms naming the app's category (low ranking odds, but anchor the homepage headline).
- **Long-tail keywords** — specific phrases matching one concrete use case or user problem the app solves (see `REFERENCE.md`'s short-tail/long-tail section). These are what most of the site's pages will target — favor them; they convert better and rank faster.

Optimize the selection for keywords that plausibly drive a download or conversion, not just traffic volume.

## 3. Build the site

Follow `REFERENCE.md`'s hero → how it works → guides → FAQ → CTA template:
- One **guide** page per long-tail keyword: the user's problem, how to solve it, then how the app does that step for them.
- One **FAQ** entry per specific query, each with a "learn more" link into the matching guide.
- Structured data on the homepage: `SoftwareApplication` or `MobileApplication` (see `REFERENCE.md`'s schema table).

## 4. Hand off

Once the site exists and is deployed, continue at `SKILL.md` Step 2 — the technical audit script and the rest of the workflow apply to this new site exactly like an existing one. Submit the sitemap via `mcp__gsc__submit_sitemap` as part of Step 7.
