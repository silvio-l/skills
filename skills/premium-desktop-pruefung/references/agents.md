# Execution and independent agent contracts

## Capability and isolation contract

Before dispatch, inspect actual exposed agent/session tools. A conceptual role does not install a runtime agent. Codex may expose spawn/send/wait tools or CLI execution; Claude may expose Agent with fresh contexts. Prefer a fresh context rather than a history fork. When available, create specialized workers using the runtime's real API, never a fictional tool or hard-coded agent class. Record tool, session identity, baseline and context supplied. If no separate agent/session is available, use an explicitly separated second pass and keep independent validation open.

Do not shell out to another model CLI merely because its binary exists: check authentication, supported sandbox/tool flags and execution policy. Scope and resource limits apply to child agents too. Screen-reader execution is disabled unless the user explicitly requested it; pass this scope to every worker and critic. They must not enable, install or request screen readers on their own, including for falsification or retesting. Child workers cannot spawn more agents or launch builds without coordinator assignment. Suggested defaults: at most three workers, twelve related units per package, one GUI owner, one build, and bounded external commands. Change batch sizes for actual evidence volume, never discard queued work. Load catalogue rows by ID and source slices by location; preserve raw artifact paths and hashes rather than pasting enormous logs into context.

## Worker brief

Give only: target repository and immutable baseline; product audience/tasks; relevant object/variant/unit IDs; corresponding criteria and method rows; allowed source paths; isolated runtime/profile; job ID and owner; allowed tools/time/resource budget; output fragment path and evidence namespace. Ask the worker to:

1. Trace implementation and the actual entry/exit path, including dependencies and alternate entry points.
2. Execute the applicable method; record steps, environment, expected/actual and primary evidence for every disposition.
3. Challenge its own hypothesis once, recording the alternate explanation and observation.
4. Return per-unit fragments, suspected findings and gaps. Do not confirm its own finding, publish issues, change product code, merge another worker's results or claim global completeness.

Shared GUI access must be serialized. Parallel workers may inspect disjoint static sources. Use a queue for browser/native stateful tests; each job restores only its isolated test profile. An interrupted worker is not presumed finished.

## Independent critic brief (blind first)

First provide raw repository, audience/task contract, baseline and runtime access **without investigator verdicts**. Ask for an independent route/window/command/configuration/state inventory, particularly indirect and alternative paths. Record this independently derived list as evidence. Then provide ledger and raw artifacts:

- Reconcile the independently derived inventory with objects/variants, file exclusions, the not-inventoried directories (`scan_ignored`) and relationships. Find missing paths and unsupported equivalence claims.
- Select original files, build/version and runtime evidence directly; do not rely on summaries or screenshots alone for behavior.
- Review each terminal unit's method and evidence. Keyboard interaction needs a sequence and focus observations; persistence needs restart; visual quality needs actual rendered inspection; user-perception claims need suitable user evidence or explicit heuristic qualification.
- Actively falsify each candidate: alternate accessible name source, authorized role differences, valid WCAG exception, transformed color/background, intended platform behavior, stale build or test setup error. Record attempted counterexample and outcome, including when the claim survives.
- Return explicit accepted/refuted/uncertain findings and gap records, with digest-bound review rows. Confirming evidence must be read or reproduced, not inferred from the original author's confidence.

Every critic and worker that drives a browser uses its **own** browser session (for example its own `PWC_SESSION` or profile directory) with a network guard limited to the target's origins; shared sessions mix focus, storage and navigation state between agents and invalidate independence. State session name and allowed origins in the brief.

Give critics the allowed object `kind` values (view, flow, component, dialog, menu, notification, configuration, integration) so their inventory proposals map without translation.

A final fresh critic checks the closed ledger, raw evidence, unprocessed work, refutations and unsent issues. A new supported gap reopens the loop. No majority vote or multiple AI opinions replace primary evidence.

## Safe runtime testing

The bundled scripts do not execute repository code. For actual app testing:

