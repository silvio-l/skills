# Phase 0 — Repo Introspection

This phase runs deterministically before any web research or user interaction. It reads
the repo on disk and produces a structured JSON situation report that subsequent phases
consume.

## Running the script

```bash
SCRIPT=~/.claude/skills/ship-to-playstore/scripts/phase0-introspect
python3 "$SCRIPT" "<path-to-flutter-repo>"
```

- Exit 0: Flutter/Android project detected — JSON situation report on stdout.
- Exit 1: Not a Flutter/Android project — warning on stderr, no JSON. Abort with the warning text.
- Exit 2: Usage error.

If exit 1 fires, the repo is iOS-only or not Flutter at all. Point the user at
`ship-to-appstore` for iOS releases, or stop.

## Situation report schema

```json
{
  "flutter_android": true,
  "app_display_name": "my_app",
  "application_id": "com.example.myapp",
  "version_name": "1.2.3",
  "version_code": 42,
  "min_sdk_version": 21,
  "target_sdk_version": 34,
  "gradle": {
    "wrapper_version": "8.5",
    "agp_version": "8.3.0",
    "kotlin_version": "1.9.22",
    "java_toolchain": "17",
    "ndk_version": null
  },
  "signing": {
    "signing_config_set": true,
    "keystore_hints": ["android/key.properties", "android/app/keystore.jks"],
    "has_key_properties": true,
    "play_app_signing_enrollable_from_repo": false
  },
  "icon_set": {
    "complete": true,
    "missing_densities": [],
    "present_densities": ["mdpi", "hdpi", "xhdpi", "xxhdpi", "xxxhdpi"]
  },
  "permissions": {
    "declared": ["android.permission.INTERNET", "android.permission.POST_NOTIFICATIONS", "android.permission.CAMERA"],
    "expected_from_plugins": ["android.permission.INTERNET", "android.permission.CAMERA", "android.permission.POST_NOTIFICATIONS"],
    "excessive": [],
    "missing": []
  },
  "credentials": {
    "service_account_json": [{ "path": "android/api/play-service-account.json" }],
    "fastlane_supplyfile": { "path": "fastlane/Appfile" },
    "env_hints": ["ANDROID_PUBLISHER_SERVICE_ACCOUNT", "GOOGLE_APPLICATION_CREDENTIALS"]
  },
  "fastlane_lanes": ["play_release", "play_beta", "supply"],
  "play_billing": {
    "likely_present": true,
    "packages": ["in_app_purchase"],
    "code_markers": ["InAppPurchase", "queryProductDetails", "BillingClient"]
  },
  "data_safety_hints": {
    "analytics_tracking": [{ "package": "sentry_flutter", "category": "crash/diagnostics" }],
    "account_deletion": { "likely_present": true, "hints": ["deleteAccount"] }
  },
  "user_generated_content": { "likely_present": false, "has_report_or_block": false },
  "push_notifications": { "fcm_used": true, "firebase_in_manifest_only": false },
  "supabase_used": true
}
```

All top-level keys are always present (values may be `null`/empty) so downstream phases can rely on the shape.

## Interpreting findings

Present the situation report to the user as a structured summary. Flag issues clearly.

### Version fields — `version_code` is the monotonic identity (interpretation delta vs. iOS)

Unlike iOS where `build_number` is a per-version counter, **`version_code` is the monotonic identity** on Play.
It must be a strictly-increasing integer across the app's entire lifetime, regardless of `version_name`.

- `version_name`: the human-visible string (e.g. `1.2.3`). Bump freely for marketing.
- `version_code`: **must be strictly greater than the last uploaded version code on the target track**. A collision
  is an upload reject. **Flag it now** and cross-reference against Phase 2's last track version code before any build —
  this is the #1 preventable AAB-upload failure.

### `target_sdk_version` — the annually-incrementing Play floor (cross-ref placeholder)

Play blocks submissions whose `targetSdkVersion` is below the current Play-enforced minimum, which increments yearly.
**The exact current minimum is NOT stated here** — it is Phase 1 freshness research (HARD RULE: no training-memory
values). Surface `target_sdk_version` in the report so Phase 1 can cross-reference it against the live floor and
mark it as a hard blocker before any build. Treat a low `target_sdk_version` as a probable blocker pending Phase 1.

`min_sdk_version` affects device coverage and Play's "minimum Android version" — informational, not a blocker.

### Gradle toolchain — prevents the #1 first-run build failure

`gradle` exposes the wrapper, AGP, Kotlin, Java, and NDK versions. The most common first-run failure is an
AGP/Gradle/Java incompatibility (e.g. AGP 8.x requires Java 17) or a wrapper that isn't `./gradlew`-invoked:

- `wrapper_version` + `agp_version` must be a compatible pair (AGP pins a Gradle range).
- `java_toolchain` must match what AGP demands.
- Phase 2 §9.1 surfaces this up front instead of discovering it via a 5-minute failed build.

### Signing — secret hygiene is absolute (interpretation delta vs. iOS)

`signing.keystore_hints` surfaces **paths only** — `key.properties`, `*.jks`, `*.keystore`. The script **never**
reads `key.properties` (it sits next to `storePassword` / `keyPassword` / `keyAliasPassword`). The **alias name** is
also not extracted from `key.properties` — point the user at the file instead of surfacing its contents.

- `signing_config_set: false` → blocker: no `signingConfig` wired into a build type. Provide the exact `build.gradle`
  block to add (Phase 3 Step 2).
