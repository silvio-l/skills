---
name: ratchet-up
description: "Context-safe agentic loop that ratchets a feature's issues forward — discovers ready issues, respects blocked-by deps, dispatches workers and read-only reviewers, gates format/analyze, commits approved. Usage: /ratchet-up <feature-path> [max-iter]"
disable-model-invocation: true
metadata:
  argument-hint: "<feature-path> [max-iter]"
---

# Ratchet-Up — Iterative Issue Loop

You are the **orchestrator**. You discover, schedule, dispatch, gate, review, commit, and summarize. You do **not** implement feature code yourself.

A ratchet clicks one tooth at a time and never slips backward. Every issue that reaches `APPROVED:` clicks the ratchet one step forward; nothing can unwind unless the user explicitly says so.

Each issue is handled by a clean-context worker sub-agent. Each implementation is checked by a dedicated read-only reviewer sub-agent. The orchestrator keeps only compact state in active context — everything else lives in the per-feature dump zone at `<feature>/.ratchet-up/`.

The skill is **project-agnostic** and works on the **active branch** (typically `dev`) — no new branches, no worktrees. Merging `dev → main` and tagging stays a user-driven activity.

## Where things live

| Concern | File |
|---|---|
| Step-by-step state machine (§1–§17, incl. roadmap hooks §3.5 + §15.5, batched visual pass §15.4) | [algorithm.md](algorithm.md) |
| Project detection, gate, commit, quick-path | [gates.md](gates.md) |
| Issue contract, synonyms, status transitions | [formats.md](formats.md) |
| Worker prompt template | [worker.md](worker.md) |
| Reviewer prompt template | [reviewer.md](reviewer.md) |
| Conditional visual UI verification (frontend diffs) | [visual-review.md](visual-review.md) |
| Planner prompt template | [planner.md](planner.md) |
| Cheap Evidence-block pre-check | [scripts/check-evidence.sh](scripts/check-evidence.sh) |

Read the file you need when you need it. SKILL.md is the always-on layer — keep it minimal.

## Core Principles

- **Code changed ≠ task complete.** Completion requires acceptance criteria met, gates passing, evidence recorded, and reviewer approval — never a worker's confidence alone.
- Keep the orchestrator in the Smart Zone — no full diffs, no full logs, no cumulative test output in active context.
- Never load full issue contents into orchestrator context — pass them only to the assigned worker/reviewer.
- Treat every issue as a small, independently verifiable slice.
- Gate format/analyze **before** the reviewer — fail fast, save a sub-agent.
- For **frontend diffs only** (UI surfaces touched, per `gates.md` §2.5), the reviewer additionally verifies the rendered result against the plan's declared visual expectations. Three tiers, cheapest first: (1) screenshot-free **code-level** checks incl. sibling-component comparison — always; (2) **cheap capture** (running session, goldens, installed browser) per-issue in the reviewer spawn; (3) **heavy capture** (simulator boot / full build / discovered visual-QA command) is *never* run per-issue — it is batched into **one** pass at feature-end (`algorithm.md` §15.4). Backend diffs pay nothing; when no capture path exists the step skips with a suggestion, never a blocker. See `visual-review.md`.
- Skip the gate for doc-only diffs (quick-path) — don't burn `flutter analyze` on a CHANGELOG bump.
- Run the cheap Evidence pre-check **before** the gate — catches the most common worker miss in milliseconds.
- Commit only after the reviewer approves; one commit per issue.
- On rework, **feed the reviewer's blockers back to the next worker** — never let a worker re-implement blind.
- Spawn read-only sub-agents (reviewer, planner) with `subagent_type: Explore`; only the worker needs `general-purpose`.
- **Always set `model:` explicitly on every spawn** — never let a sub-agent inherit the orchestrator's model (sub-agent spend is the biggest cost driver). Default `claude-sonnet-4-6` for worker, reviewer, and planner; escalate a single spawn to `claude-opus-4-8` only for an architecturally hard issue.
- Stop and escalate to `needs-human` instead of improvising on scope, dependency, or assumption drift.
- Never push. Never tag. Never merge to `main`. Never use hook-bypass flags.
- Never delete `<feature_path>` unless objectively verified done — or explicitly confirmed by the user.
- One issue at a time. No parallel workers. Predictable beats fast.

## Definition of Done (single source of truth)

A single issue is **DONE** only when **all** of the following hold. Worker self-check, gate, and reviewer all reference this list verbatim — no duplicates anywhere else in the skill.

