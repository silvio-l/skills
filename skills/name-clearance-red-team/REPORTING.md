# Reporting — Layout & Mode Variants

`scripts/render_report.py <workdir> --mode deep|quick|launch|handoff [--html]` is the only place a report gets assembled. It never re-implements band/gate/verdict logic — every risk-relevant number comes from `risk_model.py`. This document describes the layout it produces, for anyone reading a report or maintaining the renderer.

## `report.md` — common structure (`deep`, `launch`, `handoff` modes)

In order:

1. **Title + disclaimer.** Name, generation timestamp, mode. A fixed paragraph stating this is a preliminary, conservative screening, not legal advice, and that a `LAWYER CLEARANCE REQUIRED`/`DO NOT USE` verdict or any hard-stop finding should go to a qualified professional before further use.
2. **Freedom-to-use verdict.** The band badge + verdict string from `risk_model.verdict_for()`, plus the dominating finding's id and summary (or "no adverse findings on record" if none).
3. **Registrability assessment.** A **separate** verdict from the one above — computed the same way (`risk_model.overall_band()`) but restricted to `category: absolute_ground` findings only. Registrability (can this even be filed as a mark) and freedom-to-use (does using it collide with someone else's existing rights) are different questions with different answers possible: a name can be perfectly registrable and still infringe an existing mark, or face an absolute refusal ground and still be safe to use as an unregistered business name. Never collapse these into one line.
4. **Assumptions.** Every entry from `profile.json`'s `assumptions` array — what was defaulted instead of asked, and why.
5. **Territorial coverage.** A territory × source-category table: for each target territory and each source category actually appearing in the search log, `completed` / `blocked` / `partial` / `not searched`, with a detail column showing the underlying status counts. A territory with no rows at all reads `not searched` — this is what makes an accidentally-skipped territory visible at a glance.
6. **Findings.** One table row per finding (id, territory, category, mark/name, owner, `visual/phonetic/conceptual` similarity, goods proximity, band, evidence quality), followed by one subsection per finding with its summary, strongest counter-argument, and evidence entries.
7. **Digital availability.** The `digital-availability.json` records as a table (identifier, status, method, reason).
8. **Red team.** Every attack (vector, severity, argument, rebuttal) and any unresolved `missed_vectors`.
9. **Gate status.** All 13 gates with ✅/❌ and their reason string, verbatim from `derive_gates()`.
10. **What is missing and how to complete it.** Every open gate's reason, plus every unresolved search-log row's `manual_instructions` — this section is what turns `RESULT INCOMPLETE` into an actionable next step instead of a dead end.
11. **Limitations.** A fixed paragraph: no worldwide-coverage claim, absence of a finding is not proof of freedom to use, `manual_only` sources per SOURCES.md were only checked where a row explicitly says so, and the report has no opinion on anything outside the territories/goods/sources actually in scope.

## `RESULT INCOMPLETE` handling

When any gate is false, section 2's verdict line is replaced by `RESULT INCOMPLETE – NO RELEASE RECOMMENDATION POSSIBLE` — **every other section above still renders in full.** This is the direct implementation of RISK-MODEL.md's gate-enforcement rule: an incomplete run must never look like an empty or broken report, or the incentive becomes to fake gate completion just to get something usable.

## `--mode quick`

Skips sections 3–11 entirely. Just the title/disclaimer plus one line: the Quick Scan verdict (`GO TO DEEP CHECK` / `RENAME LIKELY` / `IMMEDIATE STOP`) and a reminder that this is a triage result, never a green light.

## `--mode launch`

Everything in the common structure, plus a **Launch economics** section between Red team and Gate status, sourced from `profile.json`'s optional `launch_economics` object: `sunk_cost`, `rename_cost_estimate`, `coexistence_strategy`, `goods_services_narrowing`, `alternate_spelling_considered`, `defensibility_assessment`. Collected via a short additional intake pass before rendering (SKILL.md — launch mode is a render pass over an existing `deep` working directory, not a new research pipeline); if that intake was never run, the section says so plainly rather than being silently omitted.

## `--mode handoff`

Renders the common `report.md` as usual, **and additionally** writes `lawyer-handoff.md`: case context (name type, goods/services, territories, planned use, flagged prior events), the search variants actually used, the strongest conflicts ranked by band (top 10), every open gate and every hard-stop-triggering finding as an explicit open legal question, and a flat evidence list (finding id → url/register_id). This is the document meant to leave this skill's context entirely and go to counsel — it deliberately omits the narrative framing and disclaimer boilerplate a lawyer doesn't need.

## `--html`

Wraps the same Markdown content in a minimal self-contained HTML page (light/dark aware via `prefers-color-scheme`) with a colored verdict badge at the top. It is a rendering of the same data as `report.md`, never a separate content source — if you need to change what a report says, change `render_markdown()`, not the HTML template.
