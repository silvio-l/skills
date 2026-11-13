# Redesigning an existing page

A redesign keeps what works and what other code depends on, and changes the rest deliberately.

## Before touching anything

1. **Inventory.** Route(s), components, locale files and keys, `data-testid`s, anchors linked from elsewhere (app, emails, ads, docs), analytics events, forms and their endpoints, SEO meta, structured data.
2. **Baseline.** Run both checks on the current page and keep the reports as `.website-creator/baseline-lint.json` and `.website-creator/baseline-render/` (`--out`). Take full-page screenshots at 375 and 1440.
3. **Read the copy against the product.** Every claim checked against the implementation: features that do not exist (anymore), wrong numbers, outdated screenshots. List them; they go into the report as fixed or as open proof points.
4. **What to keep.** Ask yourself (and, in the copy decision, the user) which parts are deliberate: brand phrases, legal text, wording other channels quote.

## Doing it

- Edit in place. Keep routes, keys, testIDs, anchors, analytics hooks and form contracts; rename only with a migration (redirect, alias key) and list it in the report.
- The copy decision shows sentence pairs: before → after → reason, per section.
- Existing DESIGN.md: the direction proposals start from it; a direction that replaces it says so explicitly. Without DESIGN.md, extract the current tokens first so the user sees what changes.
- Remove dead CSS and unused assets that the redesign makes obsolete; nothing else.

## After

- Compare against the baseline: lint and render findings must not increase; list what disappeared.
- Check incoming links and anchors still resolve; check the page in every locale.
- The report lists everything that changed for other code (none, ideally).
