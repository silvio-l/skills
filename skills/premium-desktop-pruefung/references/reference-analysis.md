# Reference analysis: Cloudflare and the previous desktop audit

Research date: 2026-11-18. This is a source analysis, not a claim that the reference's agents were executed successfully.

## Source identity and inspection scope

The current Cloudflare main branch resolved to commit **c1c8a8c1471069fb0e188eeaff69b8e8db6564a8**, dated 2026-09-14. The recursive Git tree was not truncated and contained 22 files. All 22 were retrieved at that immutable revision and inspected, including the complete skill subtree. [Pinned repository](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/README.md).

| Files inspected | Purpose and actual contents |
| --- | --- |
| LICENSE; README.md | MIT license; usage and upstream design claims |
| SKILL.md | Coordinator instructions, six-stage full-audit workflow, profiles, execution safeguards, invocation budgeting |
| RECONNAISSANCE.md | Four source-grounded inventory perspectives; canonical unit identities; ledger contract; prior-run handling |
| HUNTING.md | Bounded assignments, evidence discipline, independent coverage critics, fresh-owner reassignment |
| VALIDATION-AND-REPORTING.md | Candidate falsification, three verdict contracts, final record review, report instructions |
| ATTACK-CLASSES.md | General security hypotheses and full-path verification |
| AI-AND-LLM.md; CLIENT-SIDE.md | Model/tool authority; browser sources, sinks and persistence |
| CLOUD-AND-DEPLOYMENT.md; DATA-ISOLATION-AND-LIFECYCLE.md | Source versus deployed configuration; derived copies and lifecycle boundaries |
| DESKTOP-MOBILE-AND-LOCAL-IPC.md; MEMORY-SAFETY-AND-BINARY.md | Native privilege/IPC; bounds, ownership, concurrency and binary evidence |
| PROTOCOLS-RPC-AND-MESSAGING.md; RESOURCE-EXHAUSTION-AND-AVAILABILITY.md | Producer-to-consumer semantics; bounded amplification evidence |
| SUPPLY-CHAIN-AND-RELEASE.md; WEB-PROTOCOL-AND-AUTH.md | Build-to-release identities; parser, session and account transitions |
| report-schema.json; validate-findings.cjs; validate-findings.test.cjs | Verdict schema, bounded custom schema interpreter and tests |
| validate-coverage-ledger.cjs; validate-coverage-ledger.test.cjs | Ledger snapshot validation and tests |

There is no additional executable orchestrator, sandbox launcher, artifact promoter, agent-definition file or ledger JSON Schema in that tree. Those capabilities must not be inferred from their descriptions.

## Observed mechanisms

**Discovery and scope.** Four independent reconnaissance assignments cover product/stack, principals/controls, entry surfaces/copies/sinks, and execution/deployment visibility. Materially different subsystems require focused discovery or an explicit deferred unit. Inventory follows relationships and alternative routes, not file-read totals. Domain modules activate from observed boundaries rather than language names. Architecture summaries are bounded; detailed modules load as needed. [RECONNAISSANCE.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/RECONNAISSANCE.md).

**Identity, depth and lifecycle.** A canonical tuple combines surface, boundary, subsystem and attack class, with lifecycle modes for deep audits. Encoding rules avoid line-number or agent-dependent identities. Units include paths, methods, owners, checks, unresolved facts and prior attempts. Hunters trace concrete invariants through normal, alternative, retry, failure and migration paths; unexpected boundaries return to the coordinator's queue. A pattern hit is not a finding. [HUNTING.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/HUNTING.md), [ATTACK-CLASSES.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/ATTACK-CLASSES.md).

**Delegation and isolation.** The parent alone writes shared state; workers use assigned IDs and private scratch space. Roles such as research/general are instructions, not portable installed agent definitions. Target execution requires an OS-enforced sandbox, denied external network, an empty allowlisted environment, read-only target/toolchain access, scratch-only writes and explicit resource caps. Artifact promotion specifies descriptor-anchored no-follow traversal, bounded regular files, exclusive creation and repeated identity checks. These are rigorous written requirements, but this repository does not implement their enforcement. [SKILL.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/SKILL.md), [VALIDATION-AND-REPORTING.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/VALIDATION-AND-REPORTING.md).

**Coverage and reopening.** Planned and in-progress units cannot contain terminal evidence. Covered units require checks and no unresolved facts; candidate units require fingerprints; blocked units retain partial evidence and blockers. Deferred and excluded units carry reasons. Reassignment archives the exact terminal attempt, increments the wave, changes owner and clears live evidence. A post-wave critic reads source and proposes missing units or deeper reassignment. Standard/deep runs reserve a distinct final-clean critic; quick audits have one wave and explicitly defer critic-discovered work. Budget exhaustion never means completion. [RECONNAISSANCE.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/RECONNAISSANCE.md), [HUNTING.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/HUNTING.md).

**Independent validation and falsification.** Fresh reviewers must reconstruct candidates from primary source and bounded observations, check preventing controls and attempt refutation. Confirmed, needs-validation and rejected records have different required fields. Unvalidated candidates remain in the ledger, outside final findings. Standard/deep profiles add a second final-record verifier; quick combines those reviews but retains a separate reviewer. Changed evidence requires renewed verification. [VALIDATION-AND-REPORTING.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/VALIDATION-AND-REPORTING.md).

