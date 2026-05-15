---
name: full-quality-scan
description: Runs all configured linters and security scanners (cppcheck, ESLint, Semgrep, osv-scanner, dart analyze) across the entire repository, then fixes every finding — directly if ≤10, via a structured plan with parallel subagents if more. Use when user wants a full repo-wide quality or security scan, says "scan everything", "fix all lint issues", "clean up the whole repo", "full quality check", or asks to run tools across the full codebase (not just staged files or recent changes).
---

# Full Quality Scan & Fix

## Overview

Threshold: **≤ 10 findings → fix directly. > 10 → plan first, then fix with subagents.**

## Phase 1 — Scan (run all tools in parallel)

Run each applicable tool. Collect raw output into named buckets.

```bash
# Dart/Flutter — always
flutter analyze --fatal-infos 2>&1

# C++ — if windows/runner/ exists
cppcheck \
  --enable=style,warning,performance,portability \
  --platform=win64 --std=c++17 \
  --suppressions-list=windows/runner/.cppcheck-suppress \
  --inline-suppr --quiet \
  windows/runner/ 2>&1 | grep -E ': (error|warning|style|performance|portability):'

# JS/TS — if website/eslint.config.mjs exists
(cd website && node_modules/.bin/eslint src/ 2>&1)

# SAST — if semgrep installed
semgrep --config p/ci --error --quiet \
  --include="*.ts" --include="*.js" --include="*.mjs" \
  --include="*.cpp" --include="*.h" --include="*.go" \
  --exclude="node_modules" --exclude="dist" --exclude="build" --exclude=".dart_tool" \
  . 2>&1

# Dependency vulnerabilities — if osv-scanner installed
osv-scanner scan \
  $([ -f pubspec.lock ] && echo "--lockfile pubspec.lock") \
  $([ -f website/package-lock.json ] && echo "--lockfile website/package-lock.json") \
  2>&1
```

## Phase 2 — Triage

Count and group findings:

| Bucket | Tool | Fix strategy |
|---|---|---|
| dart | flutter analyze | `dart fix --apply`, then manual |
| cpp | cppcheck | manual C++ edits |
| js_ts | eslint | `eslint --fix`, then manual |
| sast | semgrep | manual, case-by-case |
| deps | osv-scanner | `npm audit fix` / `flutter pub upgrade` |

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

Get user confirmation, then spawn one subagent per bucket with ≥ 3 findings:

```
Agent(description="Fix cppcheck findings in windows/runner/",
      prompt="Fix these cppcheck findings in windows/runner/: [list]. 
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

Re-run the full Phase 1 scan. All buckets must return zero findings before proceeding.

If any finding remains: return to Phase 4 for that bucket only.

## Phase 6 — Commit

```bash
flutter analyze --fatal-infos   # must be clean
flutter test                    # must be green (or pre-existing failures noted)
git add <changed files>
git commit -m "fix(quality): resolve all <tool> findings\n\n<summary>"
```

One commit per major bucket is fine; one combined commit is also acceptable.

## Tool availability

Skip any tool silently if not installed — note which were skipped in the final report. Never install tools on behalf of the user without asking.