1. The behaviour described in the issue's intent section is implemented.
2. **Every** acceptance criterion has at least one passing test that exercises observable behaviour through the public interface — **unless** the issue is explicitly a release/process issue with no production code.
3. The change is minimal — no opportunistic refactors, no unrelated lint fixes, no scope expansion.
4. Existing architecture and naming conventions are respected.
5. Project rules from `CLAUDE.md` hold (no `!` operator where forbidden, localisation rules, design tokens, etc.).
6. Required gate commands pass (format clean, analyzer 0 issues, tests green) — or the diff qualified for the quick-path and that is logged.
7. Error handling is intentional for every new user-triggered action.
8. No secrets, PII, debug prints, commented-out code, or hook bypasses (`--no-verify`, `--no-gpg-sign`) in the diff.
9. The issue file contains a worker-supplied **Evidence block** (see `worker.md` § Mandatory Evidence block).
10. The reviewer found no blockers and explicitly returned `APPROVED:`.
11. Exactly one commit produced (or `no changes` recorded if the issue is documentation-only and that is explicitly the expected outcome).
12. **Frontend issues only** — if the diff touched a UI surface **and** a visual expectation exists (declared in the issue, or set by precedent in a sibling component, or in the project design language), the visual verification confirmed the rendered result matches it — per-issue for cheap/code-level checks, and via the batched §15.4 pass for heavy capture paths. Does not apply to backend issues, to UI with no expectation source, or when no capture path exists at all (then it is a recorded suggestion, not a gate). A batched-pass visual blocker reopens the affected issue (it is not "done").

A task that fails any of these is **not done**, regardless of how the worker self-rates the result.

## Configuration

All tunables read from `<feature_path>/.ratchet-up/config.yaml`. Missing keys fall back to defaults. Example:

```yaml
# Gate commands (see gates.md §1; auto-detected if absent)
format: "dart format ."
analyze: "flutter analyze --fatal-infos --fatal-warnings"
test: "flutter test"

# Loop tunables
rework_limit: 2          # max rework rounds per issue (gate + reviewer + evidence-precheck combined)
planner_threshold: 5     # spawn planner when len(eligible) > this (or fan-out detected, see algorithm.md §6)
cycles_cap: 20           # floor for MAX_CYCLES_PER_ITER = max(cycles_cap, eligible*3)
max_iter: 3              # max full passes over the issue list (CLI arg overrides)

# Hard-Deletion-Guard
feature_marker: "/.scratch/"   # feature_path must contain this substring
```

## Quick reference — what to do when

| Trigger | Action |
|---|---|
| User runs `/ratchet-up <feature>` | Start at `algorithm.md` §1 |
| `.scratch/roadmap.md` exists at repo root | `algorithm.md` §3.5: read/ask for `<feature>/.roadmap-sprint`, flip linked Sprint `todo → in-progress` |
| Choosing gate commands | `gates.md` §1 (override → CLAUDE.md → auto-detect) |
| Worker returned `DONE:` | Run `scripts/check-evidence.sh`, then gate (`gates.md` §3 — quick-path if diff is doc-only) |
| Diff touches a UI surface | Classify `{{UI_DIFF}}` (`gates.md` §2.5); reviewer runs visual verification (`visual-review.md`, tiers 1–2) |
| All issues `done` and any UI was touched | `algorithm.md` §15.4: one batched visual pass (tier 3, heavy capture) before §15.5 |
| Reviewer returned `REWORK:` | `persist_rework_feedback` (`algorithm.md` §9), then re-queue |
| Reviewer output malformed | Retry **once**, then escalate to `needs-human` (`algorithm.md` §7) |
| All issues `done` | Verify (`algorithm.md` §15) → roadmap status to `done` (§15.5, if linked) → summary (§16) → cleanup (§17) |
| Issue under-specified | Issue quality gate sets `needs-info` (`algorithm.md` §5, format rules in `formats.md`) |

## Roadmap integration (optional)

If the repo has a `.scratch/roadmap.md` produced by [`to-roadmap`](../to-roadmap/SKILL.md), `ratchet-up` will:

- on the first run for a given feature directory, ask once which Sprint-ID this feature implements (or `none`) and persist the answer in `<feature>/.roadmap-sprint`,
- on every run, flip the linked Sprint from `todo` to `in-progress` at the start (§3.5),
- on a successful run that ends with **all** issues `done`, flip the Sprint to `done` at the end (§15.5).

If the roadmap file is absent, the marker is `none`, or the marker references an unknown Sprint-ID, the loop runs unchanged and prints `(no link)` in the summary. The link is feature-local — different features in the same repo can target different Sprints, and re-running `ratchet-up` on an already-`done` Sprint logs a warning but does not auto-flip backward.
