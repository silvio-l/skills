# Risk Model (normative)

This is the only normative source for how a band, a gate, or a verdict is produced. `scripts/risk_model.py` implements exactly this document — if you change a threshold or a hard-stop mapping in one, update the other in the same commit. No step anywhere in this skill writes a band, gate value, or verdict string directly; everything routes through this module's functions, called from `check_gates.py`/`render_report.py`.

## The four axes

Every finding carries four independent 0–4 scores (except `evidence_quality`, 0–3):

- **`severity`** — how bad the consequence would be if this conflict is real: 0 = irrelevant … 4 = existential (e.g. forced rename after launch, injunction, damages).
- **`likelihood`** — how likely the conflict is to actually be asserted or matter in practice: 0 = remote … 4 = highly likely.
- **`legal_proximity`** — how close the legal relationship actually is (sign similarity + goods/services overlap + territory match combined): 0 = unrelated … 4 = identity or near-identity.
- **`evidence_quality`** — as reported by whoever wrote the finding: 0 = speculation, 1 = indirect, 2 = reliable, 3 = official primary source. **Never trusted as reported** — see "Evidence-quality capping" below.

Additionally, whenever a finding claims a conflict with an older sign: **`similarity` is three separate 0–4 scores** (`visual`, `phonetic`, `conceptual`) — a single blended similarity number would hide exactly the distinction that decides real cases (visually distinct but phonetically identical marks are a real, common conflict pattern). Paired with a mandatory **`goods_proximity`** (0–4) — sign similarity without goods/services overlap is not a real conflict signal, so the field is structurally required on every conflict finding rather than left to a reviewer's memory.

## Evidence-quality capping

`cap_evidence_quality(finding)` recomputes usable evidence quality from `verification_status`, ignoring the finding's self-reported number:

| `verification_status` | max usable `evidence_quality` |
|---|---|
| `unverified` | 0 |
| `reported_by_search_snippet` | 1 |
| `verified_by_direct_lookup` | 3 |

A claim with no traceable source can still raise a finding's *risk band* (a suspicious-but-unverified hit still deserves investigation) but can never count as evidence that *clears* the name — that asymmetry is why the cap exists.

## Band per finding

`band_for_finding(finding)`:

1. **Score band.** `base = max(severity, legal_proximity)`. Adjust by likelihood: `likelihood <= 1` → shift one band down (floor GREEN), `likelihood == 4` → shift one band up (ceiling BLACK), otherwise no shift.
2. **Hard-stop override.** If the finding carries a `hard_stop_id` (see table below), the band becomes `max(score_band, hard_stop_band)` — a hard stop can only push the band worse, never better than what the scores alone produced.
3. **Evidence floor on BLACK.** If the resulting band is `BLACK` but `cap_evidence_quality(finding) < 2`, the band is pulled down to `RED` — an existential-looking claim with no reliable evidence is escalated hard (never GREEN/YELLOW) but capped just short of the absolute worst verdict until it's actually verified.

Bands, low to high: `GREEN < YELLOW < ORANGE < RED < BLACK`.

## Overall band

`overall_band(findings)` — **worst-of across all findings, never averaged.** Twenty clean findings and one RED finding is an overall RED, full stop; averaging would be exactly the mistake that lets a serious conflict get diluted into a false "mostly fine" impression. No findings at all → `GREEN`, reason `"no adverse findings recorded"`. The report always names the dominating finding by id.

## The fourteen §11 hard stops

Three force `BLACK` outright (evidence floor above still applies); the other eleven force at least `RED` regardless of what the finding's own axis scores alone would produce. A hard stop can only make the band worse than the scores, never better.

| `hard_stop_id` | Forced band |
|---|---|
| `identical_mark_identical_goods` | BLACK |
| `famous_mark_collision` | BLACK |
| `actual_cease_and_desist` | BLACK |
| `near_identical_high_proximity` | RED |
| `company_sign_conflict` | RED |
| `work_title_conflict` | RED |
| `misleading_official_certification_proximity` | RED |
| `protected_professional_title` | RED |
| `personality_or_name_right` | RED |
| `protected_geographic_indication` | RED |
| `problematic_official_emblem` | RED |
| `ongoing_litigation` | RED |
| `unclear_rights_chain` | RED |
| `high_investment_under_uncertainty` | RED |

The last three (`ongoing_litigation`, `unclear_rights_chain`, `high_investment_under_uncertainty`) — together with `actual_cease_and_desist` above — are typically discovered only through the Phase 1 prior-events question, not through research; no register lookup can surface them.

