# Run ledger and executable gates

Python 3.8+ with the standard library is enough. Keep the run directory outside the product sources and use the same path for every command. A second `init` never overwrites work.

```sh
A="${CLAUDE_SKILL_DIR}/scripts/audit.py"
python3 "$A" init "$RUN"                    # creates audit.json, parts/, evidence/
python3 "$A" capacity                       # slots=N for the next wave (never above 3)
python3 "$A" merge "$RUN" "$RUN"/parts/w1-*.json
python3 "$A" check "$RUN"
python3 "$A" digest "$RUN"
python3 "$A" report "$RUN" > "$RUN/report.md"
```

`check` and `report` exit 0 for a complete ledger, 1 for open units, findings or other gate violations, and 2 for unreadable or structurally broken input. `report` also prints the partial balance on exit 1.

## Who writes what

- The **coordinator** is the only writer of `audit.json`. It changes the ledger only through `merge` (or a direct edit for its own fields such as `product` and `waves`).
- **Subagents** never touch `audit.json`. Each writes exactly one fragment file `parts/<agent-id>.json` in the format below plus its raw evidence under `evidence/<agent-id>/`, and returns a short summary.
- `merge` inserts or replaces table rows by ID, appends `waves`, overwrites `views`/`product` fields and replaces `final`. It lists every replaced ID — a replacement the coordinator did not intend means two agents were given overlapping units.

Use stable, readable IDs such as `O-settings`, `U-reset-win`, `C-reset`, `F-inheritance`, `E-reset-after`. Units keep their ID when reopened. A context or variant with a different test path gets its own unit.

Agent IDs (`owner`, `critic`, `verifier`, `implementer`, `retester`, `final.critic`) name real, separate subagent contexts, e.g. `worker-w1-a`, `critic-w1`, `verifier-F-focus`, `retester-F-focus`, `critic-final`. A renamed role inside the same context is not independent, and one session must not invent new identities.

## Fields

- `product` holds text for `audience, type, core_task, first_value, platforms, scope, coordinator`. Name boundaries and excluded products/platforms in `scope`. Report single exceptions as audited units.
- The four `views` (`product`, `code`, `runtime`, `platform`) each hold `account` (search path, yield, contradictions) and `evidence` (E-IDs). The runtime view needs a running app and live evidence.
- `objects` holds per O-ID `description, variants, links, rules, plan, evidence`. `links` is a list of other O-IDs, possibly empty. `rules` lists catalog IDs from `methoden.md`. `plan` maps each of those rule IDs to a list of concrete target variants (platform, state, input path where relevant). Every combination of object, rule and planned variant needs its own unit. Every catalog rule must be mapped at least once; a rule irrelevant for the whole product still gets an explicit mapping and an evidenced exclusion. The critic also checks the rules left out per object.
- `units` holds per U-ID `object, rule, variant, task, expected, owner, wave, mode, status, observation, countercheck, evidence`. `countercheck` states the counter-test performed and its result. Terminal states are `pass`, `candidate` and `excluded` (the latter with `rationale`). Open units carry `missing` and `next`. Use `mode: runtime` for behaviour and visible quality; only questions that are decidable statically use `inspection` with `inspection_reason`. A missing runner or refused permission keeps the unit open — an environment gap is never a reason to exclude.
- `evidence` holds per E-ID `kind, file, observation, context`. Kinds: `source, runtime, image, trace, diff, test, document`. Each file is relative to `audit.json`, exists and is non-empty. Archive relevant code excerpts with origin and revision. For interactions record app version/revision, OS, window situation, input, test data, steps and actual result. A screenshot proves what is visible, an event trace proves an input sequence, an accessibility tree proves semantics. Check that evidence actually shows what it claims.
- `waves` is a chronological list. Each wave holds `units, critic, critique, evidence, gaps`. `gaps` lists every U-ID with a justified gap; each must be worked again in a later wave. A unit's `wave` is the last wave it was worked in (1-based). The critic also re-checks passes and exclusions against the raw evidence. Every critique is a separate subagent run.
- `candidates` holds per C-ID `symptom, units, evidence`. All affected units carry `candidate`, even after refutation or repair; the current state of the problem comes from the finding.
- `findings` holds per F-ID `cause, candidates, verifier, alternative, reasoning, decision, evidence`. Each C-ID belongs to exactly one finding with a shared cause. `evidence` must include all original evidence of its candidates. The fresh verifier names and tests plausible alternatives. Allowed decisions: `confirmed`, `refuted`, `open` (plus `missing, next`). A `confirmed` finding adds `change, implementer, before, patch, after, retester, retest_status, retest_result, adjacent, adjacent_status, adjacent_result`. `before, patch, after` are E-ID lists for the baseline run, the real code diff and the runtime test of the changed build. `retest_status` and `adjacent_status` must be `pass`. A retester independent of the implementer re-runs the original path and one adjacent path; `adjacent` references its own evidence. The change itself happens in the target repository.
- `final` holds `critic, critique, evidence, gaps, snapshot`. A new critic reviews the updated end state after all retests. New gaps create work packages, another wave and another final critique. Set `gaps` to an empty list only after the review. Record the final review as an E-ID, fill in every other final field first, then run `digest` and store its output as `snapshot` (the only field excluded from the hash). Any later change to data, catalog or evidence files needs a new final critique.

## Example worker fragment

A fragment for `merge`. Replace the illustrative rule ID with the matching ID from `methoden.md`; evidence must really be produced.

```json
{
  "objects": {
    "O-editor": {"description": "Editor with search dialog", "variants": "macOS, keyboard; close search", "links": [], "rules": ["DES-03"], "plan": {"DES-03": ["macOS, keyboard, search dialog"]}, "evidence": ["E-before"]}
  },
  "units": {
    "U-editor-focus": {"object": "O-editor", "rule": "DES-03", "variant": "macOS, keyboard, search dialog", "task": "Close the search dialog with Escape and keep typing", "expected": "Input lands in the editor", "owner": "worker-w1-a", "wave": 1, "mode": "runtime", "status": "candidate", "countercheck": "Closing via the button returns focus to the editor.", "observation": "After Escape the editor ignores input.", "evidence": ["E-before"]}
  },
  "candidates": {"C-focus": {"symptom": "Keyboard input lost after dialog", "units": ["U-editor-focus"], "evidence": ["E-before"]}},
  "evidence": {"E-before": {"kind": "trace", "file": "evidence/worker-w1-a/focus-before.log", "context": "App/OS/revision and start state", "observation": "Focus target after Escape is the closed window."}}
}
```

Judge real depth from the observations. The validator cannot derive inventory completeness, screenshot provenance or the quality of a cause from files alone — that is what the independent review steps are for.
