# Method: phases 1–3 and 5

Requirement IDs refer to the BSI Grundschutz++ user catalog. Use `gspp.py show <run>/catalog <id>` to read the exact current text, and never cite from memory.

## Phase 1: Scope and structure analysis

**Information domain (Informationsverbund, GC.6.1, STM.1).** Name the organisation, the business processes and the services in scope, together with their boundary. A repository alone is rarely a complete information domain. Include what the code depends on to run: hosting, CI/CD, DNS, identity provider, mail, backups, third-party APIs, the people and roles that operate it, and the rooms or cloud regions. Things outside the domain are interfaces and are listed as such.

**Sources of truth, in this order:**

1. Code and infra-as-code: Dockerfiles, compose, Terraform, Kubernetes, systemd, nginx and similar.
2. CI and deploy config.
3. Lockfiles and SBOM.
4. Repo docs: README, runbooks, ADRs, SECURITY.md.
5. Commit history, for owners and maintenance practice.
6. Public metadata of the service.

Record every inference you cannot verify as an assumption.

**Asset list.** Write one table for the asset types in this order:

- business processes;
- information (data classes);
- applications;
- IT systems;
- networks and communication links;
- rooms and locations, including cloud regions;
- service providers and outsourcing;
- people and roles.

Each row has an ID, a name, a description, an owner (assumed if unknown), its dependencies, and one or more **target-object categories**, the exact names from `gspp.py categories`.

**Grouping.** Group assets that are of the same type, configured alike and have the same protection need. Examples are a pool of identical containers or every developer laptop. Do not group anything else.

**Network plan.** Describe the network as text or a Mermaid diagram: zones, trust boundaries, external connections, and administrative access paths. The technical check (phase 4) reuses these boundaries.

## Phase 2: Protection needs (GC.7.1)

**Scale.** The catalog uses two levels:

- **normal:** damage is limited and manageable;
- **hoch:** damage is considerable or threatens the organisation.

When damage could be existential, rate it `hoch` and flag it in the text as "sehr hoch". The risk analysis is then mandatory, and the asset needs its own requirements in the security concept beyond the catalog.

**Damage scenarios.** Assess each scenario for each information object and business process:

- violation of laws, regulations or contracts (e.g. GDPR Art. 32);
- impairment of the right to informational self-determination;
- physical injury;
- impaired performance of tasks;
- negative internal or external effects, such as reputation;
- financial consequences.

Rate each scenario for confidentiality, integrity, availability and authenticity, and give a one-line reason.

**Inheritance to assets.**

- **Maximum principle:** an asset takes the highest need of all processes and information that depend on it.
- **Cumulation effect:** many `normal` dependents can add up to `hoch`, for example a single host that serves every business process.
- **Distribution effect:** redundancy or partial dependence can lower a need. Only lower it when the reason is documented and verified, never by assumption.

Write `02-protection-needs.md` as a table: one column per dimension, plus the reason for each rating. Map the result to `protection` in `model.json`.

## Phase 3: Modelling (STM.2)

`model.json` lists the assets with their categories and protection needs, plus `relevance` decisions. `gspp.py model` then implements STM.2.1:

- The ISMS practices (GC, STM, UMS, VRB, PERF, RISK) are always selected (STM.2.1.1).
- Category inheritance: a requirement for `IT-Systeme` also applies to `Hostsysteme` (STM.2.1.4.1). Synonyms resolve to their canonical name.
- `erhöht` requirements are selected only for an asset rated `hoch` in a dimension the requirement addresses. A requirement without any dimension counts for every dimension.
- Requirements are deduplicated: each appears once and lists all its assets (STM.2.1.4.2).
- Requirements without a target-object category need an explicit relevance decision with a reason (STM.2.1.5). Decide by exact ID or by a prefix (`GEB` or `GEB.3`); the most specific key wins. Typical outcomes:
  - a pure SaaS or cloud deployment usually marks `GEB` (buildings) irrelevant, with the reason "operated by provider X, covered by DLS". The DLS requirements on the provider then stay relevant.
  - `BES` (procurement) and `PERS` (personnel) are relevant whenever the organisation buys services or employs people. If you cannot observe them, their status will be `nachweis_fehlt`, which is fine; they are not irrelevant.
- An asset that no requirement matches (`assets_without_requirements`) gets either a better category or its own requirements in the security concept.
- `dependencies_outside_package` lists `required` links that point outside the package. Add them via relevance, or justify in the check why the dependency does not apply.

Iterate until `gspp.py model` exits 0.

## Phase 5: Grundschutz check (UMS.1)

For each requirement in `package.json`, write one entry in `check.json`:

| status | meaning | required fields |
|---|---|---|
| `umgesetzt` | fully met for all listed assets | `evidence` (list of pointers) |
| `teilweise` | met for some assets or aspects | `measure`, `note` |
| `nicht_umgesetzt` | not met | `measure` |
| `entbehrlich` | not needed, e.g. covered otherwise | `justification`; for MUSS also `risk_ref` |
| `nachweis_fehlt` | cannot be verified from the target | `measure` (usually "create and document") |

**Rules:**

- **Binary outcome (UMS.1.1).** Only a fully met requirement counts. `gspp.py check` derives `effective` yes or no, including the `required` dependencies. `blocked_by_dependency` lists requirements whose own status is fine but whose dependency is open. Name these in the report.
- **Parameters.** The catalog's `{{ insert: param }}` values are BSI defaults. If the organisation needs a different value (STM.5), document the chosen value and its reason in the concept.
- **Organisational requirements.** Examples are policies, trainings, management reviews and contracts. Documents found in the target, its wiki or docs count as evidence. Without one, the status is `nachweis_fehlt` with a measure to create and approve the document; never `umgesetzt` by assumption.
- **Technical findings.** Every `confirmed` finding from phase 4 makes the affected requirements at most `teilweise` and is cited by its finding ID. A `needs_validation` record is cited as an open point and does not lower the status by itself.
- **Measures.** One measure can close several requirements. Number them `M-001`, `M-002`, … in order of priority. They are specified in `06-implementation-plan.md` (see `CONCEPT-AND-ISSUES.md`).

`03-grundschutz-check.md` presents `check.json` per practice and group: the requirement ID, modal verb, short title, assets, status, evidence or measure, and the effective yes/no. Above the table, give totals per status and the share of effective MUSS, SOLLTE and KANN requirements.
