# Algorithm — Orchestrator State Machine

The full step-by-step skill behaviour. Read this once at the start of each `/ratchet-up` invocation. SKILL.md is the single source of truth for the Definition of Done, principles, and tunables; this file is the executable logic.

Glossary:

- **DoD** — Definition of Done, defined in SKILL.md.
- **gate** — format + analyze run between worker and reviewer; see `gates.md`.
- **quick-path** — gate skipped because diff is doc-only; see `gates.md`.
- **dump zone** — `<feature>/.ratchet-up/` — all operational state lives here.
- **tunables** — `rework_limit`, `planner_threshold`, `cycles_cap`, `max_iter`, `feature_marker`; see SKILL.md `## Configuration`.

---

## Script convention (since 2026-05-20)

Future implementation work in Track B3 of `.scratch/architecture-deepenings/` replaces several prose-form passages in this document with calls to dedicated scripts under `skills/ratchet-up/scripts/`:

- `guard-feature-path.sh` — replaces the §1 / §17 Hard-Deletion-Guard prose.
- `detect-project.sh` — replaces `gates.md` §1 Project Type Detection prose.
- `classify-diff.sh` — replaces `gates.md` §2 Quick-Path Heuristic prose.
- `verify-final.sh` — replaces §15 Objective Final Verification prose.

**Hard Requirement.** These scripts are mandatory. If one is missing or not executable at runtime, the orchestrator sets the current issue to `Status: needs-human` and logs exactly:

```text
✗ ratchet-up script missing or non-executable: scripts/<name>.sh — run `npx skills@latest update silvio-l/skills`
```

No soft fallback to the prose form at runtime. The prose form for each section is removed once the corresponding script lands, so there is exactly one source of truth.

Until the B3 scripts ship, the prose form in §1, §15 and in `gates.md` §1 / §2 remains authoritative. The Hard Requirement applies from the moment the first script lands.

Rationale: single-user repo, frequent updates via `npx skills@latest update -g`, drift between prose and script is the bigger risk than a transient missing-script eskalation.

---

## §1 — Parse Arguments

Extract:

- `feature_path` — required, path to the feature directory (typically `.scratch/<feature>/`).
- `max_iter` — optional, default from config (fallback `3`). One pass = one walk over currently-eligible issues.

Normalise `feature_path` (strip trailing slash; resolve relative to repo root if needed).

**Hard-Deletion-Guard preconditions** (sanity-checked here and again before any `rm -rf`):

- `feature_path` contains the configured marker (default `/.scratch/`, see `feature_marker` tunable).
- `feature_path` is not empty, `.`, or `/`.
- `feature_path` is not the repository root.
- `feature_path` exists and is a directory.
- `<feature_path>/issues/` exists and is a directory.

If any check fails: stop with a clear error.

---

## §2 — Prepare Dump Zone

All operational state lives inside `<feature_path>/.ratchet-up/`. Nothing is written outside the feature directory.

```bash
mkdir -p "$feature_path/.ratchet-up/rework"
```

| File | Purpose |
|---|---|
| `run-log.md` | append-only timeline |
| `queue.md` | current iteration's queue snapshot |
| `issue-status.md` | last-known status per issue |
| `rework-counts.md` | per-issue rework counter |
| `context-summary.md` | rewritten after every cycle (§12) |
| `deviations.md` | one-liners for `needs-info` / `needs-human` |
| `test-notes.md` | raw gate failure output |
| `config-resolved.md` | gate commands chosen by `gates.md` §1 |
| `rework/<basename>.md` | transient: reviewer blockers → next worker |

**Rule:** raw outputs, long logs, analyzer/test failure dumps go into these files — **never** into orchestrator context. Only one-line outcomes flow back to the orchestrator.

---

## §3 — Preflight

```bash
git status --short
git rev-parse --abbrev-ref HEAD
git rev-parse --short HEAD
```

Allowed pre-existing changes:

- files under `<feature_path>/`
- files under `<feature_path>/.ratchet-up/`

