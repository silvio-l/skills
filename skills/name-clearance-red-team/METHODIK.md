# Methodology — Phases 1–8

Normative detail behind SKILL.md's flow. Each phase below maps to one or more of the flow's numbered steps. RISK-MODEL.md is the only normative source for scoring/gates/verdicts — this document is about *what to check*, not *how to score it*.

## Phase 1 — Intake (Checkpoint A)

Populate `profile.json` per `schema/profile.schema.json`. Pull from the repo/context first; only ask for what's missing.

**Never inferred, always asked explicitly, even if a plausible default exists:**
- `goods_and_services` — free text describing what the name will actually be used for. This decides whether a conflicting mark's goods/services class collides at all; guessing it defeats the entire proximity analysis downstream.
- `target_territories` — e.g. `["DE", "EU"]`. Offer `DE+EU` as a starting suggestion but require explicit confirmation, don't default silently.

**Recommended fields** (`target_customers`, `industry`, `business_model`, `languages`, `launch_date`, `legal_entity`, `future_markets`, `known_competitors`, `candidate_domains`, `risk_tolerance`, `search_depth`) may be defaulted from context, but every default actually used goes into `profile.json`'s `assumptions` array with a reason — never silently.

**The mandatory prior-events question** (`prior_events` object): has this name already received a cease-and-desist, is there an ongoing dispute, is the rights chain to this name unclear (e.g. bought from someone, inherited from a prior project), has significant investment already gone into it? Ask this explicitly, as plain text with lettered options if useful — no search can discover any of these four facts; they map directly to four of the fourteen RISK-MODEL.md hard stops (`actual_cease_and_desist`, `ongoing_litigation`, `unclear_rights_chain`, `high_investment_under_uncertainty`).

Also identify which §8 special-sector modules (below) plausibly apply, from `industry`/`goods_and_services`/context — record the list in `profile.json`'s `sector_modules_applicable`. Every module listed there must later resolve to either a `sector-<name>` cluster's findings or an entry in `sector_modules_not_applicable` with a reason — the `special_sector_rules_checked` gate checks exactly this pairing.

## Phase 2 — Decomposition

Break the name into its components before generating variants: is it a compound, an acronym, a coined/invented word, a real-language word, a person's name, a geographic term? This classification feeds both variant generation (Phase 3) and absolute-grounds checking (Phase 4) — a coined word has essentially no descriptiveness risk; a real-language descriptive term does.

## Phase 3 — Name variants

Run `scripts/generate_name_variants.py` for the deterministic classes (orthographic: spacing/hyphenation/umlaut-ASCII/plural/typo-transposition; phonetic: per-language substitution rules; transliteration: Latin↔Cyrillic confusables relevant to digital-squatting risk). The script deliberately does **not** generate semantic variants (translations, synonyms, acronym expansions, reversed word order) — hardcoding a translation table would substitute model knowledge for actual research. Instead it emits an empty `semantic_hint` slot per requested language; fill each one in from your own language knowledge or a quick lookup, and append the results to `variants.json` under the same shape. Every variant used later in the search plan must trace back to either a script-generated entry or a filled `semantic_hint` — never invent a variant ad hoc mid-search without recording it here.

## Phase 4 — Absolute grounds

Per target language: is the name (or a dominant part of it) purely descriptive of the goods/services, generic, deceptive, or otherwise likely to face an absolute refusal ground at the relevant trademark office? This is assessed directly in the main thread, no subagent — it is a linguistic/conceptual judgment, not a register lookup. Record the outcome as a `completed` row in `searchlog/linguistic-<lang>.json` (`cluster_id: linguistic-<lang>`, `search_type`/`source_category: linguistic`) regardless of outcome — this row alone satisfies the `absolute_grounds_checked` gate (RISK-MODEL.md), which reads the search log rather than `findings`, since a clean assessment has nothing to put in a finding. If the assessment actually turns up a concern, additionally write a `findings/linguistic-<lang>.json` entry, `category: absolute_ground`, `language` set. A finding here can legitimately use `source_id: model-knowledge` for a linguistic judgment, but per `cap_evidence_quality()` such a finding's evidence quality is capped low — the registrability assessment in the report says so plainly (REPORTING.md) rather than presenting a linguistic hunch as verified fact. The fan-out's `linguistic-<lang>` cluster (Phase 5, ORCHESTRATION.md) revisits the same language with actual web corroboration for semantic variants and appends to these same two files — it is a deeper follow-up, not a duplicate requirement.

