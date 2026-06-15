---
name: full-quality-scan
description: Runs all configured linters and security scanners (cppcheck, ESLint, Semgrep, osv-scanner, dart analyze) repo-wide, then fixes every finding. Use for a repo-wide quality or security scan, e.g. "scan everything" or "fix all lint issues".
---

# Full Quality Scan & Fix

## Overview

Threshold: **≤ 10 findings → fix directly. > 10 → plan first, then fix with subagents.**

## Phase 1 — Scan

Run the bundled wrapper. It is the single source of truth for tool flags and skip-rules — never duplicate the tool invocations into the agent's prompt.

```bash
bash skills/full-quality-scan/scripts/scan-all.sh
# or, when invoked as the installed skill:
bash ~/.claude/skills/full-quality-scan/scripts/scan-all.sh
```

Output contract — **one finding per line**:

```
BUCKET|FILE:LINE|MESSAGE
…
---
TOTAL_FINDINGS=<n>
```

Exit code: `0` = clean, `1` = findings present. The wrapper skips silently for tools that are not installed; the summary line is always emitted.

Bucket names emitted by the wrapper: `dart`, `cpp`, `js_ts`, `sast`, `deps`. Anything else is a wrapper bug, not an unknown tool — fix the wrapper.

## Phase 2 — Triage

Parse each `BUCKET|FILE:LINE|MESSAGE` row and group by bucket. The bucket names map directly to fix strategies:

| Bucket | Source tool | Fix strategy |
|---|---|---|
| `dart` | flutter analyze | `dart fix --apply`, then manual |
| `cpp` | cppcheck | manual C++ edits |
| `js_ts` | eslint | `eslint --fix`, then manual |
| `sast` | semgrep | manual, case-by-case |
| `deps` | osv-scanner | `npm audit fix` / `flutter pub upgrade` |

`TOTAL_FINDINGS` from the wrapper's summary line is the threshold input:

**≤ 10 total → go directly to Phase 4 (fix inline).**
**> 10 total → build a plan in Phase 3.**

## Phase 3 — Plan (> 10 findings only)

Present a numbered fix plan grouped by bucket and severity:

```
PLAN
════
[deps]   1. Upgrade X (CVE-2025-…) — flutter pub upgrade / npm audit fix
[cpp]    2. floating_button_window.cpp:468 — unreadVariable tProg
[js_ts]  3. hero-carousel.ts:9 — prefer-const
...
```

Get user confirmation, then spawn one subagent per bucket with ≥ 3 findings. **Set `model` explicitly on every spawn** — fixing lint/security findings is Sonnet-tier work; never let the subagent inherit the orchestrator's model (subagent spend is the biggest cost driver):

```
Agent(description="Fix cppcheck findings in windows/runner/",
      model="claude-sonnet-4-6",
      prompt="Fix these cppcheck findings in windows/runner/: [list]. 
              Fix only the listed findings — do not touch or 'improve' surrounding code. 
              Run cppcheck after each logical group to verify. 
              Do not commit.")
```

Buckets with < 3 findings are fixed inline by the orchestrating agent.

## Phase 4 — Fix

For each bucket (inline or via subagent):

1. Apply auto-fixable changes first (`dart fix --apply`, `eslint --fix`, `npm audit fix`).
2. Fix remaining findings manually — read the exact file/line before editing.
3. Re-run the bucket's tool after every logical group to confirm green.

**Never suppress a finding without a written reason.**

## Phase 5 — Verify

Re-run `bash scripts/scan-all.sh`. The wrapper must exit `0` with `TOTAL_FINDINGS=0` before proceeding.

If any finding remains: return to Phase 4 for the affected bucket only — do not loop through clean buckets again.

## Phase 6 — Commit

```bash
bash scripts/scan-all.sh        # must exit 0
git add <changed files>
git commit -m "fix(quality): resolve <tool> findings\n\n<summary>"
```

The wrapper is the only quality gate at this stage; project-specific test/typecheck commands are out of scope for this skill and live in the project's own commit hooks or `CLAUDE.md`. One commit per major bucket is fine; one combined commit is also acceptable.

## Tool availability

The wrapper skips silently for any tool that is not installed — its summary line is the authoritative record of what ran. Never install tools on behalf of the user without asking.
