# Phase 0 — Repo Introspection

This phase runs deterministically before any web research or user interaction. It reads
the repo on disk and produces a structured JSON situation report that subsequent phases consume.

## Running the script

```bash
SCRIPT=~/.claude/skills/ship-to-appstore/scripts/phase0-introspect
python3 "$SCRIPT" "<path-to-flutter-repo>"
```

- Exit 0: Flutter/iOS project detected — JSON situation report on stdout.
- Exit 1: Not a Flutter/iOS project — warning on stderr, no JSON. Abort with the warning text.
- Exit 2: Usage error.

## Situation report schema

```json
{
  "flutter_ios": true,
  "app_display_name": "my_app",
  "marketing_version": "1.2.3",
  "build_number": "42",
  "bundle_id": "com.example.myapp",
  "team_id": "XXXXXXXXXX",
  "signing_style": "automatic",
  "icon_set": {
    "complete": true,
    "missing_sizes": [],
    "total_required": 27,
    "present": 27
  },
  "launch_assets": {
    "has_launch_screen_storyboard": true,
    "has_launch_image_assets": false
  }
}
```

## Interpreting findings

Present the situation report to the user as a structured summary. Flag issues clearly.

### Version fields

- `marketing_version`: The human-visible version string (e.g. `1.2.3`). Must be bumped before submission.
- `build_number`: The integer build counter (e.g. `42`). Must be strictly greater than the last accepted build on ASC — even for the same marketing version.

### Signing

| `team_id` | `signing_style` | Interpretation |
|---|---|---|
| present | `automatic` | Standard Xcode-managed signing — usually works out of the box. |
| present | `manual` | Developer manages certificates/profiles manually — more setup required. |
| `null` | `unknown` | No Team ID found in pbxproj. Signing is not configured. Flag as a blocker. |

### Icon set

- `complete: false` with non-empty `missing_sizes`: list the missing slots and ask the user to regenerate via `flutter_launcher_icons` or Xcode.
- `total_required: 0` means the `AppIcon.appiconset/Contents.json` is missing entirely — a critical gap.

### Launch assets

- Modern Flutter projects use `has_launch_screen_storyboard: true`. That is correct.
- `has_launch_image_assets: true` alongside a storyboard is redundant and may cause a review warning.
- Both `false` means no launch screen is configured — the app will show a blank screen on startup.

## What this phase does NOT check

Phase 0 is intentionally scoped to facts readable from disk without network or credentials:

- Does not check App Store Connect for existing app records, build status, or metadata gaps.
- Does not validate certificate expiry or provisioning profile contents.
- Does not check Xcode or Flutter SDK versions against Apple's current minimums.
- Does not verify screenshot specifications or store metadata completeness.

These gaps are filled by Phase 1 (freshness research), Phase 2 (ASC status), and Phase 3 (guided release loop).
