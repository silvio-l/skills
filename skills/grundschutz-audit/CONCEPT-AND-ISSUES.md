# Method: phases 7–9 (concept, SoA, issues, report)

## Phase 7: Security concept (`05-security-concept.md`)

The concept is the main document an auditor reads first, and it must make sense on its own. Use this structure:

1. **Introduction:** the organisation, the purpose, the date, the catalog version and commit (`catalog/sources.json`), and the method (Grundschutz++ plus the technical check, profile).
2. **Information domain and structure analysis:** a summary of `01-structure.md`, the network plan, and the interfaces.
3. **Protection needs:** a summary table and the reasons for every `hoch`.
4. **Modelling:** the requirement package by practice. List the relevance decisions with their reasons, any own requirements for assets the catalog does not cover, and any changed parameter values (STM.5).
5. **Grundschutz check result:** totals; status per practice; blocked dependencies.
6. **Risk analysis:** the method, the top risks, and the treatment decisions (from `04-risk-analysis.md`).
7. **Measures:** a reference to `06-implementation-plan.md`, with the ten most important measures summarised.
8. **Residual risk and acceptance:** the residual risks with a proposed acceptance by management, which the organisation must sign.
9. **ISO 27001 mapping:** a summary of the SoA.
10. **Assumptions and limits:** everything from `run-metadata.json` → `assumptions[]`, plus anything not observable from the target.

## Implementation plan (`06-implementation-plan.md`, UMS.2–UMS.4)

The plan has one row per measure:

| field | content |
|---|---|
| `M-xxx` | stable ID; reused by later runs and verify mode |
| title | short and neutral, safe for a public tracker |
| requirements | catalog IDs this measure makes effective |
| risks | `R-xxx` it reduces |
| priority | P1 (MUSS gap or risk hoch or higher), P2 (SOLLTE gap or risk mittel), P3 (rest) |
| owner | role, e.g. "maintainer" or "ISB" (UMS.3), assumed if unknown |
| deadline | relative to the run date (UMS.4): P1 30 days, P2 90 days, P3 180 days unless the catalog parameter says otherwise |
| acceptance criteria | checkable statements; what evidence verify mode will look for |
| effort | from the requirement's `effort_level`, 0–5 |
| issue | URL (phase 8) |
| status | open, in progress, done (verified), exception (UMS.5, with reason and expiry) |

`measures/M-xxx.md` holds the full detail:

- affected assets and files;
- the technical finding IDs;
- the verbatim requirement texts;
- the implementation steps;
- the acceptance criteria;
- the evidence location `evidence/M-xxx/`.

## ISO 27001 statement of applicability (`07-soa.md`)

Render `soa.json` as a table of the Annex A controls with these columns:

- the control;
- the mapped Grundschutz++ requirements;
- applicable yes or no;
- the state (`implemented`, `partially_implemented`, `not_implemented`, `not_applicable`);
- a justification for inclusion or exclusion.

The mapping is the BSI's own (`catalog/iso-mapping.json`). For a control without mapped requirements, argue applicability directly from the structure analysis. Clauses 4–10 of ISO 27001 (the ISMS core) correspond to the ISMS practices GC, STM, UMS, VRB, PERF and RISK, so summarise them in one section.

## Phase 8: Issues

**Detect the forge** from `git remote get-url origin` of the target. Use the matching CLI, already authenticated:

- `gh` for GitHub;
- `glab` for GitLab;
- `tea` or internal forge-cli (`fj`) for Gitea or internal forge;
- the forge's REST API with an existing token.

When none works, write the issue bodies into `measures/` and mark the phase `partial`. Never ask for credentials.

**Visibility.** Check whether the repository is public, for example `gh repo view --json visibility` or the `private` field of the API. Then choose the issue content:

- **Private tracker:** title `[M-xxx] <neutral title>`. The body holds the requirement IDs, priority, deadline, acceptance criteria and a summary of the steps, plus a pointer to the measure file name, without absolute paths.
- **Public tracker:** title `[M-xxx] <neutral title>`. The body holds only the requirement IDs, priority, deadline and the line "Details are kept in the private audit documentation." It never contains vulnerability details, file paths, endpoints, payloads or findings. A confirmed vulnerability is never described in a public issue; if the forge offers private security advisories, use those.

**Idempotence.** Before creating an issue, search the open and closed issues for `[M-xxx]`. Update an existing one instead of creating a duplicate. Use the labels `security` and `grundschutz` when they exist, and do not create labels.

Write each issue URL back into the plan and into `measures/M-xxx.md`.

## Phase 9: Report (`REPORT.md`)

1. Management summary, at most 15 lines: the scope, the overall picture, and the 3–5 most important measures.
2. Key figures: the requirements in the package, with totals per status and the effective share by modal verb; the risks by level; the measures by priority; and the SoA state counts.
3. The catalog version and commit, the profile, the run date, and the phase status.
4. The residual risks proposed for acceptance.
5. **Self-declaration** (in the report language), with this content:

   > This information domain was assessed against the BSI IT-Grundschutz++ user catalog (version/commit) and mapped to ISO/IEC 27001:2022 Annex A. Of N requirements in the package, X are effectively implemented. Open requirements are covered by the measures M-001 to M-NNN with owners and deadlines. The residual risks listed above require formal acceptance by management.

6. **Disclaimer**, which must not be removed:

   > Unofficial, automated best-effort assessment by an AI agent acting in the role of an information security officer. It is not a certification, attestation or audit under ISO/IEC 27001, BSI IT-Grundschutz or any other scheme. It does not replace an audit by an accredited certification body or BSI-certified auditor, and it covers only what was observable from the assessed sources. Organisational requirements without evidence are reported as not verified.
