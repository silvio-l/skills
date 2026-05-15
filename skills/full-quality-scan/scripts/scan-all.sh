#!/usr/bin/env bash
# full-quality-scan: run all linters on the entire repo and print structured output.
# Usage: bash scripts/scan-all.sh [repo-root]
# Output: one finding per line, format: BUCKET|FILE:LINE|MESSAGE
# Exit code: 0 = clean, 1 = findings present

set -euo pipefail
ROOT="${1:-$(git rev-parse --show-toplevel 2>/dev/null || pwd)}"
cd "$ROOT"

FINDINGS=0
print() { echo "$1"; FINDINGS=$((FINDINGS + 1)); }

# ── Dart/Flutter ──────────────────────────────────────────────────────
if command -v flutter >/dev/null 2>&1; then
  while IFS= read -r line; do
    [[ "$line" =~ ^(error|warning|info)\ -\ (.+):([0-9]+):[0-9]+\ -\ (.+)$ ]] || continue
    print "dart|${BASH_REMATCH[2]}:${BASH_REMATCH[3]}|${BASH_REMATCH[1]}: ${BASH_REMATCH[4]}"
  done < <(flutter analyze --fatal-infos 2>&1 || true)
fi

# ── C++ (cppcheck) ────────────────────────────────────────────────────
if command -v cppcheck >/dev/null 2>&1 && [ -d windows/runner ]; then
  SUPPRESS=""
  [ -f windows/runner/.cppcheck-suppress ] && SUPPRESS="--suppressions-list=windows/runner/.cppcheck-suppress"
  while IFS= read -r line; do
    [[ "$line" =~ ^([^:]+):([0-9]+):.*(error|warning|style|performance|portability):\ (.+)$ ]] || continue
    print "cpp|${BASH_REMATCH[1]}:${BASH_REMATCH[2]}|${BASH_REMATCH[3]}: ${BASH_REMATCH[4]}"
  done < <(cppcheck --enable=style,warning,performance,portability \
    --platform=win64 --std=c++17 $SUPPRESS --inline-suppr --quiet \
    windows/runner/ 2>&1 | grep -E ': (error|warning|style|performance|portability):' || true)
fi

# ── JS/TS (ESLint) ────────────────────────────────────────────────────
if [ -f website/node_modules/.bin/eslint ] && [ -f website/eslint.config.mjs ]; then
  while IFS= read -r line; do
    [[ "$line" =~ ^[[:space:]]+([0-9]+):[0-9]+[[:space:]]+(error|warning)[[:space:]]+(.+)$ ]] || continue
    print "js_ts|website/src:${BASH_REMATCH[1]}|${BASH_REMATCH[2]}: ${BASH_REMATCH[3]}"
  done < <(cd website && node_modules/.bin/eslint src/ 2>&1 || true)
fi

# ── SAST (Semgrep) ────────────────────────────────────────────────────
if command -v semgrep >/dev/null 2>&1; then
  while IFS= read -r line; do
    [[ "$line" =~ ^([^:]+):([0-9]+):.*$ ]] || continue
    print "sast|${BASH_REMATCH[1]}:${BASH_REMATCH[2]}|semgrep finding"
  done < <(semgrep --config p/ci --quiet \
    --include="*.ts" --include="*.js" --include="*.mjs" \
    --include="*.cpp" --include="*.h" --include="*.go" \
    --exclude="node_modules" --exclude="dist" --exclude="build" --exclude=".dart_tool" \
    . 2>&1 || true)
fi

# ── Dependencies (osv-scanner) ────────────────────────────────────────
if command -v osv-scanner >/dev/null 2>&1; then
  LOCKFILES=""
  [ -f pubspec.lock ] && LOCKFILES="$LOCKFILES --lockfile pubspec.lock"
  [ -f website/package-lock.json ] && LOCKFILES="$LOCKFILES --lockfile website/package-lock.json"
  if [ -n "$LOCKFILES" ]; then
    OSV_OUT=$(osv-scanner scan $LOCKFILES 2>&1 || true)
    if echo "$OSV_OUT" | grep -q "VULNERABLE\|vulnerability"; then
      while IFS= read -r line; do
        [[ "$line" == *"VULNERABLE"* ]] || continue
        print "deps|lockfile|$line"
      done <<< "$OSV_OUT"
    fi
  fi
fi

# ── Summary ───────────────────────────────────────────────────────────
echo "---"
echo "TOTAL_FINDINGS=$FINDINGS"
[ "$FINDINGS" -eq 0 ] && exit 0 || exit 1
