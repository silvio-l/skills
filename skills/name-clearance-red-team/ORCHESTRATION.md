# Orchestration — Fan-out Protocol

Goal of this document: how the research plan actually gets executed without holding every finding in the main context, and without ever depending on a specific agent CLI's subagent mechanism. **The artifact contract is the real mechanism, not subagent dispatch** — `searchlog/<cluster-id>.json` + `findings/<cluster-id>.json` per SOURCES.md's schemas are what `risk_model.py` reads. It never asks who wrote them or how. Dispatching a parallel sub-task per cluster is an optimization for context size and wall-clock time; a sequential in-context pass produces an equally valid run.

## Working directory

Created in the **user's own working directory** (not this skills repo) at `.name-clearance-tmp/<name-slug>-<YYYY-MM-DD>/`:

```
.name-clearance-tmp/<name-slug>-<YYYY-MM-DD>/
├── profile.json               # Checkpoint A intake (Phase 1)
├── variants.json              # generate_name_variants.py + filled semantic_hint (Phase 2+3)
├── digital-availability.json  # check_digital_availability.py output (Phase 7)
├── searchlog/
│   ├── _plan.json             # the full planned array, every row not_attempted initially,
│   │                         #   each row already carrying its cluster_id (see below)
│   ├── de-eu-registers.json   # one file per cluster after execution — never shared between clusters
│   ├── intl-wipo.json
│   └── ...
├── findings/
│   ├── de-eu-registers.json   # array, empty if the cluster ran clean — never omit the file
│   ├── intl-wipo.json
│   └── ...
├── redteam.json               # Phase 9 (REDTEAM.md)
├── synthesis.md                # narrative only — never a verdict
├── report.md
├── report.html                 # only with --html
└── lawyer-handoff.md           # only --mode handoff
```

One subdirectory per run, not a flat directory — repeated runs after a rename must not clobber prior evidence, and Launch Decision needs to compare candidates side by side.

## Clusters

Clusters are keyed **by territory × source group**, never by source alone — collapsing territories into one cluster silently breaks the "every target territory checked and reported separately" rule everywhere downstream.

| Cluster id | Scope | Writes |
|---|---|---|
| `de-eu-registers` | DPMA + EUIPO/TMview for DE+EU target territories | `searchlog/de-eu-registers.json`, `findings/de-eu-registers.json` |
| `intl-wipo` | WIPO Global Brand Database + any other target territories' national offices | same pattern |
| `unregistered` | Company/business registers, work titles, package registries (npm/PyPI/GitHub), app stores, marketplaces | same pattern |
| `linguistic-<lang>` | **One cluster per target language, never combined** — absolute grounds + semantic-variant corroboration for that language | same pattern |
| `sector-<name>` | Conditional, one per triggered §8 module (METHODIK.md Phase 8) | same pattern |
| `digital` | Manual-only digital-category lookups the script can't do (`social-handle-check`, SOURCES.md) — `search_type: digital` rows, `cluster_id: digital` | `searchlog/digital.json`, `findings/digital.json` |

`digital-availability.json` is produced directly by `check_digital_availability.py` (Phase 7) — RDAP domain checks plus GitHub/npm/PyPI existence checks — not by a research cluster; it needs no research judgment, just the script's deterministic output, and never enters the `searchlog/` merge. The `digital` cluster above is a separate, smaller thing: the handful of digital-category lookups the script can't do at all (social-media handles) and that therefore need a plan row like any other manually-checked source.

## Every row carries its own `cluster_id`, from the plan onward

`render_report.py` merges `_plan.json` and every `searchlog/<cluster-id>.json` file into one list, keyed on `(query, source_id, territory, cluster_id)`. Two rows that share query/source_id/territory but belong to different clusters — e.g. the `linguistic-de` and `linguistic-en` rows for the same name — are only kept apart because of `cluster_id`; without it one silently overwrites the other and its gate reports the cluster as never checked. This applies at **every** stage, not just cluster execution:

