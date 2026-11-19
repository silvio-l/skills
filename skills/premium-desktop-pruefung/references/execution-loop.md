# Execution loop and completion contract

Use this workflow for a full audit. A user-requested partial audit retains its narrower scope. The workflow does not authorize implementation changes or new external systems.

## Choose a usable path before building infrastructure

Inventory the actual host, session and available browser/native tools first. Read platform-compatibility.md and agents.md for proportionate execution controls. Consider an identified installed build, local reviewed build with disposable profile, available local VM/container, and already authorized remote device. Select by method fidelity, available controls and setup effort, not by a preferred lab name. Record actual probes and alternatives in runtime evidence. Tool presence is not a successful probe; a historical failure is not a current failure.

Keep web, native and source evidence distinct. A browser demo with an in-memory backend can test layout, navigation and many keyboard paths; it cannot test disk persistence, native permissions, native window restoration or OS integration. A native failure does not prevent the browser sweep; a browser success does not close native units. Never keep setting up a new environment while an existing suitable path is unused.

**Prefer an idle second device for GUI runs.** Headed native input takes over keyboard, pointer and focus; on the user's working machine it collides with their work and with other sessions, and their activity contaminates the run. When an authorized second machine is available, run there:

1. Bundle the build and fixtures outside the target tree (`git archive` of the baseline plus the built artifact, a synthetic profile) and transfer it with `rsync -a --checksum` to a dedicated directory on the device.
2. Prepare the device: the desktop-automation tool with Accessibility and Screen Recording permission granted to the process that runs it, a test user without personal accounts, the default browser pointed at a blocking page, and the machine kept awake for the whole run (`caffeinate -dimsu` on macOS, or disabled sleep); a device that sleeps drops the session mid-unit. Check reachability before dispatching each package.
3. Collect evidence on the device into one directory per job, fetch it back with `rsync`, verify a SHA-256 manifest and import it with `evidence --batch`.
4. Record the device, OS build and tool versions in `profile.runtime`; list services and login items before and after (agents.md) and record activity that was not the audit as a `foreign-change` gap.

After a setup succeeds, update `profile.runtime` with evidence and immediately perform a real core task. Then return to the work queue. After a setup fails, inspect the cause and try a suitable alternative; repeat the same setup only after a relevant change. Record a method as blocked only when available applicable alternatives cannot perform it within the authorized scope. Infrastructure work must serve a named queued method.

## Discover until the inventory reconciles

The scanner checkpoints bounded work and resumes initialization, including untracked files; nested checkouts, Git-ignored directories and dependency caches are skipped and listed (`scan_ignored`) per the relevance policy in [protocol](protocol.md). Do not switch to `git ls-files` or exclusions to evade a batch limit. Follow reported unreadable paths and unresolved symlinks. Internal links to inventoried targets are fingerprinted without traversing them twice. Inventory referenced content outside the root as explicitly linked evidence/subruns when authorized; no silent following of links. External, broken or excluded link targets remain source-scan limits in the current helper: subrun evidence does not clear that gate. To close it, establish an authorized self-contained source baseline and start a linked run; never claim aggregate completeness from manual subrun reconciliation. A scan of paths does not discover all UI semantics.

Produce four evidence-backed lists and reconcile their differences: (1) audience/tasks, (2) implementation/routes/commands/configuration, (3) runtime tour, (4) platforms/data/states. Include hidden menus, dialogs, nested settings, tray/windows, onboarding exits, role/permission/feature gates and generated views. New discoveries add objects/variants and rerun `plan`; keep stable unit IDs. Review this inventory independently before interpreting a finished matrix as broad coverage.

Enumerate supported variant values separately from exercised combinations. Partition unbounded data by meaningful boundaries. Test independent failure risks explicitly; only use equivalence where implementation and observed behavior support it. Do not explode arbitrary combinations merely to inflate the matrix, or let a large matrix replace a missing semantic inventory.

**Search the tracker before you start.** Look for earlier audit runs (the issue marker `ui-ux-audit:`, earlier reports) and open issues on the same product surfaces. Known issues become `tracking` on later findings instead of duplicates, and an earlier run's inventory is a cross-check for the four lists, not a substitute.

**Keep harness files out of the target tree.** Agent harnesses write lock and state files (scheduled-task locks, worktrees under `.claude/`) into the working directory. Run the coordinator from the run directory, not from inside the audited repository; the relevance policy skips Git-ignored directories, but a run created before it (or with `--scan-all`) treats such a file as source drift. `adopt-scan-policy` moves an older run onto the policy.

**Pin the audited revision.** Tools on the test host can move the target checkout during a long run (a desktop app that keeps repository checkouts current runs `git pull`), and `drift` then reports the whole diff. Audit from a dedicated worktree at the baseline revision (`git worktree add --detach PATH REV`) from the start. If the checkout already moved, create that worktree and run `audit.py relocate RUN PATH`: it switches the run to PATH only when a scan with the run's policy reproduces the compared baseline byte for byte, and lists missing, different and extra files otherwise. A fresh worktree lacks ignored and untracked inputs such as built binaries; `--copy-missing` copies missing files that Git does not track at the new path from the current repository when they still have their baseline hash, and refuses a missing tracked file (that checkout is at another revision). The relocation is journalled in `relocations`; no reviewed row changes, so reviews stay valid. Workers and critics then read the source from the new path.

