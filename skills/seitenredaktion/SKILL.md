---
name: seitenredaktion
description: "Edit the German copy of an existing landing or product page in the repo against a bundled taste guide, with research of the three biggest competitors. Use for 'Seitenredaktion', 'Landingpage-Texte überarbeiten', 'Copy redigieren'."
argument-hint: "[route or page name] [optional focus]"
disable-model-invocation: true
---

# Seitenredaktion

Edit this page in the current project: $ARGUMENTS

Without a page argument, take the public start page, provided it is unambiguous; otherwise stop and ask which page is meant. A focus after the route (e.g. `/ Fokus auf Hero und Download`) narrows the work but never skips the checks.

## 1. Load the taste

Read `${CLAUDE_SKILL_DIR}/TASTE.md` in full before touching any text. It is written in German on purpose — it is the editorial standard the output copy must meet, not documentation to translate.

If the project has its own `TASTE.md` (repo root or its docs folder), it takes precedence over the bundled one wherever the two disagree; the bundled file fills the gaps.

## 2. Run the brief

Carry out the section **„Umsetzungsauftrag für eine bestehende Seite“** of `TASTE.md` end to end, with the page from `$ARGUMENTS` as `[Route oder Seitenname]`:

1. **Product and status quo** — read the rendered page, its components and locale files. Derive audience, visiting occasion, product terms and main action from the project itself; verify features, limits and CTA targets against the implementation, never against marketing claims.
2. **Competitor research** — identify the three largest direct competitors for the same use case and market, justify the choice with comparable, current size indicators and sources (mark it as an estimate where hard market data is missing). Fetch each official home page (and the comparable product page if needed): prefer the German version, try `curl` first, and use a rendered headless browser when the page is a JS shell, cookie-walled or incomplete. Search snippets never count. Record URL, language, retrieval date and remaining gaps.
3. **Editing** — reconstruct each competitor's scroll logic (prior knowledge, promise, explanation, proof, objection, action), then write your own copy. Competitors are inspiration only: `TASTE.md`, the project's brand voice and verified product facts win. Keep strong passages, dissolve recurring two-beat slogans, cut or move blocks that add neither information nor orientation.

## 3. Implement in place

Change the copy where it already lives — existing components and locale/translation files, keeping keys, `testID`s/`data-testid`s and routing intact. Do not introduce a parallel content system, new components or design changes unless the copy cannot work without them; say so explicitly if you do. All page copy stays German.

## 4. Verify and report

Finish only with a checked result: desktop and mobile view, links, anchors, locale keys, interactions and the project's relevant checks (lint, type check, build). Then report compactly:

- the three competitor sources (URL, language, date, gaps),
- the defining editorial decisions as sentence pairs (before → after → reason),
- the check results,
- open proof points — product claims that still need a source or a decision, and any check you could not run, each named concretely.

Offer to record taste-revealing decisions per **„Mit echten Entscheidungen weiterentwickeln“** in the project's own `TASTE.md`; never write them into the bundled guide.

## Examples

```
/seitenredaktion / Fokus auf Hero, Bildschirmfreigabe und Download
/seitenredaktion /funktionen/jahresplan Prüfe, ob das Beispiel bis zur nächsten Entscheidung trägt
```