If the working tree contains unrelated changes, stop and report — do not auto-stash. Record baseline branch + SHA in `run-log.md`. Warn (don't stop) if the branch is `main` / `master` — the project convention typically wants work on `dev`.

---

## §3.5 — Roadmap Linkage (optional, runs only when roadmap exists)

If `.scratch/roadmap.md` does **not** exist at the repo root, skip this section entirely — no questions, no logs.

If it exists:

1. **Read marker.** Look for `<feature_path>/.roadmap-sprint`. If present and non-empty, its first line is either a Sprint-ID (`sprint-\d{2}-[a-z0-9-]+`) or the literal string `none` (= user explicitly opted out of linking this feature).
2. **Ask once if missing.** If the marker file is absent, extract all Sprint-IDs from the roadmap:

   ```bash
   grep -E '^\*\*Sprint-ID:\*\* sprint-' .scratch/roadmap.md
   ```

   Show the user the list and ask which Sprint this feature implements. Accept also `none` / `skip` if the feature is not tied to the roadmap. Persist the answer to `<feature_path>/.roadmap-sprint` (one line, exact Sprint-ID or the literal `none`). Ask **exactly once** — never again on later invocations.
3. **Skip if `none`.** If the marker says `none`, skip the rest of §3.5 silently.
4. **Sync status to `in-progress` (idempotent).** Read the current `**Status:**` line of the matching Sprint block in `.scratch/roadmap.md`. Apply the table:

   | Current | Action |
   |---|---|
   | `todo` | Edit the line to `**Status:** in-progress`. Log `roadmap: <sprint-id> todo → in-progress` to `run-log.md`. |
   | `in-progress` | No-op. |
   | `done` | No-op, but log a warning: `roadmap: <sprint-id> already done — ratchet-up continuing anyway`. The user may be reopening a finished sprint; do not auto-flip back. |

   Use the `Edit` tool with the unique two-line anchor — Sprint-IDs are guaranteed unique in a roadmap file, so the anchor disambiguates:

   ```text
   old_string:
   **Sprint-ID:** <sprint-id>

   **Status:** todo

   new_string:
   **Sprint-ID:** <sprint-id>

   **Status:** in-progress
   ```

5. **Validation guards:** if the Sprint-ID from the marker is not found in the roadmap, do **not** invent a new block. Log `roadmap: marker references unknown sprint-id <id> — skipping status sync` and continue without setting status. The user can fix the marker file manually.

---

## §4 — Discover Issues (metadata only)

```bash
grep -rlE "^(Status:|- \*\*Status:\*\*) ready-for-agent" "$feature_path/issues/" | sort
```

For each candidate, read **only**:

- filename
- the `Status:` line
- the `## Blocked by` section
- (optionally) the first `# …` heading

An issue is **eligible** when every referenced blocker file exists and has `Status: done`. If a blocker is missing entirely → set the current issue to `needs-info`, write a one-liner into `deviations.md`, skip. If a blocker is still `ready-for-agent` → leave the dependent issue queued for a later iteration (becomes eligible once the blocker completes).

Queue eligible issues alphabetically (by filename) unless §6 reorders them.

---

## §5 — Issue Quality Gate (before worker dispatch)

Run the synonym greps from `formats.md` §1. If any required concept (Intent / Acceptance criteria / Blocked by) has zero matches:

- Set `Status: needs-info`
- Append a one-liner to `deviations.md` listing the missing sections
- Skip the issue (do not ask the worker to guess)

This gate runs **on headings only**, never on bodies — cheap, and prevents burning a full Worker+Reviewer cycle on under-specified issues.

---

## §6 — Optional Planner Phase (adaptive threshold)

Spawn the Planner sub-agent **at most once per full pass** when **any** of these triggers:

1. `len(eligible) > planner_threshold` (tunable, default `5`), **OR**
2. `len(eligible) >= 3` AND at least one eligible issue is referenced in another issue's `## Blocked by` section (dependency fan-out → ordering matters even at small N).

For ≤ 2 eligible issues, never spawn the planner — alphabetical order is fine.

The Planner uses `planner.md` as its prompt template and `subagent_type: Explore` (read-only). Required output, parseable from the agent's final message:

```text
<plan>
{"order": ["01-foo.md", "03-bar.md", "07-baz.md"], "reason": "<one sentence>"}
</plan>
```

If the tag is absent, malformed, or contains a filename not in the eligible set → **ignore the plan**, fall back to alphabetical, log `planner ignored` in `run-log.md`. The Planner has no authority to skip or block issues — only to reorder.

---

## §7 — Main Loop

```text
iteration = 0
rework_count[issue] = 0
malformed_retries[issue] = 0
total_cycles = 0
MAX_CYCLES_PER_ITER = max(cycles_cap, eligible_at_iter_start * 3)

WHILE iteration < max_iter:
    iteration++
    eligible = discover_and_quality_gate()           # §4 + §5
    IF eligible is empty: break

    queue = planner_order(eligible) if planner_triggers(eligible) else sorted(eligible)
    Write queue to queue.md

    iter_cycles = 0
    approved_this_pass = false
    rework_persisted_this_pass = false

    WHILE queue not empty AND iter_cycles < MAX_CYCLES_PER_ITER:
        issue = queue.dequeue()
        IF re-read shows Status != ready-for-agent: continue

        worker_result = spawn_worker(issue)          # §8
        iter_cycles++; total_cycles++

        IF worker_result starts with "DONE:":
            # §8.5 cheap pre-check — catches missing Evidence before gate/reviewer
            IF NOT scripts/check-evidence.sh issue.path:
                rework_count[issue] += 1
                handle_rework(issue, "evidence-incomplete")
                continue

            gate_mode = classify_diff()              # gates.md §2
            gate_ok = run_gate(gate_mode)            # gates.md §3
            IF NOT gate_ok:
                rework_count[issue] += 1
                handle_rework(issue, "gate failed — see test-notes.md")
                continue

            reviewer_result = spawn_reviewer(issue)  # §9
            iter_cycles++; total_cycles++

            CASE reviewer_result:
                "APPROVED:" →
                    commit_issue(issue)              # gates.md §4
                    delete_rework_file(issue)
                    approved_this_pass = true
                    Keep Status: done

                "REWORK:" →
                    rework_count[issue] += 1
                    persist_rework_feedback(issue, reviewer_result)
                    rework_persisted_this_pass = true
                    handle_rework(issue, "rework — " + first_line)

                "BLOCKED:" →
                    Set Status: needs-human
                    log "reviewer blocked — " + reviewer_result

                malformed / ERROR / missing tag →
                    malformed_retries[issue] += 1
                    IF malformed_retries[issue] <= 1:
                        log "reviewer malformed — retrying once"
                        Re-add to front of queue (Status stays ready-for-agent)
                    ELSE:
                        Set Status: needs-human
                        log "reviewer error — " + reviewer_result

        ELSE IF worker_result starts with "BLOCKED:":
            Set Status: needs-info
            log "✗ blocked — " + worker_result

        ELSE IF worker_result starts with "NEEDS-REPLAN:":
            Set Status: needs-human
            log "✗ replan — " + worker_result

        ELSE:                                        # malformed worker output
            malformed_retries[issue] += 1
            IF malformed_retries[issue] <= 1:
                log "worker malformed — retrying once"
                Re-add to front of queue
            ELSE:
                Set Status: needs-human
                log "✗ error — " + worker_result

        context_compact()                            # §12
        rediscover_into_queue(queue)                 # §13

    # Early-exit only if NO real progress in this pass.
    # Newly-persisted rework counts as progress (next worker has fresh blockers).
    IF NOT approved_this_pass AND NOT rework_persisted_this_pass:
        log "no progress this pass — exiting early"
        break

handle_rework(issue, reason):
    IF rework_count[issue] > rework_limit:
        Set Status: needs-human
        log "rework-limit (" + reason + ")"
    ELSE:
        Set Status: ready-for-agent
        Re-add to front of queue
        log "↺ " + reason
```

**Exit conditions:**

| Condition | Action |
|---|---|
| Queue empty AND iteration < max_iter | §15 verify → §16 summary → §17 cleanup if all done |
| `max_iter` reached | Stop, write summary, ask before deleting |
| `MAX_CYCLES_PER_ITER` reached | Stop the iteration, log `cycle-cap hit` |
| A full pass produced neither APPROVED nor a new REWORK file | Stop, summary, ask before deleting |

---

## §8 — Worker Dispatch

Read `worker.md` for the prompt template.

Before spawning:

- Read the **full current issue content** (this issue only).
- Optionally include compact feature context if files exist (one of):
  - `<feature_path>/PRD.md`
  - `<feature_path>/context.md`
  - `<feature_path>/issue-map.md`
- Include the latest `context-summary.md`.
- Include `config-resolved.md` so the worker knows which gate commands to run.
- Do **not** include unrelated issues unless they are direct, already-`done` blockers needed for context.
- **Rework path** — if `rework/<basename>.md` exists, read it in full and pass its content as `{{REWORK_FEEDBACK}}`. Otherwise pass an empty string.

Spawn via `Agent` with `subagent_type: general-purpose` (worker needs Edit/Write):

- `description`: `"Implement: <issue_filename>"` (or `"Rework: <issue_filename>"` on rework rounds).
- Do **not** set `isolation: worktree` — work on the active branch.

Prompt variables: `{{ISSUE_PATH}}`, `{{ISSUE_CONTENT}}`, `{{FEATURE_PATH}}`, `{{COMPACT_CONTEXT}}`, `{{GATE_COMMANDS}}`, `{{REWORK_FEEDBACK}}`.

Worker must return exactly **one status line** — no diffs, no code blocks:

```text
DONE: <one-line summary>
BLOCKED: <reason — missing prerequisite>
NEEDS-REPLAN: <reason — scope/architecture/assumption broken>
ERROR: <reason — unrecoverable failure>
```

---

## §8.5 — Evidence Pre-Check (cheap, runs before gate)

```bash
scripts/check-evidence.sh "$issue_path"
```

Exit 0 → proceed to gate.
Exit 1 → rework (counts against `rework_limit`); never burn a gate run or reviewer spawn.
Exit 2 → setup error; log and treat as worker error.

This catches the most common failure mode (worker forgets the Evidence block) in < 50 ms, instead of running gates and a full Reviewer spawn first.

---

## §9 — Reviewer Dispatch

Read `reviewer.md` for the prompt template.

Before spawning:

- Re-read the current issue file (worker may have updated it).
- Collect a compact diff fingerprint — **never** paste the full diff into orchestrator context:

```bash
git diff --stat
git diff --name-only
```

The reviewer inspects files and diff directly via its own tools.

Spawn via `Agent` with `subagent_type: Explore` (read-only):

- `description`: `"Review: <issue_filename>"`

Prompt variables: `{{ISSUE_PATH}}`, `{{ISSUE_CONTENT}}`, `{{FEATURE_PATH}}`, `{{GATE_COMMANDS}}`, `{{GATE_RESULT}}`, `{{CHANGED_FILES}}`, `{{DIFF_STAT}}`.

`{{GATE_RESULT}}` is the literal output line from §10 — e.g. `gate ok`, `gate ok (quick-path: doc-only)`, or `gate skipped`. The reviewer **trusts** this result and does not re-run the heavy gate commands; it may only run `--check`-form spot probes if it has a concrete suspicion.

Reviewer returns exactly **one status line**, optionally followed by `BLOCKERS:` / `SUGGESTIONS:`:

```text
APPROVED: <compact reason>

REWORK: <compact required changes>
BLOCKERS:
- [path/file:NN] description
SUGGESTIONS:
- [path/file:NN] description

BLOCKED: <reason>
ERROR: <reason>
```

### `persist_rework_feedback(issue, reviewer_result)`

When the reviewer returns `REWORK:`, extract the `BLOCKERS:` block (suggestions stay informational) and write to `<feature_path>/.ratchet-up/rework/<basename>.md`:

```md
# Rework Feedback — <basename>

Iteration: <N>
Reviewer summary: <REWORK first line>

## Blockers (must fix this round)
- [path/file:NN] description
- [path/file:NN] description
```

This file is the **single source of truth** for the next worker spawn. After `APPROVED:` the file is deleted (see `gates.md` §4).

If the reviewer returned `REWORK:` without a `BLOCKERS:` block, write the entire reviewer one-liner under `## Blockers` so the next worker still has actionable context. **Never lose the rework reason.**

---

## §12 — Context Compaction

After every cycle, **rewrite** `context-summary.md` to keep only:

```md
# Context Summary

## Feature
<feature_path>

## Active Branch
<branch> @ <short-sha>

## Completed Issues
- <filename>: <one-liner>

## Current Queue
- <filename>

## Rework Items
- <filename>: <count> — <reason>

## Deviations / Blockers
- <filename>: <reason>

## Next Eligible Issues
- <filename>
```

The orchestrator retains only this summary in active context. **Do not** retain: full diffs, full logs, full test output, complete bodies of past issues, raw worker/reviewer analysis. If you need them again, re-read the file.

---

## §13 — Rediscovery

After each cycle:

```bash
grep -rlE "^(Status:|- \*\*Status:\*\*) ready-for-agent" "$feature_path/issues/" | sort
```

Re-evaluate blockers. Append newly eligible issues to the queue if they are not already queued, not currently being processed, and not `needs-info` / `needs-human`. This is how dependency chains unblock within a single iteration.

---

## §14 — Rework Limit

Each issue may be reworked at most `rework_limit` times (tunable, default `2`). Combined: gate-failures + reviewer rejections + evidence-precheck failures all count.

If exceeded:

- Set `Status: needs-human`
- Append `rework-limit exceeded` to `run-log.md`
- Stop looping that issue; continue with the next eligible one

Independent of rework_count, `malformed_retries` allows **one** retry per issue for malformed worker/reviewer output before escalating to `needs-human`.

---

## §15 — Objective Final Verification

After the loop, classify the result objectively:

```bash
grep -rE "^(Status:|- \*\*Status:\*\*) " "$feature_path/issues/" | sort
grep -rlE "^(Status:|- \*\*Status:\*\*) ready-for-agent" "$feature_path/issues/" || true
grep -rLE "^(Status:|- \*\*Status:\*\*) done" "$feature_path/issues/" || true
```

**A) All Done** — every issue file has `Status: done` and none have `ready-for-agent`, `needs-info`, or `needs-human` → proceed to §15.5, then §16, then §17.

