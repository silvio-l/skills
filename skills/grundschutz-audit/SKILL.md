---
name: grundschutz-audit
description: "Autonomous ISMS audit of a repo or service per BSI IT-Grundschutz++ and ISO 27001: protection needs, modelling, technical check, risk analysis, security concept, one issue per measure. Use for 'Grundschutz-Audit', 'BSI-Check', 'Sicherheitskonzept'."
argument-hint: "[audit|verify] [scope] [quick|standard|deep]"
disable-model-invocation: true
---

# Grundschutz Audit

You act as the **information security officer (ISB)** of the organisation that owns the target. You run the BSI IT-Grundschutz method in its current form (**Grundschutz++**, BSI user catalog from the *Stand-der-Technik-Bibliothek*) end to end, map the result to **ISO/IEC 27001:2022 Annex A**, and turn every gap into a tracked measure with evidence.

The technical depth comes from Cloudflare's `security-audit` workflow, bundled unchanged in `technical/` (MIT, see `NOTICE`). This file wraps it in the Grundschutz method; on conflict, this file wins.

**What the result is:** an *unofficial, certification-oriented best-effort statement* ("Selbsterklärung"). It is not an ISO 27001 certificate, not a BSI attestation and not an audit by a certified auditor, and every report says so.

## Arguments

- `audit` (default): full run, phases 0–9.
- `verify [run-dir]`: re-check the evidence of open measures from an earlier run (see "Verify mode").
- `scope`: a path, repo or service name. Default: the current repository.
- Profile `quick | standard | deep` (default **standard**) sets the depth of phase 4 exactly as in `technical/SECURITY-AUDIT.md`. It sets how many technical findings feed the Grundschutz check. It does not change the method.

## Operating rules (non-negotiable)

1. **Fully autonomous.** Never ask the user anything. When information is missing (owners, organisational processes, protection needs), make the conservative assumption, record it in `run-metadata.json` → `assumptions[]` with the reason, and continue. An organisational requirement you cannot observe is **`nachweis_fehlt`**, never `umgesetzt`.
2. **Documentation lives outside the target.** Everything goes to `~/grundschutz-audit/<verbund>/run-<N>/` (next free N; `<verbund>` = slug of the information domain). Nothing is written into the audited repo. Nothing is published to GitHub, GitLab or any other public host, issues included (see rule 6).
3. **Read-only on the target.** No commits, no fixes, no config changes, no traffic against production. The same write isolation applies as in `technical/SECURITY-AUDIT.md`.
4. **The catalog is fetched, never bundled.** The BSI catalog is CC BY-SA 4.0. `scripts/gspp.py fetch` downloads it into `<run>/catalog/` and pins the commit. Every requirement you cite carries its ID and the catalog commit from `sources.json`.
5. **Language.** Reports use the user's language. BSI requirement texts are quoted verbatim in German with their ID. Measure IDs, file names and JSON keys stay as specified here.
6. **Issue privacy.** One issue per measure, on the target's forge (phase 8). If that tracker is public, the issue carries only the measure ID, the affected requirement IDs and a neutral title. Exploitable detail stays in the run directory.
7. **Evidence or it did not happen.** `umgesetzt` needs a pointer to concrete evidence: file:line, config, a command with its output, or a document under `evidence/`. The binary rule of UMS.1.1 applies: a requirement counts as implemented only if it is fully met **and** all its `required` dependencies are.

Helper: `python3 -I <skill-dir>/scripts/gspp.py` (stdlib only). Exit 0 = ok, 1 = findings, 2 = input error.

## Run layout

```
~/grundschutz-audit/<verbund>/run-<N>/
  run-metadata.json        scope, profile, catalog commit, assumptions[], phase status, run_status
  catalog/                 gspp fetch output (catalog.json, iso-mapping.json, *.csv, sources.json)
  01-structure.md          information domain, structure analysis, asset list
  02-protection-needs.md   protection needs per asset, with reasons
  model.json               input to gspp model (assets, categories, protection, relevance)
  package.json             requirement package (gspp model output)
  technical/               phase 4 output of the Cloudflare workflow
  check.json               target/actual check per requirement (phase 5)
  effective.json           binary status after dependencies (gspp check output)
  03-grundschutz-check.md  readable check, grouped by practice
  04-risk-analysis.md      risk analysis (BSI 200-3 / RISK.1), risk register
  05-security-concept.md   the full security concept (see CONCEPT-AND-ISSUES.md)
  06-implementation-plan.md measures M-xxx with owner, deadline, priority, issue link
  soa.json, 07-soa.md      ISO 27001 Annex A statement of applicability
  measures/M-xxx.md        full measure description (the private part of each issue)
  evidence/M-xxx/          evidence for verification
  REPORT.md                management summary and self-declaration
```

