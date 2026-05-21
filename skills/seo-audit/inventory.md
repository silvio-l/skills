# Phase 1 — Inventory

The inventory phase establishes context for the rest of the audit. It
is pure filesystem inspection: no source parsing, no shell-outs, no
network. The output drives the report header and tells the brand scan
where built HTML lives.

## What gets detected

| Field | How |
|---|---|
| `framework` | `astro.config.{mjs,ts,js,cjs}` → `astro`; `next.config.*` → `next`; top-level `index.html` with no framework config → `static`; otherwise `unknown`. |
| `domain_doc` | First existing of `CONTEXT.md` → `CLAUDE.md` → `README.md`. Empty string if none. |
| `seo_assets` | `robots.txt`, `sitemap.xml`, `sitemap-index.xml`, `llms.txt`, `llms-full.txt`, `ai.txt` — checked at the repo root and in `public/`, `static/`, `dist/`. First hit per asset wins. |
| `app_store_listings` | A `store/` subdirectory (up to depth 3), `package.appxmanifest` (Microsoft Store), `Info.plist` (Apple). |
| `pages` | All `.html`/`.htm` files under `<root>/dist`. Empty if `dist/` is absent — the brand scan then becomes a no-op. |

## Detection order matters

The framework heuristic short-circuits in order: Astro before Next
before static. If both `astro.config.mjs` and `index.html` exist (e.g.
mid-migration), Astro wins because that is the active build path.

## When the inventory is degraded

If `framework == "unknown"` and `pages == []`, the audit still runs —
the brand scan simply finds nothing, and the report's *Empfehlungen*
section will lead with "build the site first, then re-run". Do **not**
abort; the inventory section of the report still has value (it
documents what is missing).

## CLI surface

```bash
python3 skills/seo-audit/scripts/inventory.py <root>
```

Prints JSON. Used standalone for debugging; in normal operation
`audit.py` calls `inventory.inventory(root)` directly.
