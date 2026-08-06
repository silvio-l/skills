---
name: name-clearance-red-team
description: "Adversarial clearance for a company/product/app name: hunts conflicting trademarks, company names and unregistered rights, red-teams it, scores the risk. Markenrecherche, Namensrecherche, Firmennamen prüfen. Usage: /name-clearance-red-team <name>"
disable-model-invocation: true
metadata:
  argument-hint: "<candidate-name> [quick|deep|launch|handoff]"
---

# Name Clearance & Legal Risk Red Team

Adversarial screening for a candidate name (company, product, app, service, publication, event, …). The job is to find every reason the name might be legally, competitively, or economically risky — never to confirm it is safe. Output is one of five conservative verdicts (`PRELIMINARILY CLEAR`, `PROCEED WITH CONDITIONS`, `MODIFY BEFORE USE`, `LAWYER CLEARANCE REQUIRED`, `DO NOT USE`) or, when the research plan could not be fully executed, `RESULT INCOMPLETE`. **This is never a legal guarantee and never a substitute for a lawyer** — a `LAWYER CLEARANCE REQUIRED`/`DO NOT USE` verdict, or any hard-stop finding, means exactly that: get a qualified trademark/legal professional before using, filing, or investing further in this name.

Read before running a step: [METHODIK.md](METHODIK.md) (phases 1–8, what each phase actually checks), [SOURCES.md](SOURCES.md) (register catalog, access mode per source), [ORCHESTRATION.md](ORCHESTRATION.md) (fan-out protocol, working directory, capability handling), [RISK-MODEL.md](RISK-MODEL.md) (normative — the only place a band/verdict is defined), [REDTEAM.md](REDTEAM.md) (the adversarial pass), [REPORTING.md](REPORTING.md) (report layout, mode variants).

## Modes

- **quick** — fast triage over high-priority variants only. No fan-out, no red team. Verdict is one of `GO TO DEEP CHECK` / `RENAME LIKELY` / `IMMEDIATE STOP` — never a green light, never one of the five main verdicts.
- **deep** — the full pipeline below. Produces `report.md`/`report.html` with one of the five main verdicts (or `RESULT INCOMPLETE`).
- **launch** — `deep`'s report plus a short economic intake (sunk cost, rename cost, coexistence strategy, alternate spelling, defensibility) and one more synthesis pass, rendered over an *existing* deep-clearance working directory. Not a separate research pipeline.
- **handoff** — pure render pass over an existing deep-clearance working directory: produces `lawyer-handoff.md` (open legal questions, strongest conflicts, evidence, search variants used) for hand-off to counsel. No new research either.

`launch` and `handoff` both require step 1–10 of a `deep` run to already exist on disk for this name; if they don't, run `deep` first.

## Flow

0. **Parse the invocation.** `/name-clearance-red-team <name> [quick|deep|launch|handoff]` where slash commands are supported; otherwise the user names the skill together with a candidate name. No mode given → ask at Checkpoint A (plain text, lettered options — see below). No name given → ask for one before anything else.

1. **Checkpoint A — Intake.** Check the repo and conversation context first (`package.json`, `README`, `app.json`, prior messages, …) for anything already known — never make the user retype what's already visible. Only ask for what's genuinely missing. `goods_and_services` and `target_territories` are **never** inferred or defaulted silently — always confirm them explicitly, even if a plausible guess exists. Ask the mandatory prior-events question (cease-and-desist received, ongoing dispute, unclear rights chain, already-high investment) — four of the fourteen RISK-MODEL.md hard stops are only discoverable this way, no search finds them. Write `profile.json` per `schema/profile.schema.json`. Every recommended-field default actually used goes into `assumptions` — never silently. `AskUserQuestion` is not assumed available here; ask as plain text with lettered options (a, b, c…) and take the letter back as the answer. See METHODIK.md Phase 1 for the full field list and defaults.

2. **Phase 2+3 — Decomposition + variants.** Run `python3 scripts/generate_name_variants.py "<name>" --languages <profile.languages> --out <workdir>/variants.json` for the deterministic orthographic/phonetic/transliteration variants. Then fill each `semantic_hint` slot (translation, synonyms, acronym) per METHODIK.md Phase 3 and append the results into `variants.json` — this part is not scriptable without substituting model knowledge for research, so it stays manual.

3. **Phase 4 — Absolute grounds.** Directly in the main thread, no subagent (small enough): check descriptiveness, genericness, and other absolute refusal grounds per target language, per METHODIK.md Phase 4. Record a completed `searchlog/linguistic-<lang>.json` row per language regardless of outcome — this is what the `absolute_grounds_checked` gate actually reads — and additionally write a finding (`category: absolute_ground`, `language` set) only if the assessment turns up a real concern.

4. **Capability check.** Before building the search plan, establish what this environment can actually do: fetch a URL, run a web search, execute `python3`, write files in a working directory, dispatch parallel sub-tasks. Do not assume — a capability not actually exercised yet this session is unproven. If web fetch and web search are both unavailable, say so plainly, skip the fan-out entirely, and go straight to Checkpoint C with a full manual-lookup handoff (every planned row `not_attempted`, `manual_instructions` filled in for each). **A run with no research capability produces a handoff document, never a verdict.**

