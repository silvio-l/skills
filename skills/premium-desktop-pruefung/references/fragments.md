# Fragment and worker-result examples

One complete example per table, in the exact shape `apply` accepts. Every block is checked against `schemas/run.schema.json` by the skill's tests, so a field that is missing here is not optional; the one exception is `sha256` in a files operation, which `apply` copies from the manifest. Replace every value with observed facts; digests come from `audit.py digest`, the context digest from `audit.py next`. [protocol.md](protocol.md) explains the rules behind each field.

A fragment wraps operations; `base_sequence` is the ledger sequence the author read (an older one is rebased when the written rows did not change since):

```json
{
  "base_sequence": 42,
  "actor": "coordinator",
  "operations": [
    {"table": "profile", "id": "scope", "value": {"value": "Full audit of the desktop app, macOS 15 exercised; Windows supported but not exercised. Screen readers excluded (not requested).", "evidence": ["E-brief"]}},
    {"table": "objects", "id": "O-settings", "value": {"label": "Settings window", "kind": "view", "sources": ["src/settings/SettingsView.tsx"], "variants": ["light-wide-en", "dark-compact-de"], "relations": ["O-main-window"], "audience": "All users; administrators change sync options"}},
    {"table": "files", "id": "src/settings/SettingsView.tsx", "value": {"decision": "mapped", "reason": "", "objects": ["O-settings"]}},
    {"table": "applicability", "id": "NA-dialog-resize", "value": {"kinds": ["dialog"], "objects": [], "criteria": [], "dimensions": ["05"], "variants": [], "reason": "Dialogs have a fixed size set in src/ui/Dialog.tsx:12; window-resizing criteria cannot apply.", "evidence": ["E-dialog-source"], "actor": "coordinator"}},
    {"table": "equivalences", "id": "Q-settings-theme", "value": {"object": "O-settings", "representative": "light-wide-en", "variants": ["dark-wide-en"], "criteria": ["WCAG-2.4.3"], "dimensions": [], "reason": "Focus order is theme-independent: one component tree, theme only swaps tokens (src/theme.ts).", "evidence": ["E-theme-source"], "actor": "coordinator"}},
    {"table": "jobs", "id": "J-settings-1", "value": {"owner": "coordinator", "units": ["U-0a1b2c3d4e5f60718293"], "status": "active", "reason": "Settings keyboard walk, light-wide-en"}}
  ]
}
```

Unit results, written by the job owner after `pending` → `running` (a pass, then a documented block):

```json
{
  "base_sequence": 57,
  "actor": "worker-2",
  "operations": [
    {"table": "units", "id": "U-0a1b2c3d4e5f60718293", "value": {"object": "O-settings", "variant": "light-wide-en", "criterion": "WCAG-2.4.3", "status": "pass", "actor": "worker-2", "method": "Runtime keyboard walk with full accessibility snapshot after every Tab", "expected": "Focus follows the visual order: sidebar, form fields top to bottom, Save", "actual": "Focus visited 14 controls in visual order and returned to the sidebar", "steps": ["Launch build abc123 with a fresh profile", "Open Settings with Cmd+,", "Press Tab 15 times, snapshot after each"], "evidence": ["E-walk-settings"], "limitations": ["Window 1280x800 verified by list-windows; other sizes are separate variants"], "reason": ""}},
    {"table": "units", "id": "U-1b2c3d4e5f6071829304", "value": {"object": "O-settings", "variant": "dark-compact-de", "criterion": "ON-03", "status": "blocked", "actor": "worker-2", "method": "Runtime walkthrough of the first-run flow", "expected": "Onboarding appears on first launch", "actual": "Fresh profile skips onboarding: the build seeds onboarding.done=true", "steps": ["Launch with an empty profile directory", "Observe the first window"], "evidence": ["E-firstrun-shot"], "limitations": ["First-run copy and order untested"], "reason": "First-run state not reachable on this build", "blocker": {"attempt": "Empty profile directory and a new user account", "obstacle": "Build seeds onboarding.done=true", "alternatives": "Source reading only covers copy, not flow; no test hook found", "next_action": "Ask for a build flag or test hook that resets onboarding", "retry_when": "A build with an onboarding reset is available", "context_digest": "copy from audit.py next"}}}
  ]
}
```

A finding (investigator), a duplicate of it (any actor sets `duplicate_of` on the suspected finding; `status: "duplicate"` follows an independent review with outcome `duplicate`) and a tracked one:

```json
{
  "base_sequence": 61,
  "actor": "worker-2",
  "operations": [
    {"table": "findings", "id": "F-settings-focus", "value": {"title": "Save button unreachable by keyboard in compact settings", "units": ["U-2c3d4e5f607182930415"], "status": "suspected", "actor": "worker-2", "root_cause": "settings:compact-layout:save-outside-tab-order", "impact": "Keyboard users cannot save settings in a narrow window; no workaround", "priority": "P1", "steps": ["Open Settings in a 720x550 window", "Press Tab until focus returns to the sidebar"], "expected": "Save receives focus", "actual": "Focus skips Save; it has tabindex=-1 in the compact layout", "recommendation": "Remove tabindex=-1 from the compact Save button; accept when Tab reaches Save in both layouts", "evidence": ["E-walk-compact"]}},
    {"table": "findings", "id": "F-settings-save-dup", "value": {"title": "Compact settings cannot be saved with the keyboard", "units": ["U-3d4e5f60718293041526"], "status": "duplicate", "duplicate_of": "F-settings-focus", "actor": "worker-3", "root_cause": "settings:compact-layout:save-outside-tab-order", "impact": "Same as F-settings-focus", "priority": "P1", "steps": ["Open Settings in compact layout", "Tab through"], "expected": "Save receives focus", "actual": "Save is skipped", "recommendation": "See F-settings-focus", "evidence": ["E-walk-compact-2"]}},
    {"table": "findings", "id": "F-known-export", "value": {"title": "Export dialog loses the chosen folder", "units": ["U-4e5f6071829304152637"], "status": "suspected", "actor": "worker-2", "root_cause": "export:folder-picker:state-reset", "impact": "Users pick the folder twice", "priority": "P2", "steps": ["Open Export", "Choose a folder", "Change the format"], "expected": "Folder stays selected", "actual": "Folder resets to Downloads", "recommendation": "Keep the folder in dialog state", "evidence": ["E-export-trace"], "tracking": {"kind": "issue", "reference": "#812", "reason": "Issue #812 describes the same reset with the same steps (issue text read, not only the title)", "evidence": ["E-issue-812"]}}}
  ]
}
```

