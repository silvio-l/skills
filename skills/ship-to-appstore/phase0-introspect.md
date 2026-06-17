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
  },
  "credentials": {
    "p8_files": [{ "path": "ios/private_keys/AuthKey_ABC123.p8" }],
    "fastlane_appfile": { "path": "fastlane/Appfile" },
    "fastlane_env": null,
    "env_hints": ["ASC_ISSUER_ID"]
  },
  "fastlane_lanes": ["status", "release", "beta"],
  "analytics_tracking": [{ "package": "sentry_flutter", "category": "crash/diagnostics" }],
  "account_deletion": { "likely_present": true, "hints": ["deleteAccount", "Konto löschen"] },
  "ruby_env": {
    "has_gemfile": true,
    "ruby_version_file": "4.0.2",
    "bundler_locked": "4.0.8",
    "rbenv_present": true,
    "rvm_present": false
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

### Fastlane lanes

`fastlane_lanes` lists the lane names declared in `fastlane/Fastfile`. **Prefer these over generic
commands.** If the project defines a `status` lane, use it to read ASC state in Phase 2; if it
defines a `release`/`publish` lane, that is the submission path in Phase 3. A project-defined lane
encodes the developer's exact API-key wiring, version logic, and submission flags — re-inventing
those with raw `altool`/`deliver` calls is fragile. An empty list means no Fastfile; fall back to
the generic strategies.

### Analytics / tracking SDKs (drives privacy labels — do NOT ask the user)

`analytics_tracking` is the **factual** answer to "what data does this app collect for diagnostics
or analytics". Use it directly to fill the privacy nutrition labels (Phase 3 Step 7) instead of
presenting a generic "conditional" table or asking the user (who routinely does not know):

- `crash/diagnostics` (e.g. `sentry_flutter`) → declare **Crash Data**, used for App Functionality,
  **Not Linked**, not for tracking.
- `analytics` (e.g. `posthog_flutter`) → declare **Usage Data** accordingly.
- `att/tracking` category present → App Tracking Transparency (`NSUserTrackingUsageDescription`)
  **is** required. An empty `att/tracking` set means ATT is **not** required — state that as a fact.

### Account deletion (drives the Apple deletion-flow requirement — do NOT ask the user)

`account_deletion.likely_present` is a heuristic scan of `lib/` for an in-app deletion flow
(`deleteAccount`, `delete_account`, `auth.admin`, "Konto löschen", etc.). Apple requires account
deletion for any app that creates accounts.

- `likely_present: true` → tell the user the flow **was found** (cite `hints`); treat the
  requirement as satisfied unless the user says otherwise. Do not ask "do you have one?".
- `likely_present: false` → flag as a **blocker** to resolve before Step 11, not a question.

### Ruby / Bundler environment (prevents the #1 first-run failure)

`ruby_env` exposes the fastlane runtime. The most common first-run failure is `bundle exec`
resolving against system Ruby while the project pins a different version via rbenv/rvm:

- `ruby_version_file` set + `rbenv_present: true` → the project uses a pinned Ruby that is **only**
  active in interactive shells. Agent-run `bundle exec` (non-interactive) will silently use system
  Ruby and fail with a bundler-version mismatch. **Prefix every `bundle exec` with the shim PATH**
  (see Phase 2 §2.0). Surface this *before* running any fastlane command, not after it fails.
- `bundler_locked` is the exact bundler version `Gemfile.lock` demands. If the active `bundle -v`
  differs, that is the mismatch to fix — not a fastlane bug.

## What this phase does NOT check

Phase 0 is intentionally scoped to facts readable from disk without network or credentials:

- Does not check App Store Connect for existing app records, build status, or metadata gaps.
- Does not validate certificate expiry or provisioning profile contents.
- Does not check Xcode or Flutter SDK versions against Apple's current minimums.
- Does not verify screenshot specifications or store metadata completeness.

These gaps are filled by Phase 1 (freshness research), Phase 2 (ASC status), and Phase 3 (guided release loop).