## Phase 5 — Register + proximity analysis (the fan-out)

For every variant × territory × source in the search plan: run the query, and for every hit judge sign similarity as **three separate scores** (`visual`, `phonetic`, `conceptual`, each 0–4) — never collapse to one blended similarity number, that discards exactly the distinction that matters (two marks can be visually distinct but phonetically identical, or vice versa). Pair every similarity judgment with a `goods_proximity` score (0–4) — sign similarity in isolation, without asking whether the goods/services actually compete, is not a real conflict signal. See ORCHESTRATION.md for the cluster breakdown and RISK-MODEL.md for how these numbers become a band.

## Phase 6 — Unregistered rights

Beyond registered marks: company/business names (Handelsregister-style registers), unregistered trademark use (business use without formal registration, which can still create prior rights in many jurisdictions), work titles (§5 MarkenG-style protection for publications/software/media titles), and domain-name-adjacent prior use. See SOURCES.md's `unregistered` cluster for the concrete source list.

## Phase 7 — Digital availability (deterministic)

`scripts/check_digital_availability.py` — RDAP-based domain checks (never DNS resolution, which produces false signals both ways) plus GitHub/npm/PyPI existence checks via their public JSON APIs. These go straight to `digital-availability.json`, not `searchlog/`, per ORCHESTRATION.md. App-store names and social-media handles have no reliable public existence API and are deliberately out of scope for the script — record them instead as `manual_verification_required` rows in `searchlog/digital.json` (`cluster_id: digital`, `search_type: digital`) for social-media handles (`social-handle-check`, SOURCES.md), or as part of the `unregistered` cluster (`cluster_id: unregistered`) for app-store/marketplace listings (`app-store-search`, `play-store-search`, `marketplace-search`, SOURCES.md) — never scrape a page that will bot-block the request. `unknown` from this script (e.g. for a TLD not present in IANA's RDAP bootstrap, such as `.de`/`.io`/`.eu` as of this writing) must never be treated as "available" downstream.

## Phase 8 — Special-sector modules (conditional)

Triggered per `profile.sector_modules_applicable`, checked in Phase 1:

- **Regulated industry** (finance, healthcare, legal, pharma, …) — sector-specific naming restrictions or required disclosures (e.g. "Bank", "Versicherung", "Arzt" are restricted terms in German-speaking jurisdictions).
- **Geographic indication** — does the name reference a protected designation of origin or geographic indication for the relevant goods (wine, food, spirits, regional specialties)?
- **Official/professional title** — does the name imply an official title, certification, or professional designation it hasn't earned (e.g. "TÜV", "Notar", "zertifiziert")?
- **Personality/name rights** — does the name reference a real, identifiable person without their consent?
- **Official emblems** — does the name or an obvious visual pairing reference a state emblem, flag, or international-organization symbol (Red Cross, Olympic rings, UN, national coats of arms) protected against unauthorized commercial use?

Each triggered module gets its own `sector-<name>` cluster (ORCHESTRATION.md) producing `findings/sector-<name>.json` (`category: sector_specific`) — even a clean check writes an (empty) findings array plus a completed search-log row (`cluster_id: sector-<name>`), so "checked, nothing found" stays distinguishable from "never checked" on disk, same principle as every other cluster. The `special_sector_rules_checked` gate reads that search-log row, not the findings array — see RISK-MODEL.md.