A unit review, and a finding review that accepts subject to machine-readable corrections (`digest` is the digest of the corrected row, `base_digest` of the row as read; `digest --corrections` prints both):

```json
{
  "base_sequence": 70,
  "actor": "critic-1",
  "operations": [
    {"table": "reviews", "id": "R-U-0a1b2c3d", "value": {"actor": "critic-1", "mode": "independent", "scope": "unit", "target": "U-0a1b2c3d4e5f60718293", "digest": "from audit.py digest --scope unit", "verdict": "accept", "outcome": "pass", "evidence": ["E-walk-settings", "E-critic-rewalk"], "countercheck": "Re-walked with a fresh profile and checked the window size in list-windows before the first Tab", "limitations": ["Same machine as the worker"]}},
    {"table": "reviews", "id": "R-F-settings-focus", "value": {"actor": "critic-1", "mode": "independent", "scope": "finding", "target": "F-settings-focus", "digest": "digest of the corrected row", "base_digest": "digest of the row as read", "verdict": "accept", "outcome": "confirmed", "evidence": ["E-critic-compact"], "countercheck": "git log -S tabindex on the file: no commit intends it; no test asserts it", "limitations": [], "corrections": {"priority": "P0", "impact": "Keyboard users cannot save any setting in a narrow window; changes are lost on close"}}}
  ]
}
```

A gap from a rejected review, and a foreign change on the test host:

```json
{
  "base_sequence": 75,
  "actor": "coordinator",
  "operations": [
    {"table": "gaps", "id": "G-R-inventory-2", "value": {"description": "R-inventory-2: the published help pages have no object", "status": "resolved", "units": [], "evidence": ["E-help-objects"], "resolution": "Added O-help-index and O-help-article, plan rerun"}},
    {"table": "gaps", "id": "G-foreign-provisioning", "value": {"description": "Remote provisioning started a helper service at 14:05 during the settings walk", "status": "open", "units": ["U-0a1b2c3d4e5f60718293"], "evidence": ["E-launchctl-diff"], "resolution": "", "category": "foreign-change"}}
  ]
}
```

An evidence row as `audit.py evidence` writes it (never write evidence rows by hand; a directory adds `members`):

```json
{"table": "evidence", "id": "E-walk-settings", "value": {"file": "evidence/written-by-audit-py", "sha256": "written-by-audit-py", "kind": "screenshot", "locator": "Settings, Tab 1-15", "environment": "macOS 15.4, build abc123, 1280x800, light, en", "captured_by": "worker-2", "members": {"tab-01.png": "sha256 of the file"}}}
```

`evidence RUN BATCH.json --batch --actor worker-2`, sources relative to the batch file:

```json
[
  {"id": "E-walk-settings", "source": "shots/settings-walk", "kind": "screenshot", "locator": "Settings, Tab 1-15", "environment": "macOS 15.4, build abc123, 1280x800, light, en"},
  {"id": "E-walk-trace", "source": "traces/settings-walk.json", "kind": "trace", "locator": "accessibility snapshots after each Tab", "environment": "macOS 15.4, build abc123"}
]
```

`ingest RUN RESULT.json --actor worker-2`: the whole worker result in one write. Findings omit `actor` (the ingesting worker is the author); a unit's `finding` adds it to that finding:

```json
{
  "job": "J-settings-2",
  "evidence": [
    {"id": "E-walk-compact", "source": "shots/compact-walk", "kind": "screenshot", "locator": "Compact settings, Tab 1-12", "environment": "macOS 15.4, build abc123, 720x550, dark, de"}
  ],
  "units": {
    "U-2c3d4e5f607182930415": {"status": "fail", "method": "Runtime keyboard walk with full snapshots", "expected": "Save receives focus", "actual": "Focus skips Save", "steps": ["Open Settings at 720x550", "Tab through"], "evidence": ["E-walk-compact"], "limitations": [], "reason": "", "finding": "F-settings-focus"}
  },
  "findings": {
    "F-settings-focus": {"title": "Save button unreachable by keyboard in compact settings", "units": [], "status": "suspected", "root_cause": "settings:compact-layout:save-outside-tab-order", "impact": "Keyboard users cannot save settings in a narrow window", "priority": "P1", "steps": ["Open Settings at 720x550", "Tab through"], "expected": "Save receives focus", "actual": "Focus skips Save", "recommendation": "Remove tabindex=-1 from the compact Save button", "evidence": ["E-walk-compact"]}
  },
  "close": true
}
```