**Resume and context economy.** Prior evidence is reused only after source/condition checks. Prior blockers, exclusions and changed source generate current work; a rejected hypothesis suppresses only that exact unchanged claim. Stable identities, bounded packets, lazy modules and reserved critic/verifier budgets support continuation. No persistent job service, lock protocol or crash recovery command is supplied. [SKILL.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/SKILL.md), [RECONNAISSANCE.md](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/RECONNAISSANCE.md).

## What the deterministic code proves

The findings validator implements the supplied schema itself, including a custom visibleContent keyword. It rejects unsupported schema keywords, malformed verdict shapes, duplicate/unsorted fingerprints, unsafe relative path syntax, invalid trace ordering and severity exceeding demonstrated impact. It bounds input to 5 MiB, depth to 64, top-level findings to 1,000 and diagnostics to 100. It checks own properties and handles Unicode/control-character diagnostics defensively. This is not a general JSON Schema engine. [Validator](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/validate-findings.cjs), [schema](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/report-schema.json).

The ledger validator checks canonical identity, unique units, snapshot status invariants, ownership, reviewed-path unions, ordered attempt waves, fresh reassignment owners and evidence non-reuse. Its bounds include 5 MiB, 10,000 units, 64 nested levels and 100 diagnostics. Artifact ownership is a string-path rule. Extra bookkeeping keys are permitted. [Ledger validator](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/validate-coverage-ledger.cjs).

Neither validator proves source paths exist, referenced lines support a claim, artifact bytes exist or are truthful, discoveries are complete, agents are independent, history was never rewritten, or rendered reports match findings. Findings and ledger are validated separately: there is no cross-file closure gate. An empty ledger, or one containing unfinished units, can be structurally valid. Safe opening of the validator's input file is not the full descriptor-based scratch-promotion implementation described in prose.

## Tests actually executed

Both unmodified upstream suites were run together on macOS with Node v26.13.1:

```sh
node --test <reference-checkout>/skills/security-audit/validate-findings.test.cjs \
  <reference-checkout>/skills/security-audit/validate-coverage-ledger.test.cjs
```

Result: **65 tests passed, 0 failed, 0 skipped**, duration 1,299.397042 ms. The suites cover valid and invalid records, malformed schemas, paths, terminal controls, Unicode, symlinks/FIFOs, input/resource limits, canonicalization, owner consistency and archived attempts. Sources: [findings tests](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/validate-findings.test.cjs), [ledger tests](https://github.com/cloudflare/security-audit-skill/blob/c1c8a8c1471069fb0e188eeaff69b8e8db6564a8/skills/security-audit/validate-coverage-ledger.test.cjs). They use temporary fixtures; no production target was executed. No full Cloudflare agent audit, deployed sandbox or discovery benchmark was run. Passing these suites supports the implemented validators, not empirical end-to-end audit effectiveness.

## Critical assessment and transfer decisions

The following are this implementation's conclusions, not upstream claims.

- Preserve relationship-based discovery, stable IDs, alternative-path tracing, source-grounded exclusions, fresh reviewers, falsification, explicit unknowns and separately reserved validation capacity.
- Preserve append-only attempt intent, but add executable transition/ownership controls and recovery behavior rather than relying solely on final snapshots.
- Extend validation across inventory, criteria, evidence, findings and reports; verify evidence integrity and source freshness where technically possible. A machine gate still cannot prove semantic completeness.
- Replace security attacker/sink/severity concepts with audience, task, state, interaction, accessibility criterion and user impact. Do not copy attack-class checklists into UI/UX.
- Treat rendered observations and interaction traces as primary UX evidence. Source alone cannot establish focus behavior, real rendering, assistive-technology support or perceived simplicity.
- Use evidenced variant equivalence and explicit scenario matrices. Neither a Cartesian product too large to execute nor an arbitrary coverage percentage establishes completeness.
- Do not import source code or substantial verbatim prose from the MIT reference. The new implementation applies independently described principles; copying upstream implementation later would require retaining its license notice.

## Relationship to the previous premium-desktop-pruefung

The previous SKILL.md, Premium-Desktop-Design.md, method catalog and protocol were inspected before replacement. They already supplied audience-specific simplicity, rendered-UI evidence, first-success/routine/recovery scenarios, four inventory views, cross-surface persistence links, stable rule IDs, 46 catalog rules, one shared-state writer, fresh critiques and resource-aware work packets.

Retain that product standard and useful legacy criteria, plus the four product/code/runtime/platform perspectives. Preserve serialized GUI ownership and bounded static work packages. Extend coverage to web applications, the complete applicable WCAG 2.2 A/AA set, adaptive conditions and explicit objective-versus-heuristic evidence.

Replace the old automatic implementation/retest loop with reproducible findings and issue delivery. Issue creation is not a product fix and must not be reported as one. Target edits require a separate explicit authorization and later regression validation. Replace hard-coded Claude variables, agent types, background-call syntax and project implementer names with detected runtime capabilities. A serial counter-review must disclose reduced independence instead of claiming a fresh agent was used. These are intentional behavior changes, not evidence that the original workflow already provided them.

