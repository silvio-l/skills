# Platform compatibility and capability contract

Checked on 2026-11-18. Compatibility means a common instruction/data/tool bundle with capability detection; it does not imply that every host supplies browser automation, native accessibility, isolated execution or subagents.

## Observed platform support

| Surface | Claude Code | OpenAI Codex |
| --- | --- | --- |
| Common package | SKILL.md plus referenced files and executable scripts | Same |
| Core metadata | name and description; Claude extensions are optional | name and description; optional agents/openai.yaml |
| Project discovery | .claude/skills/<name>/SKILL.md | .agents/skills/<name>/SKILL.md |
| Personal discovery | ~/.claude/skills/<name>/SKILL.md | ~/.agents/skills/<name>/SKILL.md |
| Invocation | Explicit /premium-desktop-pruefung | Explicit skill selection / $premium-desktop-pruefung as supported by the host |
| Delegation | Available Agent tool and allowed configured/built-in type | Available subagent tools; agent configuration and host policy apply |
| Execution dependency | Python interpreter for bundled tools; optional audited application tooling | Same |

Sources: [Claude skills](https://code.claude.com/docs/en/skills), [Codex skills](https://learn.chatgpt.com/docs/build-skills). The latter is the current destination of the official developers.openai.com/codex/skills documentation. Both describe progressive loading; supporting modules should load only when needed. Repository-local directories here are installation destinations, not instructions to overwrite this source repository.

Claude-specific disable-model-invocation and argument-hint metadata do not define Codex invocation behavior. The shared workflow must not require CLAUDE_SKILL_DIR substitution or $ARGUMENTS expansion: resolve files from the installed SKILL.md location and use the user's actual request. Project-local policy can further restrict discovery.

## Agent mapping

The skill's coordinator, inventory reviewer, investigator and verifier are responsibilities, not executable tool names. At run start, record which delegation tool and agent types are actually exposed. Give each worker a bounded packet with unit IDs, raw-source locations, evidence paths, expected output and write permissions. The coordinator remains the sole shared-state writer. Reviewer context should exclude the investigator's persuasive narrative and include primary evidence.

Claude renamed Task to Agent in version 2.1.63; current documentation supports nested agents subject to tool permissions and depth limits. A fresh non-fork agent has an isolated context; a fork inherits conversation. Do not select a fork when claiming an independent fresh review. Installed agent names and allowed tools are configurable. [Claude subagents](https://code.claude.com/docs/en/sub-agents).

Current Codex documentation permits delegation after a direct request or applicable project/skill instruction, and agents.enabled can disable it. Default model inheritance does not establish reviewer independence. Record the actual reviewer identity and access to raw evidence. Tool names exposed by one host must not be assumed in another. [Codex subagents](https://learn.chatgpt.com/docs/agent-configuration/subagents).

The portable workflow needs no nested agents. If delegation is absent or denied, use a distinct counter-review pass, reopen primary sources, and record that the same model/context performed both roles. This is weaker evidence and cannot be presented as independent-agent validation.

## Safe execution and missing capabilities

### Native desktop adapter

Inspect exposed Computer Use, Agent Desktop / Desktop Agent and browser capabilities before selecting an adapter. Use the `agent-desktop` skill when available and suitable, or an existing equivalent host capability under its own instructions. For agent-desktop, load the installed executable's `desktop` and `platform` guides, record its version and permissions, and verify a real accessibility snapshot on each host. For other adapters, probe the actual observation and interaction capabilities needed by the check. Keep snapshot-qualified refs on the host where they were generated. SSH connectivity and a successful `status` command alone do not establish GUI access. Browser-only checks use the configured browser adapter when suitable.

### Select evidence with minimal token cost

Choose per check, not once for the whole audit. Among methods that can establish the required evidence, prefer the lowest expected token cost, including setup, output volume and likely retries. Reuse suitable existing capabilities before installing another tool; respect explicit user choices and configured tool restrictions.

- For semantics, values and state transitions, prefer focused DOM/accessibility queries, stable element refs and concise structured results. Filter to the relevant window, subtree or fields instead of repeatedly dumping the full tree or page.
- For appearance, inspect actual rendered images: layout, clipping, overlap, typography, visible focus, visual hierarchy and image/canvas content cannot be established from source or accessibility trees alone. Use targeted screenshots or crops at sufficient resolution; retain enough surrounding context to judge relationships. Keep original evidence on disk and reference it rather than repeatedly loading identical images.
- Use screenshot-based Computer Use when structured controls are absent or insufficient, including native dialogs and canvas surfaces. If an adapter can act through stable refs and supply images, combine those capabilities rather than forcing every action through pixel coordinates.
- Reuse observations only while the relevant build, state and environment remain unchanged. Capture new evidence after relevant changes; inspect full-window or full-page context when the criterion requires it. Token savings never justify skipped variants, missing visual checks or weaker evidence presented as a pass.

Record the selected adapter and its evidence limits in runtime evidence. Add a brief reason when switching methods or when the cheaper available method cannot answer the check; no per-action accounting is required.

Observed adapter smoke checks on specific hosts are recorded in the [validation record](validation.md#host-capability-observations--2026-11-18); they are not capability evidence for the current run.

The optional desktop VM facility does not by itself prove the filesystem, network or credential isolation required below. Verify those boundaries independently before executing target-controlled code.

### Adapter pitfalls observed in audits

- **Tool-name collisions.** A short name may be an unrelated system binary: on macOS `cu` is the UUCP "call up" command, not Computer Use. Resolve the adapter by its documented entry point and version output, never by `which <short name>` alone.
- **Frontmost app.** Headed key presses go to the frontmost app, which may be the login window, another browser or a notification. Verify the frontmost app and window immediately before each key press.
- **Keys agent-desktop cannot send as typed.** Escape needs an unscoped `--headed press` (a ref-scoped press does not reach the window); `?` and other shifted characters on a German layout are not sent reliably through `type`. Use the key name or a different path and record the limitation instead of reporting a missing shortcut.
- **Snapshots for focus checks.** `snapshot -i` (interactive elements only) omits focused headings and static elements; check focus with a full snapshot.
- **Private data in captures.** Menu-bar snapshots (Apple menu recent items), `list-windows` (foreign window titles) and screenshots can show personal data; AutoFill one-time codes have appeared in a screenshot. Filter snapshots to the target app and window, crop screenshots to the window, and redact before evidence leaves the machine.

### Host-first capability decision

At the start of **each run**, inspect the current OS/session, exposed tools, installed identified app, available build commands, browser adapter, native desktop adapter and permissions, writable disposable profiles, local runners/VMs and already authorized remote devices. Historical failures are leads to recheck, not current capability evidence. A missing Docker or failed sandbox-exec probe is specific to that runner; neither proves that the current host cannot run authorized product tests.

Record candidate path, supported methods, build provenance, data/write/network controls, probe result, reason for selection/rejection and fallback in an evidence document linked from `profile.runtime`. Prefer the current host when it can test the actual platform with appropriate controls. A browser session can test web behavior while native setup proceeds; a remote Linux browser cannot certify macOS/Windows storage or OS integration. Avoid building infrastructure when an identified installed build can answer the question. Try suitable available alternatives before asking the user for new infrastructure.

Choose controls proportionate to the code and action using agents.md. A trusted, identified product under the user's audit instruction can use local disposable test data after command/dependency review; unknown executable code needs demonstrated containment. Do not infer trust from a filename or skip review because a build exists. For containment-dependent execution, verify actual boundaries:

For a candidate runner, use a small auditor-authored probe with an explicit deadline: an allowed scratch write must succeed, a write to a disposable sentinel outside the permitted area must fail, inherited credentials must be absent, and prohibited network access must be denied. Test denial only against a controlled local listener or approved test endpoint, never a production service. Inspect the effective filesystem/network/process/resource policy as well; one failed connection cannot prove network isolation. Record output and exit status, remove only owned probe artifacts, and stop on a failed/crashed probe. Do not invent a universal sandbox-exec profile or claim support from its presence.

| Available lane | Minimum condition | What remains unproven |
| --- | --- | --- |
| Source inspection | Read-only files at recorded baseline; no repository commands/imports | Rendered appearance and runtime behavior |
| Existing-runtime observation | Identified already running build; explicitly designated synthetic test profile; read-only screenshot/accessibility inspection | Untested interactions; unknown source/build correspondence |
| Auditor-authored fixture | Reviewed self-contained code, dedicated profile, no target scripts/hooks or external dependencies | Real application behavior; untrusted-code containment |
| Actual target build/test/interaction | Reviewed product/commands and appropriate local controls; demonstrated sandbox/container/VM for untrusted code; throwaway data, no personal credentials, explicit bounds | Only executed scenarios gain evidence |
| Remote/testlab execution | Authorized destination and operator demonstrate the same controls; provenance-preserving job/result packet | Unreturned, mismatched or unverifiable evidence |

These lanes are choices per method, not whole-audit verdicts. Source analysis can continue while rendering is blocked. See agents.md for packet fields and import checks. Remote execution, native sandbox profiles and these probe steps are operational instructions, not tools claimed to have been tested in this delivery.

A worktree separates edits; it is not a network/process/resource sandbox. A read-only tool policy alone does not establish all OS-level restrictions. Before builds, tests or application startup, determine the controls required for the specific action and code. Missing required controls block that execution path, not every possible path; continue testing with suitable alternatives.

Use synthetic data and isolated profiles. Do not expose credentials through logs, issue attachments or screenshots. Browser/native tools are optional adapters discovered at runtime. Their absence leaves requested methods open, not passed. Screen-reader execution is outside the default scope and is enabled only by an explicit user request; follow M6 for scope exclusions and criterion-level evidence limits. A contrast calculator or static semantic check cannot replace a rendered/browser or assistive-technology observation.

Issue transport is also an optional capability. Prepare concrete reviewable issue payloads from validated records; publish only through the authorized target's supported tracker workflow and record returned identities. An unavailable tracker must remain a documented delivery gap; a local issue draft is not a remotely created issue. Never infer permission to edit the audited product from permission to audit or create issues.