## Verdict mapping

| Band | Verdict (`deep`/`launch`/`handoff` modes) |
|---|---|
| GREEN | `PRELIMINARILY CLEAR` |
| YELLOW | `PROCEED WITH CONDITIONS` |
| ORANGE | `MODIFY BEFORE USE` |
| RED | `LAWYER CLEARANCE REQUIRED` |
| BLACK | `DO NOT USE` |

`PRELIMINARILY CLEAR` is structurally unreachable unless **every** planned search-log row is `completed` **and** at least one row is a `verified_by_direct_lookup`-quality completed row against a `registered_mark` source (`_has_primary_register_lookup`). A run with zero findings but zero completed primary-register lookups is downgraded to `PROCEED WITH CONDITIONS` — a completely unresearched name must never present as clean just because nothing was found, since nothing was actually looked for either.

**Quick Scan mode ignores gates entirely** and uses a separate three-value scale instead of the five verdicts above:

| Band | Quick Scan verdict |
|---|---|
| BLACK / RED | `IMMEDIATE STOP` |
| ORANGE | `RENAME LIKELY` |
| GREEN / YELLOW | `GO TO DEEP CHECK` |

Quick Scan never produces a green light — its only job is deciding whether a full Deep Clearance is warranted, likely to end in a rename, or should stop immediately.

## Gates (13, all derived from artifacts on disk)

`derive_gates(profile, variants, searchlog_rows, findings, redteam)` computes every gate fresh from what's actually on disk — never from a stored boolean anywhere. If *any* gate is false, `verdict_for()` (in `deep`/`launch`/`handoff` modes) returns `RESULT INCOMPLETE – NO RELEASE RECOMMENDATION POSSIBLE` **instead of only the verdict line** — every other report section (findings, territorial coverage, red team, evidence, limitations, and a "what's missing and how to complete it" block) still renders in full. This is deliberate: a report that goes fully blank on an open gate creates pressure to fake completion just to get a usable artifact out of the run.

`absolute_grounds_checked` and `special_sector_rules_checked` are deliberately keyed off the search log, not `findings` — a clean check produces zero findings by design (ORCHESTRATION.md rule 2: "a clean cluster still writes both files"), so a gate that demanded a finding to close would be structurally unreachable for the ordinary, adverse-free case. `company_names_checked` is likewise deliberately narrowed to territories with a real company register (`_TERRITORIES_WITH_COMPANY_REGISTER` in `risk_model.py`) rather than every `target_territories` entry — otherwise a `DE`+`EU` run, the default this skill suggests, could never close it.

| Gate | True when |
|---|---|
| `context_complete` | `profile.json` has `name`, `name_type`, `goods_and_services`, `target_territories`, `planned_use`, `prior_events` all set |
| `territories_defined` | `target_territories` is non-empty |
| `goods_services_defined` | `goods_and_services` is non-empty |
| `name_variants_generated` | `variants.json` has at least one variant |
| `exact_search_completed` | every planned `search_type: exact` row is `status: completed` |
| `similarity_search_completed` | every planned `search_type: similarity` row is `status: completed` |
| `unregistered_rights_checked` | every planned `search_type: unregistered` row is `status: completed` |
| `company_names_checked` | every target territory that SOURCES.md actually lists a company register for (`DE`/`AT`/`CH` — there is no EU-wide register) has at least one `completed` row with `source_category: company_register` |
| `absolute_grounds_checked` | every language in `profile.languages` (default `["de"]`) has at least one `completed` search-log row with `cluster_id: linguistic-<lang>` |
| `special_sector_rules_checked` | every module in `sector_modules_applicable` is either in `sector_modules_not_applicable` or has at least one `completed` search-log row with `cluster_id: sector-<module>` |
| `red_team_completed` | `redteam.json` has at least one attack, every attack has a `rebuttal`, every `missed_vectors` entry has a `resolution` |
| `evidence_review_completed` | every finding has at least one evidence entry with a `url` or `register_id` |
| `limitations_disclosed` | always true — the renderer emits this section unconditionally, so this gate cannot be forgotten by construction |

**The deadlock escape hatch:** a search-log row with `performed_by: user`, `status: completed` (from the Checkpoint C manual-lookup handoff) satisfies its gate exactly like an agent-completed row. Since no trademark register offers reliable automated access (SOURCES.md), this is not an edge case — it's the normal path to a real, gate-passing `deep` run.