**B) Incomplete** — at least one issue is not `done` → print summary, **do not delete**, ask explicitly:

```text
⚠️  Cleanup übersprungen — nicht alle Issues sind abgeschlossen.

Offene Issues:
  - issues/03-foo.md (Status: needs-info)
  - issues/04-bar.md (Status: ready-for-agent)

Empfehlung: Lösch den Ordner jetzt nicht. Die offenen Issues enthalten
wichtige Informationen (Blockaden, Fehlerbeschreibungen), die du noch
brauchst, um den Strang abzuschließen. Ein vorzeitiges Löschen würde
diesen Kontext unwiederbringlich vernichten.

Möchtest du den Ordner <feature_path> trotzdem löschen? (ja/nein)
```

Only delete if the user answers `ja` explicitly.

---

## §15.5 — Roadmap Status (final, only on Branch A — All Done)

Runs only when §15 classified the result as "All Done". For Branch B (Incomplete), §15.5 is skipped entirely — the Sprint stays `in-progress` until the next ratchet-up run finishes the remaining issues.

1. Read `<feature_path>/.roadmap-sprint`. If absent or equal to `none`, skip.
2. Read the `**Status:**` line of the matching Sprint block in `.scratch/roadmap.md`.
3. Apply the table:

   | Current | Action |
   |---|---|
   | `in-progress` | Edit to `**Status:** done`. Log `roadmap: <sprint-id> in-progress → done`. Include the transition line in §16 summary. |
   | `todo` | Edit to `**Status:** done` (covers the edge case where §3.5 was skipped — e.g. user added the marker mid-flight). Log `roadmap: <sprint-id> todo → done`. |
   | `done` | No-op. |

   Use the same two-line anchor pattern as §3.5 (`**Sprint-ID:**` followed by `**Status:**`).