Before the first `plan` on a large inventory, and again whenever new objects arrive, record `applicability` rules for criteria that cannot apply to an object kind (a CLI or integration object has no window size or visual contrast) and `equivalences` for variants proven to share implementation and rendering. Estimate units first (objects × variants × criteria): tens of thousands of units mean the rules are missing, not that the audit is thorough. See protocol.md "Matrix rules".

## Execute bounded packages continuously

Run `audit.py next RUN --limit 12` (the limit bounds the suggested packages; a small object can go to one worker whole). It lists packages across objects/variants, blocker freshness, active jobs and review work. `limit` bounds units per package, not total audit scope; the helper does not choose which runtime is safe or certify semantic completeness. Claim one bounded package under `jobs`; never claim thousands of untouched units just to assign a common blocked reason. Respect the GUI owner and unfinished jobs before claiming work.

Schedule by user risk and evidence affinity (`next --first OBJECT` puts named objects first): complete core flows, data-loss/recovery paths and platform-specific functions early, then systematically sweep remaining surfaces and criteria. A single walkthrough can supply evidence to multiple criteria only when each expected outcome was actually observed. For each package:

1. Read the relevant criterion and method; establish preconditions and a discriminating expected outcome.
2. Exercise the original path, a meaningful alternative/counterexample and recovery as appropriate. Capture positive observations as well as deviations.
3. Import raw evidence and record only the scope established. A partial positive observation belongs in a running unit's `actual`/`limitations`; it is not a full pass. Unattempted work stays pending.
4. Import the worker result with `ingest` (or apply fragments), close/reconcile the job, add newly discovered inventory, and refresh `next`. Dispatch independent review while other executable work continues. After critic rounds run `apply-corrections` and `resolve-answered` before dispatching the next round.

Carry these workstreams through to evidenced outcomes, not merely smoke tests:

| Workstream | Required observation where applicable |
| --- | --- |
| Main tasks | Entry to useful result, cancel/repeat, alternate navigation, empty/loading/populated states |
| Errors | Controlled save/load/network/permission failure, retained input, retry, final stored state and negative control |
| Keyboard/semantics | Full task without pointer, Tab/Shift+Tab, widget keys, modal return, accessible names/roles/values and dynamic updates |
| Rendering | Actual viewport/scale, clipping/reflow, contrast across states, supported themes/locales and boundary windows |
| Native lifecycle | Real target OS/backend, fresh and existing disposable profiles, save/read-back, quit/relaunch, restored state, permissions and native integrations |
| Review/delivery | Independent inventory and terminal-unit reviews, falsified candidates, current final review, prepared issues and actual receipts |

Use M1–M9 for detailed methods. Screen readers remain opt-in. Missing participant studies limit empirical claims; they do not stop heuristic walkthroughs or technical checks.

## Blockers are observations, not a backlog label

New blocked writes require `blocker` with nonempty `attempt`, `obstacle`, `alternatives`, `next_action`, `retry_when`, `context_digest`, plus the unit's attempted `steps`, observed `actual`, primary `evidence`, `reason` and `limitations` (protocol.md lists what `apply` fills in from the blocker). Alternatives identify what was checked and why it cannot perform this method; never fill them with boilerplate. The tool validates structure/freshness; the reviewer must validate truth.

On any capability/scope/platform change, import fresh evidence and update the corresponding profile. `next` then marks old blocker records stale. Retry or reclassify affected units using owned jobs; `blocked → pending` is allowed for work that is executable again or was never attempted. Remove obsolete `blocker` from the new row; journal history retains the old record. Legacy blocked rows without structured evidence are reported as unsubstantiated, not silently converted or counted as proven obstacles. Existing runs remain readable; their next blocked write follows the new contract.

Do not mark a product defect merely because the audit tool failed. Distinguish observed behavior, inferred cause, plausible user consequence and evidence limit. Severity follows demonstrated impact. Confirmed source findings must state that runtime/native reproduction remains open, and must not claim data loss or whole-task failure from a narrower observation.

## Continue, checkpoint, or finish

A generated report is an intermediate artifact while executable requested work remains. Continue after setup, a few findings, package limits and critic gaps. Do not end with an offer to perform already requested checks.

Stop only when the requested work is complete, the user pauses/narrows it, an actual execution limit interrupts the session, or remaining work depends on specifically documented unavailable capabilities/input after suitable alternatives were assessed. Before an unavoidable handoff, persist the current job owner, last action, evidence, retry conditions and next concrete commands. Do not convert unattempted work to blocked to justify stopping. A current documented blocker still needs its retry condition evaluated; elapsed time alone is not permission to change scope.

Activity outside the audit on the test host (another session's build, remote provisioning, an OS update) is neither a product defect nor an audit result: record it as a gap with `category: foreign-change` and the affected units, and retest those units. The report lists such gaps separately.

Run drift, check and report; inspect queued reviews and the issue outbox separately. `check` certifies ledger consistency only. An incomplete inventory, unapplied review gaps, native/browser substitutions or pending delivery must stay explicit. Report separately: supported versus exercised scope, passes/failures, unexamined work, documented versus stale/unsubstantiated blockers, exclusions, review state, confirmed/suspected/refuted findings, and issue receipt URLs. Validation diagnostic counts are not product-defect counts. Do not claim a percentage of total product coverage from an incomplete inventory.
