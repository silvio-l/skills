#!/usr/bin/env bash
# check-evidence.sh — fast Evidence-block pre-check before spawning gate/reviewer.
#
# Usage: scripts/check-evidence.sh <issue_path>
# Exit 0 → Evidence block present and minimally well-formed.
# Exit 1 → missing / incomplete; orchestrator should send issue back to rework
#          without burning a gate run or reviewer spawn.
#
# Cheap heuristic: greps for the mandatory keys. Reviewer still does the deep
# cross-check against the diff (see reviewer.md).

set -u

issue_path="${1:-}"
if [[ -z "$issue_path" || ! -f "$issue_path" ]]; then
  echo "check-evidence: missing or unreadable issue file: $issue_path" >&2
  exit 2
fi

required_keys=(
  "^## Evidence"
  "^- changed_files:"
  "^- tests_run:"
  "^- acceptance_coverage:"
  "^- gate_commands_run:"
  "^- remaining_risks:"
  "^- decisions:"
)

missing=()
for key in "${required_keys[@]}"; do
  if ! grep -qE "$key" "$issue_path"; then
    missing+=("${key#^}")
  fi
done

if (( ${#missing[@]} > 0 )); then
  printf 'evidence-incomplete: %s\n' "${missing[*]}"
  exit 1
fi

# Status flip check — worker contract requires `Status: done` on DONE return.
if ! grep -qE "^Status: done$" "$issue_path"; then
  echo "evidence-incomplete: Status line not flipped to 'done'"
  exit 1
fi

exit 0