## Phases

Mark each phase in `run-metadata.json` → `phases` as `done`, `partial` (with reason) or `skipped` (with reason). Detailed method guidance for phases 1–3 and 5 is in `METHOD.md`, for phase 6 in `RISK-ANALYSIS.md`, and for phases 7–9 in `CONCEPT-AND-ISSUES.md`. Read each file when you reach its phase.

**Phase 0 — Setup.** Resolve the scope and create the run directory. Run `gspp.py fetch <run>/catalog` and record the commit and catalog date. If the fetch fails, reuse the newest cached catalog from an earlier run under `~/grundschutz-audit/` and record that as an assumption. If no cached catalog exists, stop with `run_status: "incomplete"`.

**Phase 1 — Scope and structure analysis (GC.6.1, STM.1).** Define the information domain: business processes, information, applications, IT systems, networks, rooms and service providers inside the scope, plus the interfaces at its edge. Derive the inventory from the code, infra-as-code, CI, deploy config and docs. Every asset gets an ID and one or more target-object categories from `gspp.py categories`.

**Phase 2 — Protection needs (GC.7.1).** Rate confidentiality, integrity, availability and authenticity as `normal` or `hoch` for each information object and business process. Pass the ratings to the assets using the maximum principle, cumulation effect and distribution effect, and give a reason for every rating. Before any technical work, write `02-protection-needs.md`.

**Phase 3 — Modelling (STM.2).** Write `model.json` and run `gspp.py model <run>/catalog model.json --out package.json`. Exit 1 means open gaps. In that case, decide the relevance of every listed requirement (by ID or by practice/group prefix, always with a reason). For an asset without requirements, add a category or define an own requirement in `05-security-concept.md`. Repeat until exit 0. The ISMS practices (GC, STM, UMS, VRB, PERF, RISK) are always part of the package.

**Phase 4 — Technical check.** Read and execute `technical/SECURITY-AUDIT.md` with the chosen profile. Its output goes to `<run>/technical/`. It runs autonomously under the overrides in its header. Its validators (`validate-findings.cjs`, `validate-coverage-ledger.cjs`) must pass, or the phase is `partial`.

**Phase 5 — Grundschutz check (UMS.1).** For each requirement in `package.json`, compare target and actual state and write `check.json`. Use the technical findings, the code, the configuration and the documents as evidence. Run `gspp.py check package.json check.json --out effective.json` until it exits 0. Then write `03-grundschutz-check.md`.

**Phase 6 — Risk analysis (GC.7.2, STM.4, RISK.1).** Required for every asset or requirement with protection need `hoch` and for every gap. Also required for every situation the catalog does not cover. Use the elementary threats G 0.x and the method in `RISK-ANALYSIS.md`. Each risk ends with a treatment decision; residual risks are listed for acceptance by management.

**Phase 7 — Security concept and SoA.** Write `05-security-concept.md` and `06-implementation-plan.md` (UMS.2–UMS.4). Then run `gspp.py soa <run>/catalog package.json effective.json --out soa.json` and render `07-soa.md`. Each Annex A control gets a justification for inclusion or exclusion.

**Phase 8 — Issues.** Create exactly one issue for each measure, following the forge detection and privacy rules in `CONCEPT-AND-ISSUES.md`. Write the issue URL back into the plan and into `measures/M-xxx.md`. If no forge is reachable, keep the issue body in the measure file and mark the phase `partial`.

**Phase 9 — Report.** Write `REPORT.md`: scope, catalog version, protection-need overview, status per practice, top risks, the measures, the SoA summary and the residual risk. End it with the self-declaration and the disclaimer from `CONCEPT-AND-ISSUES.md`. Set `run_status` (`complete` only if phases 0–9 are `done`). Tell the user in a few sentences where the run is, how many requirements were met or open, and the most important measures.

## Verify mode

`verify [run-dir]` (default: newest run of the current information domain) re-checks every measure that is not closed:

1. For each `M-xxx`, read `measures/M-xxx.md` and its acceptance criteria. Then inspect the current state of the target and anything placed in `evidence/M-xxx/`.
2. Verify independently: re-derive every claim from the target itself. Never accept a statement like "done" in an issue comment or commit message as evidence. Re-run the relevant technical check where possible.
3. Update `check.json` and re-run `gspp.py check` and `gspp.py soa`. Append a dated entry to `06-implementation-plan.md` (UMS.6 progress tracking).
4. When a measure is met, close its issue with a short comment that references the evidence location (privacy rules apply). When it is not met, reopen the issue or leave it open and note what is missing.
5. Regenerate `REPORT.md` with a new date and a delta section.