- Review build/test/start commands and dependencies first. Prefer an existing reproducible build. Do not run install hooks from unknown code on the host.
- For the user’s designated, identified product, inspect startup/build commands and dependencies and assess the action before choosing a runner. Authorized ordinary native/browser tests may run on the current device with a disposable profile/workspace, synthetic data, no personal credentials and controlled network destinations. An installed trusted build need not be rebuilt in a remote lab. Verify native storage paths before writes/reset and preserve unrelated data. Unknown, suspicious or unreviewed executable code still requires containment.
- Run such untrusted code only in an available sandbox/container/VM with explicit read-only source mount, a throwaway writable workspace/profile, no inherited credentials, no host socket, and outbound network denied by default. A copied directory, Python timeout or browser profile alone is **not a sandbox**. If no adequate boundary is available for that code, try other available authorized runners and keep only the affected method blocked; continue independent runtime and source methods.
- For a small fixture authored and reviewed by the auditor, a dedicated local browser profile may suffice: no project build/import/install hooks, credentials, external resources or target-controlled scripts; local services bind only to loopback. This validates the fixture's narrow behavior, not the real application's runtime. A browser profile is data separation, not containment of untrusted code.
- Existing-runtime observation is a separate lane: read-only screenshots/accessibility-tree inspection of an already running, identified build may proceed only with an explicitly designated test profile and synthetic data. Do not launch the target, invoke controls, change settings or reuse personal documents in this lane. Record build provenance; unknown build-to-source correspondence limits conclusions. Accessibility-tree reading does not enable screen-reader testing. Interactive tests or a new build use the risk assessment above; an isolated account alone does not contain untrusted code.
- Native isolation covers the user's real home directory and the OS service manager. A sandbox with network denial and separate app config/state is not enough while the app sees the real `HOME`: an installer path or `service_install`-style action can register a LaunchAgent/systemd unit/scheduled task under a production label. Run native tests that may install, register or launch services only in a throwaway user account or VM, or with a demonstrably redirected `HOME` and blocked `launchctl`/`systemctl --user`/`schtasks`. Before and after the run, list user services and login items and record the diff as evidence; remove anything the test created.
- Set a wall-clock deadline per command (initially 60 seconds for probes, explicit bounded allowance for builds), maximum output/artifact size and container CPU/memory/process limits where available. Record actual limits. Kill the owned process group/container on timeout; a surviving child process means cleanup is incomplete. Do not kill by broad process name.
- Record missing tools or unsupported isolation as blocked units with the next executable step. No empty log, timed-out test or missing requested tool is a pass. Screen-reader tests outside the default scope follow the evidenced exclusions in M6, not missing-tool jobs.
- Keep raw screenshots, traces and logs local and inspect for personal information and tokens before any publication. Use minimal issue excerpts and local evidence IDs. Approval to audit does not authorize arbitrary external uploads or executing hostile code with personal credentials.

## Capability failure and remote handoff

Use the capability checklist in platform-compatibility.md before selecting a runtime lane. If a containment probe fails, do not run code requiring that containment outside it. Re-evaluate other local tools, trusted installed builds, available VMs and authorized remote hosts before declaring that method blocked. Continue individually applicable source and runtime methods. Record the exact failed probe, exit status and missing control, with a concrete next step such as an approved test VM.

For an authorized remote/testlab run, prepare a bounded job packet: immutable source manifest and build hash, assigned unit/variant IDs, exact steps and expected outcomes, synthetic test data/profile, permitted commands, required isolation and resource limits, artifact size limits, owner and deadline. Transfer only the reviewed necessary files to the approved destination; no credentials or personal profiles. The receiving operator records actual controls and tool versions before execution, then returns command/step logs, exit statuses, timestamps, environment/build identity, raw artifacts and a SHA-256 manifest. A remote hostname or VM label alone is not proof of isolation.

Import returned files into a new local evidence namespace only after checking the packet/run identity, path safety, sizes and hashes. Preserve remote actor, artifact origin and collection steps; do not relabel imported observations as local execution or coordinator observations. A checksum establishes integrity, not truth: a fresh reviewer must inspect primary artifacts and the build/source link. Mismatched baselines, missing provenance or incomplete cleanup leave affected units open. Only the coordinator applies validated fragments through the supported transaction API; remote workers never overwrite the parent ledger. No remote runner or transport is bundled or assumed tested.

## Follow-up after separately authorized corrections

This skill creates issues, not implementations. A later fix validation starts a new baseline, links original issue/finding IDs and repeats the original failure plus an adjacent/alternative path. Include restart and existing profiles for persistence, and keyboard/adaptive checks and screen-reader checks only when explicitly requested for shared component changes. Recommend closure only with new independent evidence. Do not automatically close tracker issues during this audit workflow.
