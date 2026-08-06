# Sources — Register Catalog

One entry per `source_id` referenced from `searchlog/*.json` and `findings/*.json`. `access_mode` tells a research step whether it may fetch/search this source itself or must hand it to the user at Checkpoint C.

**`access_mode` values:**
- `automated_allowed` — fetch or search this yourself, normal reasoning-tier care (see SKILL.md "Capability tier").
- `automated_allowed_needs_setup` — a real API exists but requires credentials/registration this skill does not ship; treat as `manual_only` until a future version wires it up.
- `manual_only` — no reliable programmatic access, or the source's terms forbid automated querying. Plan the row as `pending_user_verification` from the start, with full `manual_instructions`; never attempt to scrape or bypass access control.

## Registered marks (`source_category: registered_mark`)

| `source_id` | Territory | Coverage | `access_mode` | Notes |
|---|---|---|---|---|
| `dpma-register` | DE | German national trademark register | `manual_only` | DPMAregister has no public API and its search UI is not designed for automated querying. |
| `tmview` | EU + 70+ national/regional offices | Aggregated view across participating offices | `manual_only` | No public API; ToS do not authorize automated querying. |
| `euipo-esearch` | EU | EUTM register | `automated_allowed_needs_setup` | Real REST API exists (eSearch Plus) but requires an OAuth2 client registered at `dev.euipo.europa.eu` — out of scope for this skill's v1, revisit once a client is registered. |
| `wipo-gbd` (Global Brand Database) | International (Madrid System + many national offices) | Broadest single search surface for international marks | `manual_only` | WIPO's terms explicitly prohibit automated/bulk querying of GBD. |
| `uspto-tess` | US | US federal trademark register | `manual_only` | No public API for TESS; automated querying is against its usage terms. |

## Company / business registers (`source_category: company_register`)

This table only covers DE/AT/CH — there is no EU-wide (or, in v1, US) company-name register. The `company_names_checked` gate (RISK-MODEL.md) is deliberately scoped to only the target territories listed below (`_TERRITORIES_WITH_COMPANY_REGISTER` in `risk_model.py`), so a target territory outside this table is simply out of scope for this gate rather than blocking it.

| `source_id` | Territory | Coverage | `access_mode` | Notes |
|---|---|---|---|---|
| `handelsregister` | DE | German commercial register (company name conflicts) | `manual_only` | Handelsregister.de has no public search API. |
| `unternehmensregister` | DE | Federal company-data register, overlaps with Handelsregister | `manual_only` | Same access constraints. |
| `firmenbuch` | AT | Austrian commercial register | `manual_only` | No public API. |
| `zefix` | CH | Swiss central business names index | `automated_allowed` | Zefix offers a public REST API (`www.zefix.ch/ZefixPublicREST`) — use it directly when CH is a target territory. |

## Unregistered rights / other prior use (`source_category: unregistered`)

| `source_id` | Coverage | `access_mode` | Notes |
|---|---|---|---|
| `web-search-general` | General prior-use signals (business use, press mentions, marketplace listings) | `automated_allowed` | Use your environment's web-search capability; judge each hit for whether it's genuinely prior commercial use vs. unrelated noise. |
| `github-search` | Open-source project/package name collisions | `automated_allowed` | Public search UI + `check_digital_availability.py`'s org/user existence check. |
| `npm-registry` | JS package name collisions | `automated_allowed` | `check_digital_availability.py` queries `registry.npmjs.org` directly. |
| `pypi-registry` | Python package name collisions | `automated_allowed` | `check_digital_availability.py` queries `pypi.org/pypi/<name>/json` directly. |
| `app-store-search` | iOS App Store name collisions | `manual_only` | No reliable public existence-check API; record as `manual_verification_required`. |
| `play-store-search` | Android Play Store name collisions | `manual_only` | Same. |
| `marketplace-search` (Amazon, Etsy, …) | Product/seller name collisions, where relevant to `goods_and_services` | `manual_only` | Search UIs are bot-blocked; hand to Checkpoint C. |

## Digital availability (`source_category: digital`)

| `source_id` | Coverage | `access_mode` | Notes |
|---|---|---|---|
| `rdap` | Domain registration status, per RFC 7482/9224 | `automated_allowed` | `check_digital_availability.py`, via IANA's live RDAP bootstrap registry. Never use `socket.gethostbyname`/DNS resolution for this — it produces both false "taken" (parked, unregistered domains resolve) and false "available" (registered domains that don't resolve) signals. Many common TLDs (`.de`, `.io`, `.eu` confirmed as of this writing) have no RDAP bootstrap entry at all — the script reports `unknown` for those, never a guessed `available`. |
| `social-handle-check` | Handle availability on major social platforms | `manual_only` | No reliable public existence API across platforms without authenticated access; record as `manual_verification_required`. |

## Linguistic / cultural (`source_category: linguistic`)

| `source_id` | Coverage | `access_mode` | Notes |
|---|---|---|---|
| `model-knowledge` | Descriptiveness/genericness/offensive-meaning judgment in a given language | `automated_allowed` | Legitimate for Phase 4 absolute-grounds and Phase 3 semantic-variant work, but `cap_evidence_quality()` always caps a `model-knowledge`-sourced finding's evidence quality low (`verification_status: unverified` unless independently cross-checked) — present it as a linguistic judgment, not a verified fact. |
| `web-search-linguistic` | Cross-checking a meaning/connotation claim against real usage | `automated_allowed` | Use web search to corroborate a `model-knowledge` hunch before raising its `verification_status`. |

## Sector-specific (`source_category: sector`)

No fixed catalog — sources vary by which §8 module (METHODIK.md Phase 8) triggered. Typical starting points: national professional-title registers (`manual_only`, e.g. a chamber of commerce/medical board register), geographic-indication registers (EU's eAmbrosia database — check current access mode before use), official-emblem lists (Paris Convention Art. 6ter database via WIPO — `manual_only`, same ToS constraints as `wipo-gbd`). Record the concrete `source_id` used per module directly in that module's `findings/sector-<name>.json` entries; add it to this table once a module has been run more than once.