4. If the marker references a Sprint-ID not present in the roadmap, log `roadmap: marker references unknown sprint-id <id> — skipping final status` and continue. Do **not** create a new Sprint block.

---

## §16 — Final Summary

Print a compact markdown summary:

```md
# Ratchet-Up Summary

| Issue | Final Status | Notes |
|---|---|---|
| ... | ... | ... |

## Counts
- completed:
- reworked:
- skipped (needs-info):
- needs-human:
- remaining (ready-for-agent):

## Commits
- <type>(<scope>): <subject> — <issue_filename>

## Deviations
- ...

## Follow-up
- ...

## Gate mode
- format / analyze / test commands actually used (or `skipped`)
- quick-path hits: <count>

## Roadmap
- linked sprint: <sprint-id> | none | (no roadmap)
- transition: <todo → in-progress | in-progress → done | none>
```

If `.scratch/roadmap.md` does not exist or the marker is `none`, print `## Roadmap\n- (no link)` and skip transition.

---

## §17 — Cleanup (only after objective verification)

Cleanup is allowed **only** if §15 returned "All Done", or the user explicitly answered `ja` to the §15 prompt.

Re-run the Hard-Deletion-Guard immediately before deletion (preconditions from §1).

Then:

```bash
rm -rf "$feature_path"
```

Print: `Deleted: <feature_path>`

The dump zone `<feature_path>/.ratchet-up/` is removed implicitly with the feature directory — that is intentional.