- **When the plan is built (SKILL.md step 5, "Build the search plan"):** each row in `_plan.json` is written with its `cluster_id` already set (`linguistic-<lang>`, `sector-<module>`, `de-eu-registers`, ...) — never added later as an afterthought.
- **Path A and path B alike:** every row a cluster writes to `searchlog/<cluster-id>.json` carries the same `cluster_id` it had in the plan. `absolute_grounds_checked` and `special_sector_rules_checked` (RISK-MODEL.md) key off this field, not off findings.

## Two ways to produce the same files

**A — the environment can dispatch parallel sub-tasks** that read/write files independently (e.g. an `Agent`/subagent mechanism): dispatch one per cluster, using the prompt skeleton below, and collect only a one-line summary back per cluster — never pull the full `findings` array into the orchestrator's own context. Batch dispatch (several clusters at once) is fine; nothing here requires strict sequencing between clusters.

**B — it cannot:** work the clusters sequentially in the orchestrator's own context. Three rules apply specifically to this path:
1. **Write before moving on.** Both files for a cluster are on disk before the next cluster starts — progress must survive a context compaction mid-run.
2. **A clean cluster still writes both files.** `findings/<cluster-id>.json` as an empty array, plus the complete search log for that cluster. "The cluster ran and found nothing" and "the cluster never ran" must stay distinguishable on disk — the gates read the search log, not file presence.
3. **Don't stop at the first blockage.** Record `block_reason` + `manual_instructions` and keep going; collect every blocked/open row across all clusters into one consolidated Checkpoint C handoff after the *last* cluster.

## Prompt skeleton (path A — dispatched research)

> You are the research cluster for `<cluster-id>` in a name-clearance red-team review of "`<name>`" (territories: `<territory-list>`, goods/services: `<goods_and_services>`). Your planned rows are `<inline the cluster's rows from _plan.json>`. For each row: use this environment's web-fetch/web-search capability at its default (never a downgraded) reasoning tier to actually execute the lookup. `status: completed` only if you saw real result content — a hit list, or an explicit "no results" rendered by the source itself. Anything else (empty app shell, cookie wall, CAPTCHA, bot block, HTTP error, rate limit, source's own terms forbidding automated access — see SOURCES.md's `access_mode`) is `status: blocked` with a matching `block_reason` and full `manual_instructions` (url, search_string, filters) — never record a blocked lookup as "no hits". Never solve a CAPTCHA, never bypass an access control, never invent a register number/owner/legal status. Set `cluster_id: "<cluster-id>"` on every row you write — the gates read this field, not the filename. For every hit that looks like a genuine conflict, score `visual`/`phonetic`/`conceptual` similarity separately (0–4 each, never one blended number) plus `goods_proximity` (0–4), and write a full finding per `finding.schema.json` [inline the schema], including a `strongest_counter_argument` — never leave that empty even for a weak finding. Write your complete search-log rows to `searchlog/<cluster-id>.json` and your findings array (empty if none) to `findings/<cluster-id>.json`, exactly per the schemas. Reply with ONLY a one-line summary (e.g. "6 rows: 4 completed/2 blocked; 1 finding, band YELLOW").

## Anti-fabrication clause (verbatim — quote this in every research prompt/self-instruction)

> `status: completed` only when actual result content was seen (a hit list, or an explicit "no results" rendered by the source itself). Empty app shell / cookie wall / CAPTCHA / bot block / HTTP error / rate limit / ToS prohibition → `status: blocked` with a `block_reason`. A blocked query is **never** "no hits" — that is the single most serious mistake possible in this task. Never solve a CAPTCHA, never bypass an access control, never invent a register number, owner, or legal status.

## Checkpoint C consolidation

After the last cluster (path A: after every dispatched cluster has returned; path B: after the sequential pass completes), gather every row with `status` in `blocked`/`not_attempted`/`pending_user_verification` across all `searchlog/<cluster-id>.json` files into one list, grouped by source. Present it to the user as plain text (URL, search string, filters per row). When the user reports back what they found, update the corresponding row: `performed_by: user`, `status: completed`, `result_summary` set to what they reported — this is what lets a manually-completed lookup satisfy its gate exactly like an agent-completed one (RISK-MODEL.md). A row the user couldn't access either just stays `blocked`.