5. **Build the search plan.** Cross variants × target territories × sources from SOURCES.md into `searchlog/_plan.json` (every row `status: not_attempted` initially, and every row's `cluster_id` already set to the cluster it belongs to — never added later) — see ORCHESTRATION.md for the row shape and cluster keys. **Quick Scan branches off here**: high-priority variants only, no fan-out, no red team, straight to rendering with `--mode quick`.

6. **Checkpoint B — Scope confirmation.** Plain text: show the variant list, the Nice-classification read on `goods_and_services`, the territory × source matrix, and which sources are manual-only. Let the user trim or extend before committing to the fan-out — this is the point where an obviously oversized or undersized plan gets caught.

7. **Fan-out — research.** One cluster per territory × source group (see ORCHESTRATION.md's cluster table). Run every step at this environment's default reasoning capability — never downgrade for any step, including the "mechanical" lookups (see "Capability tier" below). If the environment can dispatch parallel sub-tasks that read/write files independently, dispatch one per cluster and collect only one-line summaries back. If it cannot, work the clusters sequentially in-context, writing both `searchlog/<cluster-id>.json` and `findings/<cluster-id>.json` (even if empty) before moving to the next cluster. Full protocol, including the anti-fabrication clause every research step must follow literally: ORCHESTRATION.md.

8. **Checkpoint C — Manual-lookup handoff.** After the *last* cluster (never interrupt at the first blocked lookup), consolidate every `blocked`/`not_attempted`/`pending_user_verification` row into one handoff list: exact URL, search string, filters. The user looks these up however their own environment allows (a browser, a browser-automation tool if they have one — never assumed, never required) and reports back what they saw; report back either specific results or an explicit "no results". Update the corresponding rows to `performed_by: user`, `status: completed` (or leave `blocked` if the user couldn't get in either). Never solve a CAPTCHA or bypass an access control yourself.

9. **Red team.** Mandatory, no exceptions — see REDTEAM.md. Use the strongest reasoning/effort setting this environment offers, if it offers a choice (see "Capability tier" below). Write `redteam.json`.

10. **Synthesis + render.** A synthesis pass (same capability-tier rule as step 9) writes only the narrative framing to `synthesis.md` — it never writes a verdict; the verdict comes exclusively from `scripts/risk_model.py` via the renderer. Then `python3 scripts/render_report.py <workdir> --mode deep --html` (always pass `--html` unless the user explicitly wants Markdown only).

11. **Wrap-up.** Report to the user: the verdict line, the dominating finding, gate status (`python3 scripts/check_gates.py <workdir>` if you want the table without re-rendering), and the file paths — don't paste the full report into the chat, the files are the source of truth. If the working directory sits inside a git repo, offer (don't silently do) a `.gitignore` entry for `.name-clearance-tmp/` — the report can contain unflattering assessments of named third parties.

A `deep` run is done when: every planned search-log row is `completed` (by agent or user) or explicitly `blocked` with a reason, the red team has run, and `render_report.py` completed without error. It does **not** need every gate to be true — an incomplete run still renders, just with `RESULT INCOMPLETE` as its verdict line and everything else intact (see RISK-MODEL.md).

## Capability tier

This skill names no model. Run every step at your environment's default reasoning capability. Two adjustments, both conditional on the host actually offering a choice:

- **Never downgrade.** If your environment lets you pick a faster/cheaper/lower-effort option, do not pick it for any step of this skill — not for the "mechanical" lookups either. Every step that reads a search result or a fetched page must be able to tell *"the register returned no hits"* apart from *"the lookup never actually happened"* (empty app shell, cookie wall, CAPTCHA, bot block, HTTP error, rate limit). Misreading the second as the first is this skill's worst possible failure, and it happens at the cheapest step, not the hardest one.
- **Upgrade where it's offered.** If your environment exposes a stronger reasoning option or a higher effort/thinking setting, use it for the Red-Team pass and the Synthesis pass — they weigh conflicting evidence and argue against the user's preferred outcome, which is where extra reasoning changes the answer. If no stronger option exists, run them at the default; never skip them.

## Important rules

- **Anti-fabrication is absolute.** `status: completed` only when actual result content was seen — a hit list, or an explicit "no results" rendered by the source itself. An empty app shell / cookie wall / CAPTCHA / bot block / HTTP error / rate limit / ToS prohibition is `status: blocked` with a `block_reason`, never "no hits". A blocked query is never, ever recorded as a clean result. Never invent a register number, owner, or legal status. Full clause: ORCHESTRATION.md.
- **Gates are computed, never written.** Every gate in RISK-MODEL.md comes out of `risk_model.derive_gates()`, reading `profile.json`/`variants.json`/`searchlog/*`/`findings/*`/`redteam.json` from disk. No step in this skill sets a gate boolean directly — that is precisely the shortcut that would defeat the whole design under time pressure.
- **Evidence quality is recomputed, not trusted.** `risk_model.cap_evidence_quality()` derives the usable evidence quality from `verification_status`, ignoring whatever a finding claims for itself.
- **Verdicts come from one place.** Only `risk_model.verdict_for()` produces a verdict string. No step in this skill writes one directly.
- **Each territory stands alone.** Never merge two target territories into one search row or one finding — RISK-MODEL.md and the gates assume per-territory granularity throughout.
- **`.name-clearance-tmp/<name-slug>-<YYYY-MM-DD>/` lives in the user's own working directory**, not in this skills repo. One subdirectory per run (not a flat directory) so repeated runs after a rename don't overwrite prior evidence and launch-decision comparisons across name candidates stay possible.
