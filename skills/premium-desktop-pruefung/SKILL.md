---
name: premium-desktop-pruefung
description: "Deep UI/UX audit of an existing desktop app against a premium desktop standard (onboarding, settings, a11y, native input), then fix, verify and retest with a capped subagent team. Use for 'Premium-Desktop-Prüfung', 'Desktop-App tief prüfen'."
argument-hint: "[app or window scope] [optional focus]"
disable-model-invocation: true
---

# Premium Desktop Audit and Fix

Audit and improve the desktop app in the current repository: $ARGUMENTS

Without an argument, take the whole app. A focus (e.g. `Einstellungen und Onboarding`) orders the work but never removes catalog rules — unmapped rules still need an evidenced exclusion.

Deliver a checked and improved app in the target repository. Use the product the way its users do: a verdict on visual quality needs the rendered UI, a verdict on behaviour needs an executed action.

You are the **coordinator**. You plan, dispatch subagents, merge their results into the ledger and drive the gates. You do not grade your own work: critique, verification, retest and final critique always run in fresh subagents.

## 1. Load the standard

Read in full before planning:

- `${CLAUDE_SKILL_DIR}/references/Premium-Desktop-Design.md` — the design standard. It is written in German on purpose: it is the quality bar, not documentation to translate. Its product examples are examples; its embedded rebuild prompt is background, the job here is the existing product.
- `${CLAUDE_SKILL_DIR}/references/methoden.md` — the mandatory rule catalog (German payload, 46 rule IDs such as `ON-03`, `SET-07`). Every rule must end up mapped to units or to an evidenced exclusion.
- `${CLAUDE_SKILL_DIR}/references/protocol.md` — ledger schema, statuses, fragment format and commands.

If the project has its own design standard, it wins where the two disagree; the bundled one fills the gaps.

## 2. Baseline and run directory

1. Work inside the existing dev workflow. Record revision, local changes, start command, platform, test profile and reproducible sample data. Use isolated profiles for first run, migration and reset — never the user's real profile.
2. Create the run directory outside the product sources (a gitignored artifact folder or a sibling directory) and initialise it:

   ```sh
   A="${CLAUDE_SKILL_DIR}/scripts/audit.py"; RUN=<run-dir>
   python3 "$A" init "$RUN"
   ```

3. **Build once** for the baseline revision yourself and note the launch command. Subagents reuse this build; they never start their own build.

## 3. Load budget (hard rules)

The audit is deep, the machine is shared. These limits hold for the whole run:

| Resource | Limit |
| --- | --- |
| Parallel subagents | `python3 "$A" capacity` before every dispatch round → `slots=N`, never above **3** |
| GUI / running app | exactly **one** subagent drives the app at a time (one screen, one keyboard focus) |
| Builds, test suites, app instances | **one** at a time; the coordinator builds, workers reuse the build |
| Code changes in the target repo | **one** implementer at a time (no parallel edits on the same tree) |
| Work package | one subagent ≈ one coherent slice, under 30 minutes, at most ~12 units |

Consequences for scheduling:

- Split each wave into **static packages** (code inventory, settings schema, persistence, design tokens, `inspection` units) and **one runtime package** (all `runtime` units of the wave). Static packages run in parallel up to `slots-1`; the runtime package takes the remaining slot and runs alone on the GUI.
- If `capacity` reports `slots=1`, run packages strictly one after another — the plan stays the same, it only takes more rounds.
- **Load limits never shrink scope.** Units that do not fit a round go into the next round or wave; the ledger, not the agent count, decides when the audit is done.
- Launch parallel subagents in one message with `run_in_background: true`, then wait for their notifications; do not poll and do not start a new round while one is running.
- Pick the lightest fitting agent: `Explore` for read-only code scouting, `general-purpose` for audit workers, critics, verifiers and retesters, the project's UI agent (e.g. `ui-builder`) for visible fixes and its code agent (e.g. `umsetzer`) for logic fixes — fall back to `general-purpose` if those do not exist.
- Before any subagent drives the mouse, keyboard or screen, say so to the user. Prefer the project's own UI automation (accessibility APIs, Playwright for web views/Electron, existing UI tests) over raw pointer automation.

## 4. Profile and inventory

Write an evidenced product profile into `product`: who does which task, how often, with which input devices, on which supported systems. Back audience, promise and platforms with project sources, the running product or real user feedback; mark assumptions. Name a concrete first success, a routine task and a demanding or error-prone path. An editor, a finance overview, a tray tool and a video call need different work surfaces.

Collect four views independently — one static package each for `code` and `platform` (parallel), `product` and `runtime` inside the single runtime package — then reconcile differences:

| View | Survey | Often missed |
| --- | --- | --- |
| Product paths (`product`) | Actually play fresh install, return, quick repeat, abort and resume | alternative entry, update with existing data, declined permission |
| Implementation (`code`) | Trace entry points, windows, routes, dialogs, menus, command registry, settings schema, persistence, design tokens | second window, platform branch, setting without a visible entry |
| Running UI and input (`runtime`) | Main and secondary windows with realistic data, mouse, keyboard, accessibility API | focus after close, resize, context menu, monitor change, screen-reader value |
| Platform, data and states (`platform`) | OS integration and platform variants; selection, permissions, devices, theme, language, data volume, scope and errors along the same task | inherited value, disconnected device, unsaved input, stale selection |

Record links explicitly (wizard → stored key → settings row → effective behaviour after restart). Map every inventory object to its relevant rules and every rule to concrete units or an evidenced exclusion. A unit is a checkable combination of object, rule, variant and acceptance criterion. Identical components may share evidence only when their relevant properties really match — name covered and diverging variants. A supported platform that cannot be tested here stays visibly open; an environment gap is never a reason to exclude.

## 5. Audit waves

Plan capacity for all phases before wave 1: waves, critiques, verification, fixes, retests and final critique. Prioritise by task failure, frequency, reach and evidence gap. Stop exploring a well-covered variant while a mandatory one is still empty.

Per wave:

1. Cut **disjoint** packages (no unit in two packages). Give each subagent only: product profile, its unit IDs with object/rule/variant/expected, the relevant catalog rows, the baseline (revision, build/launch command, profile), source paths and its agent ID.
2. Brief every worker to return per unit: expected, actual, steps, environment, countercheck, evidence path and remaining question — passes included. It writes `parts/<agent-id>.json` (fragment format in `protocol.md`) and evidence under `evidence/<agent-id>/`, never `audit.json`, and answers with a summary of at most ~10 lines. Unknown expectations or unreachable environments stay `open` with `missing` and `next`.
3. Merge: `python3 "$A" merge "$RUN" "$RUN"/parts/<files>`; investigate every unexpected `replaced:` line.
4. **After every wave**, dispatch one fresh critic (`critic-w<N>`, its own context, alone — it competes with no one for the GUI unless it must reproduce something). Give it profile, inventory, catalog, ledger path and raw evidence. It searches user paths and code on its own for missing objects, dependencies, unjustified exclusions and premature passes, and re-checks passes and exclusions against raw evidence. Record the wave (`units, critic, critique, evidence, gaps`); every justified gap becomes a new or reopened unit in a later wave. Cross-findings outside the original view count too.
5. Group candidates with a shared cause into one finding; keep all affected units and original evidence.

A failing `check` mid-run is normal. Start on confirmed findings while other units are still open.

## 6. Verify

One fresh verifier per finding (`verifier-<F-ID>`). Verifiers that only need code and evidence may run in parallel within `slots`; any that must reproduce in the app queue for the single GUI slot. Give the verifier the reproducible baseline, raw evidence and the target rule. It tests alternative explanations (real focus vs. selection, project override vs. save failure, empty test profile vs. lost data) and decides `confirmed`, `refuted` or `open` (with missing evidence and the next reproducible step).

## 7. Fix

1. For each confirmed cause state the user impact, the intended improvement and an observable retest. Fix all confirmed deviations in scope, in priority order, at the shared cause when it spans several views.
2. Keep the existing design system and data models. Show for this app type why the fix helps — a tray dictation tool may need an accessible menu entry rather than a sidebar; data-heavy apps need overview and comparability, editors a coherent work surface. Leave native-target deviations open when fixing them needs a separate migration outside the job.
3. New or substantially rebuilt onboarding: compare two to three direct competitors as the standard describes. Visual redesign: hand real screenshots and product context to a separate design context (Codex CLI if installed, otherwise a fresh UI subagent with image input). Keep own runtime observation, external images and hypotheses apart; document mandatory parts that could not be done.
4. One implementer at a time works through the regular entry points, preserves user data, stored settings, familiar commands and platform conventions, and leaves a diff plus matching regression tests. Then the coordinator rebuilds once.
5. A fresh retester (`retester-<F-ID>`, never the implementer) repeats the original failing path on the changed build with identical data, window size, theme and state, and runs at least one adjacent or alternative path — for persistence also restart and an existing profile. A screenshot can prove layout; focus, persistence, permissions and latency need an input/output sequence or a measurement. Changed or newly affected units go back into wave planning.

## 8. Close

1. Dispatch a separate, fresh final critic (`critic-final`) on the latest state after all changes. Every new justified gap reopens the loop (another wave, another final critic).
2. Fill all `final` fields, then `python3 "$A" digest "$RUN"` and store the result as `final.snapshot`.
3. `python3 "$A" check "$RUN"` and `python3 "$A" report "$RUN" > "$RUN/report.md"` from exactly that state.
4. Report to the user even when incomplete: affected units, cause and the concrete next step; implemented changes, runtime evidence, refutations, exclusions and remaining gaps. Write ledger prose and the report in the language of the user's request.

Where no independent subagent run is possible, continue the reachable analysis, fixes and tests, record the pending mandatory review and close as incomplete. A passing `check` certifies formal consistency only; content verdicts rest on the reviewers and their raw evidence.
