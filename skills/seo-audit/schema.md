# Phase 4 — Schema / JSON-LD Audit

Local, offline audit of all `<script type="application/ld+json">` blocks
in the built HTML. Produces findings with `dimension='schema'`.

Script: `scripts/schema_scan.py`.

## What gets checked

### Presence

Every HTML file that contains no JSON-LD block at all gets a
`schema-missing` finding (severity=high, track=technical). The suggested
fix is a minimal `WebSite` or `Organization` skeleton.

### Tolerant extraction

The scanner extracts blocks with a lenient regex so that a broken block
does not cause an exception. A block whose content is not valid JSON is
flagged as `schema-broken` (severity=high, track=technical) and skipped
for the downstream field/type checks.

### Required-field completeness — `REQUIRED_FIELDS_V1`

Seven core Schema.org types are audited for mandatory fields. Missing
fields become `schema-incomplete` findings (severity=high,
track=technical):

| Type | Required fields |
|---|---|
| `Organization` | `name`, `url` |
| `Person` | `name` |
| `Article` | `headline`, `author`, `datePublished` |
| `Product` | `name`, `description` |
| `WebSite` | `name`, `url` |
| `WebPage` | `name` |
| `FAQPage` | `mainEntity` |

Source: [Google Rich Results requirements](https://developers.google.com/search/docs/appearance/structured-data).
Table version: `REQUIRED_FIELDS_V1` (embedded in `schema_scan.py`).
Update the constant and bump `GENERATOR_VERSION` in `audit.py` when
Google changes requirements.

### Deprecated types — `DEPRECATED_TYPES_V1`

The following Schema.org types are flagged as `schema-deprecated`
(severity=med, track=technical) and should not appear in new markup:

`WPFooter`, `WPHeader`, `WPSideBar`, `WPAdBlock`, `DataFeedItem`,
`UserComments`.

Source: schema.org deprecation notices. Table version: `DEPRECATED_TYPES_V1`.

### sameAs consistency (GEO signal)

Social-profile URLs declared in `sameAs` (Twitter/X, Facebook, LinkedIn,
Instagram, YouTube, Pinterest, TikTok, GitHub, Xing, Mastodon) that have
no matching `<a href="…">` anywhere in the page HTML are flagged as
`schema-sameas` (severity=med, track=technical). Non-social sameAs
entries (Wikidata, DBpedia, …) are ignored.

## Suppression

Pages whose first HTML comment (within the first 2 KB) contains
`contrastiveVocabulary: true` are excluded entirely — the same
convention as `brand_scan.py`. This is useful for comparison or
contrastive content pages that intentionally lack structured data.

## JSON-LD graph support

The scanner handles three JSON-LD shapes transparently:

- Plain `{"@type": "…"}` object.
- `{"@graph": […]}` wrapper — all nodes in the graph are audited.
- Top-level JSON array of objects — each element is audited.

## Finding shape

```json
{
  "file_path": "<absolute path>",
  "line_number": 42,
  "match": "Organization: Pflichtfeld „url" fehlt",
  "suggested_replacement": "Feld „url" in den Organization-Block ergänzen",
  "rationale": "Organization ohne „url" wird von Google Rich Results …",
  "category": "schema-incomplete",
  "severity": "high",
  "user_impact": 3,
  "fix_effort": 2,
  "dimension": "schema",
  "track": "technical"
}
```

`line_number` points to the opening `<script>` tag of the affected
JSON-LD block.

## Fix snippets

The report phase generates copy-paste fix snippets for two categories:

- `schema-missing` — a minimal `WebSite` JSON-LD skeleton with
  `SITE_NAME` / `DOMAIN` placeholders.
- `schema-incomplete` — a partial block for the specific type + field,
  e.g. `{"@type": "Organization", "url": "PLACEHOLDER"}`.

Snippets are deduplicated by `snippet_key` so the same skeleton is not
repeated for multiple files with the same issue.

## Determinism contract

Two calls to `schema_scan.scan_directory(dist_root)` with the same
`dist_root` contents must return byte-identical JSON. The implementation
achieves this by sorting the final list by `(file_path, line_number,
match.lower())` — the same tiebreaker as `brand_scan` and `geo_scan`.

## CLI surface

```bash
# Standalone: print findings JSON to stdout
python3 skills/seo-audit/scripts/schema_scan.py <dist-dir>
```

`audit.py` calls `schema_scan.scan_directory(dist)` directly; the
standalone CLI exists for debugging.

## What this phase does *not* do

- Validate against the live Schema.org API (`validator.schema.org`) —
  that is the `schema` external-probe adapter in `probes/schema_adapter.py`.
- Score findings — that is synthesis.
- Apply fixes — the audit only reports.
- Make any network call.