- `has_key_properties: true` → an upload keystore is configured. Good.
- `play_app_signing_enrollable_from_repo: true` → **heuristic hint only** (no keystore evidence found → possible
  first release → Play App Signing enrolment still on the table). Phase 2 determines the **real** enrolment state via
  the Play Console API/UI and overrides this hint. Enrollment is a one-time, irrevocable decision — never treat the
  hint as a verified fact.

Play App Signing is fundamentally different from Apple's model: the app is signed twice (upload key + Google's app
signing key). The upload key can be reset if lost; the app signing key, once enrolled, cannot.

### Icon set

- `complete: false` → list `missing_densities` and ask the user to regenerate via `flutter_launcher_icons`.
- Play reads the launcher icon from `mipmap-<density>/ic_launcher`; missing densities produce a blurry or absent icon
  on some device classes. `ic_launcher.xml` (adaptive icon) counts as present.

### Permissions — `excessive` / `missing` (interpretation delta vs. iOS)

`permissions` is the input to pre-submit **Gate E** (Play *Permissions* policy). Over-declared permissions are a
ranking penalty and possible reject; under-declared ones risk merge breaks.

- `excessive` (declared but no detected plugin needs it) → Play ranking penalty + possible reject. Present as
  **"verify, likely remove"**, not a hard delete — native code may use it.
- `missing` (a detected plugin needs it, not declared) → merge-break / runtime risk. Note: Flutter plugin manifests
  merge their own permissions at build time, so `missing` is a **hint**, not a guaranteed failure — but a permission
  the app's own code requests at runtime with no manifest entry will crash.
- `INTERNET` is baseline-expected for any Flutter app and never flagged as excessive.

### Credentials — paths only, never contents

- `service_account_json[].path` → relative path to a service-account JSON (matched by filename shape). **Never read
  or print the file body** (private key, client email). Phase 2 mints an OAuth2 JWT from it; Phase 0 only confirms
  presence.
- `fastlane_supplyfile` → `fastlane/Appfile` (Fastlane `supply` reads it).
- `env_hints` → env var **names** that are set (e.g. `GOOGLE_APPLICATION_CREDENTIALS`). **Never the values.**

### Fastlane lanes

Prefer project-defined lanes over raw Play API calls. `supply` / `play_release` / `play_beta` lanes encode the
developer's exact wiring. An empty list means no Fastfile → fall back to the Play Developer API strategies (Phase 2).

### `play_billing` — drives the Play-Billing gate + IAP submission gate (do NOT ask the user)

`play_billing.likely_present` is the signal that the Play-Billing gate (§9 H) and the IAP/subscription submission
gate (§8 Step 10b) are in scope at all. Flutter's `in_app_purchase` plugin routes through Play Billing on Android.

- `likely_present: true` → state as a **fact** that Step 10b is required: every product (one-time + subscription, in
  **two namespaces** — `inappproducts` + `monetization.subscriptions`, base plans + offers for subscriptions) must be
  publishable **before** the release commits. Cite matched `packages` / `code_markers`.
- `likely_present: false` → state as a **fact** that the IAP gate is not in scope. Do not ask.

### `data_safety_hints` — drives the Data Safety form (do NOT ask the user)

`data_safety_hints` feeds pre-submit **Gate D** (Data Safety form vs. actual data). Drive the form from these facts,
not a user questionnaire:

- `analytics_tracking` → the factual answer to "what data does this app collect". E.g. `sentry_flutter`
  (`crash/diagnostics`) → declare Crash Data. `posthog`/`analytics` → declare Usage Data.
- `account_deletion.likely_present` → drives the Data Safety **"data deletion provided"** field AND Play's
  account/data-deletion mandate. `true` + no in-app flow → blocker. `false` but app creates accounts → contradiction
  to surface.

### `user_generated_content` — drives the UGC-safety gate (heuristic, verify)

Conservative heuristic (≥2 distinct content-shaped markers). When `true`, Gate L requires a content filter, an
in-app report + block mechanism, and a published EULA. `has_report_or_block` indicates moderation controls were
found. Present as "investigate", not an automatic blocker.

### `push_notifications` + `supabase_used` — stack-fidelity hooks

Per global stack rules: **Supabase** (not Firebase) for auth/DB/storage/realtime; **FCM acceptable as Android push
transport only**.

- `supabase_used: true` → expected. Confirm no broad Firebase SDK use elsewhere.
- `push_notifications.fcm_used: true` + `firebase_in_manifest_only: true` → FCM is transport-only (acceptable).
  `firebase_in_manifest_only: false` with `fcm_used: true` → broad Firebase Dart SDK present; flag as a
  stack-fidelity deviation to review (should be Supabase + FCM-transport, not Firebase-everything).

## What this phase does NOT check

Phase 0 is intentionally scoped to facts readable from disk without network or credentials:

- Does not check Play Console for existing app records, tracks, or metadata gaps (Phase 2).
- Does not validate the current Play `targetSdk` floor (Phase 1 freshness research).
- Does not verify store-listing assets that live only in Play Console (feature graphic, screenshots).
- Does not check Play App Signing enrolment state (Phase 2, via Play Console API/UI).
- Does not read or validate keystore contents, service-account JSON bodies, or token validity.

These gaps are filled by Phase 1 (freshness research), Phase 2 (Play Console status), and Phase 3 (guided release loop).
