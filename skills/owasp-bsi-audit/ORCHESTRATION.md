# Orchestration — Fan-out Protocol

Goal of this document: the mechanics that keep the main context free while dozens of controls get checked. Principle: **subagents read their own controls and the code themselves and write results to disk** — the orchestrator never holds the full control text or the full findings in its own context, only one-line summaries and file paths.

## Working directory

All intermediate results live under `<repo>/.audit-tmp/` (created by the orchestrator at the start, pointed out to the user at the end as the place to find things — don't commit it, it's not part of the audited repo):

```
.audit-tmp/
├── profile.json         # structure-analysis result (step 1)
├── methodik.json         # Schutzbedarf + modeling, incl. confirmed selection (steps 2+2b)
├── findings/
│   ├── asvs-v1-auth.json
│   ├── asvs-v5-validation.json
│   ├── bsi-con10.json
│   └── ...
├── report.md
├── report.html           # only with --html
└── fix-plan.md
```

## Step 1 — Structure-analysis subagent

One `Agent` call, `model: haiku`, read-only (Explore-style). Prompt skeleton:

> Profile the repo at `<path>` for a structure analysis per BSI-Standard 200-2. Identify: (1) Zielobjekte — named applications/services/data stores/client apps with a short ID (Z1, Z2, …) and title; (2) per Zielobjekt: language/framework, entry points, whether it handles auth/payment/PII; (3) backend languages and whether PHP/MySQL/Flutter/React/React Native are present; (4) relevant config files (php.ini, .htaccess, .env.example, composer.json, pubspec.yaml, package.json) and whether a running environment with `phpinfo()` is reachable. Write the result as JSON exactly per this schema to `.audit-tmp/profile.json` [inline the schema]. Return only a one-sentence summary (number of Zielobjekte, detected languages).

## Step 2 — Schutzbedarf + modeling (in the main thread, no subagent)

Small enough to stay directly in the orchestrator's context: read `profile.json` (small), assess Schutzbedarf per Zielobjekt (default normal, justification, flag outliers — see BSI-METHODIK.md Phase 2) and map Bausteine/standards (Phase 3). Write the result to `.audit-tmp/methodik.json`. From the mapping + `profile.json`, derive the *candidate* list of applicable control groups:

- Always: relevant ASVS chapters (at least V1 architecture, V5 validation, V7 auth, V8 sessions — the rest per profile)
- If PHP/MySQL: BSI CON.8, CON.10, APP.3.1, APP.4.3 (+ APP.3.2 if webserver config is present in the repo)
- If Flutter/React Native: BSI APP.1.4, MASVS's 8 categories, ASVS chapters relevant to the API surface
- Always candidates: the curated SSDF groups (PW.6, PW.9, RV.1) and the curated SLSA Build group — these apply to essentially any codebase with a build/release pipeline

Target: 10–20 groups. Merge small catalogs (< 5 controls) together, split large chapters (> 15 controls).

## Step 2b — Baustein/standard selection (confirm with the user)

Before dispatch, present the candidate group list from step 2 to the user, grouped by standard, and ask which ones to actually run via `AskUserQuestion` (multiSelect, default = everything proposed). This is not optional — never silently dispatch the full candidate set without this checkpoint (see SKILL.md step 5). Update `methodik.json`'s `modellierung[].bausteine` to reflect only the confirmed selection before proceeding. Rationale: a real BSI Grundschutz-Check's Modellierung step is human-reviewed, not an automatic formula — and different projects may reasonably want a narrower or wider scope (e.g. skip SLSA if the project has no CI pipeline yet).

## Step 3 — Dispatch (fan-out, the actual assessment)

One `Agent` call per confirmed control group, `model: sonnet`, in batches of 3–5 in parallel (one `Agent` call with multiple `tool_use` blocks per batch). Prompt skeleton per group:

> You are the assessor for control group `<group-id>` as part of a BSI-Standard-200-2 Grundschutz-Check / OWASP review of `<repo-path>`. Read the controls from `<catalog-file>` under group `<group-id>` (full text, IDs, level, description). For EVERY control: read/search the relevant code/config in the repo, judge like a human auditor (not just keyword matching — understand the actual behavior), and determine status + severity + evidence + justification + remediation exactly per `finding.schema.json`. For BSI controls use the vocabulary ja/teilweise/nein/entbehrlich with mandatory justification (see BSI-METHODIK.md Phase 4 — Basis requirements must generally be `ja`, `entbehrlich` only with a solid justification). For OWASP/SSDF/SLSA controls use pass/fail/partial/n_a. Check config values for real where possible (php.ini values, security headers, .htaccess rules — don't just assert them). Pure hosting/infrastructure requirements (physical security, data-center operations) get `status: manual` with `out_of_scope_reason` set. Write the complete array to `.audit-tmp/findings/<group-id>.json`. Reply with ONLY a one-line summary (e.g. "12 controls: 7 ja, 2 teilweise, 1 nein, 2 entbehrlich").

The orchestrator only collects these one-liners — never the full findings arrays.

For very large audits (> 25 groups), consider the `Workflow` tool with `pipeline()` over the group list instead — same prompt logic, but deterministic fan-out control outside the main context.

## Step 4 — Render (deterministic, no model)

`python3 scripts/render_report.py .audit-tmp/ [--html]` reads `profile.json`, `methodik.json`, and all `findings/*.json` from disk and produces `report.md` (+ optionally `report.html`) and `fix-plan.md`. The orchestrator only invokes this script — it doesn't read the generated files fully into its own context, just reports the path plus a short statistic (e.g. via `grep -c` on status values).

## Step 5 — Final summary

Short summary to the user: overall statistics (e.g. "134 controls checked: 98 ja, 14 teilweise, 9 nein, 13 entbehrlich; 6 critical OWASP findings"), the three file paths, a note that a re-audit is recommended after fixes.
