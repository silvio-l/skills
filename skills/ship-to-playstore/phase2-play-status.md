# Phase 2 — Play Console Status + Credential Discovery

Loaded by the orchestrator after Phase 1 freshness research. Covers the Gradle/Java toolchain
precheck, service-account credential discovery, strategy ordering, tri-state discipline, and
the situation-overview block. The bundled `scripts/play-status` executes the actual read path;
this file is the agent-facing guide for interpreting its output and for deciding how to invoke it.

---

## 1. Toolchain precheck (PRD §9.1)

Run before any build attempt. The #1 first-run failure is an AGP/Gradle/Java incompatibility
(e.g. AGP 8.x requires Java 17) or a wrapper that is not invoked via `./gradlew`. Surface these
blockers up-front, not after a 5-minute build.

```bash
# Confirm all three tools are on PATH
command -v flutter && command -v java && command -v gradle \
  || echo "MISSING toolchain — install before proceeding"

# Read gradle-wrapper.properties; warns on AGP/Gradle mismatch
./android/gradlew --version

# Java version must match android.compileOptions / java toolchain
java -version
```

Cross-reference Phase 0's `gradle.*` fields against the toolchain output:

| Phase 0 field | Check |
|---|---|
| `gradle.wrapper_version` | Matches `gradlew --version` output |
| `gradle.agp_version` | Phase 1 freshness research carries the current AGP/Gradle compatibility matrix — do not assert compatibility from training memory |
| `gradle.java_toolchain` | `java -version` output must match the configured toolchain |
| `gradle.kotlin_version` | Cross-check Kotlin Gradle plugin compatibility with the Gradle wrapper version |

**Prerequisites for `scripts/play-status`:** Python 3 (stdlib only) and `openssl` on PATH. The
script RS256-signs the JWT assertion via `openssl dgst -sha256 -sign`; the private key is passed
on stdin and is never written to disk. Confirm `openssl` is available before invoking:

```bash
openssl version
```

---

## 2. Credential discovery (PRD §9.2)

### 2.1 Discovery order

1. **Repo — Phase 0 already found it.** Check `credentials.service_account_json[].path` in the
   Phase 0 JSON. Phase 0 looks for `android/api/play-service-account.json` (the canonical in-repo
   location — see §2.2). If found, pass this path to `scripts/play-status` via `--service-account`.

2. **Local env — names only, never values.** Phase 0 also reports `credentials.env_hints`.
   Present only the **names** of the following env vars when they are set; never read or print
   their values — they are file paths to a service-account JSON, not the JSON itself:
   - `ANDROID_PUBLISHER_SERVICE_ACCOUNT`
   - `GOOGLE_APPLICATION_CREDENTIALS`
   - `PLAY_STORE_SERVICE_ACCOUNT`
   - `PLAY_CONFIG_JSON`

   `scripts/play-status` resolves `GOOGLE_APPLICATION_CREDENTIALS` and `PLAY_CONFIG_JSON` to a
   file path internally; the values never surface in output.

3. **Out-of-repo fallback.** If no in-repo path and no env var, check
   `~/.config/play/play-service-account.json` (this skill's out-of-repo convention).

4. **Ask (pointed).** When a service-account JSON is provably absent from all three sources:
   explain it is a one-time setup — create a service account in Google Cloud Console, enable the
   Play Developer API, download the JSON key, and link the service account in Play Console →
   Users and permissions → grant app-level permissions. Note: unlike Apple's `.p8`, the JSON
   **can be re-downloaded** from Google Cloud Console if lost.

### 2.2 Service-account JSON location convention (OQ1 — locked)

- **In-repo (gitignored):** `android/api/play-service-account.json`
  The `android/api/` path is Phase 0's canonical detection target. This file **must** be listed
  in `.gitignore` — the JSON contains an RSA private key. Phase 0 verifies `.gitignore` covers
  this path and reports it as `credentials.service_account_json[].path`.
- **Out-of-repo alternative:** `~/.config/play/play-service-account.json`
  Unlike Apple's `.p8`, the service-account JSON can be re-downloaded from Google Cloud Console,
  so an out-of-repo copy is an equally valid primary source.
- **`key.properties` / keystore — never read for passwords.** Phase 0 surfaces keystore paths and
  alias presence only. The passwords in `key.properties` (`storePassword`, `keyPassword`,
  `keyAliasPassword`) are **never** read, logged, or emitted by any phase of this skill. The
  signing section in the Phase 0 report carries only `signing_config_set` and `keystore_hints`
  (relative paths).

---

## 3. Strategy ordering (PRD §9.3)

Lane-first, mirroring the iOS posture (OQ2 — locked):

| Priority | Strategy | When |
|---|---|---|
| **A — Fastlane `supply`/`play_*` (preferred)** | Run `bundle exec fastlane run supply --skip_upload_*` for a dry-run read | Phase 0 `fastlane_lanes` contains `supply` or any lane starting with `play_` |
| **B — `scripts/play-status` (raw Play API)** | Mint an OAuth2 token from service-account JSON; GET tracks/IAP/listings/appDetails | No qualifying Fastlane lane found |
| **C — `bundletool` / `aapt2` local** | AAB inspection only — `versionCode`, permissions, min/targetSdk | No credentials at all; local AAB available |
| **D — Play Console web UI guidance** | Pointer to the Console path for each check | Always-available fallback |

`scripts/play-status` reports the recommended strategy letter in the situation overview regardless
of which path the agent chose. When Strategy A is used (Fastlane lane), `play-status` is still
available for supplemental checks; the strategy letter in the overview reflects the primary read
path.

**OQ2 decision:** Fastlane `supply`/`play_*` is preferred when present because it may cover auth
and state management via `Supplyfile` / `Appfile` without requiring the agent to handle the
service-account JSON separately. If the Fastlane lane exists but cannot authenticate (e.g. the
`Appfile` references a JSON that is absent), fall back to Strategy B.

---

## 4. Tri-state discipline and cardinal errors (PRD §9.4)

Every read result is one of three states. Never collapse them:

| Marker | Meaning | Render |
|---|---|---|
| `✓ verified` | HTTP 200 — real data in hand | `✓` or the data value |
| `? cannot-verify` | Non-200, missing credentials, or out-of-scope query | `? cannot-verify (likely cause)` |
| `□ confirmed-open` | HTTP 200 + data explicitly confirms the item is absent (e.g. empty track, no IAP) | `none` |

### 4.1 The cardinal errors to avoid

1. **Swallowing HTTP 403/404 to an empty `{}`.**
   - HTTP 403 = wrong scope (`androidpublisher` not in the token's scope) **or** the service
     account is not linked in Play Console (the single most common failure). Always surface as
     `? cannot-verify (wrong scope or service account not linked in Play Console)`.
   - HTTP 404 = app not found, package name mismatch, or the Play Developer API is not enabled
     for the Google Cloud project. Always surface with the likely cause.

2. **Treating "not queryable" as "not done".**
   The following facts are partially or not API-readable — classify them as `? cannot-verify`
   and point the user at Play Console UI. Never report them as "missing" or "not done":
   - **Play App Signing enrolment state** — partially exposed; the definitive enrolled/not-enrolled
     fact is UI-only (Play Console → Setup → App signing). First-release enrolment is a one-time,
     irrevocable decision (see Phase 3 Step 2).
   - **Data Safety published state** — the form contents are draftable from Phase 0 facts; the
     published state is not reliably readable via the API.
   - **Policy decision text** — reject / suspension notices cite policy names and decision text
     that is not reliably API-readable. Have the user paste the text; classify it via Gate C
     (Phase 3 reject handler).
   - **Pre-launch report verdict** — Play auto-runs instrumentation on internal builds; the report
     surfaces in Console, not via a clean API read. The skill warns, does not block, on it.

---

## 5. Situation overview (PRD §9.5)

Run `scripts/play-status` and present the output verbatim. Its exit code is 0 on success (even
when credentials are absent — the overview still renders with `? cannot-verify` cells). Exit
code 2 is a usage error; inspect stderr for the cause.

```bash
# Minimal invocation (credentials auto-discovered, no edit-scoped reads)
python3 scripts/play-status com.example.myapp --report phase0-report.json

# With an existing edit id (enables tracks/listings/appDetails reads)
python3 scripts/play-status com.example.myapp \
  --report phase0-report.json \
  --edit-id <editId> \
  --debug
```

The situation overview has this shape (PRD §9.5):

```
=== Google Play Console: Situation Overview ===

App record
  Application ID  : com.example.myapp
  App exists      : yes | no | ?
  Live prod ver   : versionName (versionCode) | none | unknown

Tracks
  Internal        : v1.2.3 (42) (completed) | none | ? cannot-verify (…)
  Closed          : …
  Open            : …
  Production      : v1.2.2 (40) (inProgress) — rollout 10% | none | unknown

Signing
  Play App Signing enrolled : ? confirm in Console
  Upload keystore configured: yes (android/key.properties) | no → blocker

Listing & metadata
  Store listing   : complete (N locale(s)) | missing fields | unknown
  Feature graphic : set | missing | unknown
  Screenshots     : complete | N configs missing | unknown
  Privacy Policy  : set | missing | unknown

  Data Safety form : published | draft | ? cannot-verify (confirm in Console)
  Content rating   : completed (IARC) | not started | ? cannot-verify
  Pricing          : set | NOT SET (blocks production) | ? cannot-verify
  Play Billing (one-time) : pro_unlock=published | none | ? cannot-verify (…)
  Play Billing (subs)     : monthly=published | none | ? cannot-verify (…)
                   ← any product not publishable → Step 10b hard blocker

  Stack fidelity   : FCM transport-only ✓ | ⚠ Firebase SDK beyond push detected | no FCM detected

  Access strategy  : A (Play Developer API) | B (supply) | C (bundletool) | D (Web UI)
```

### 5.1 Reading the overview

- **Tracks without `--edit-id`:** All four track cells read `? cannot-verify (edit-scoped — pass
  --edit-id)`. Tracks are edit-scoped in the Play API; creating an edit is `play-submit`'s job
  (slice 04). To read tracks without a mutation, obtain an edit id out-of-band (e.g. from a
  recent `play-submit --dry-run` output) and pass it here.
- **Both IAP namespaces always queried.** `scripts/play-status` queries `inappproducts` (one-time
  products) and `subscriptions` (auto-renewing, `monetization.subscriptions`) in every invocation.
  An app with only subscriptions will correctly show `Play Billing (one-time): none` rather than
  "no IAP" — the same trap as the iOS v2/subscriptions split.
- **Subscriptions need base plans.** A subscription with no base plan cannot be published. The
  Step 10b blocker fires on any subscription that is not publishable (see `play-api-reference.md`
  §5.1).
- **Upload keystore `no → blocker`:** Phase 0 detected no `signingConfig` and no keystore hints
  → the app cannot be signed for upload. Phase 3 Step 2 must be resolved before proceeding.

---

## 6. Stack fidelity (PRD §4.2)

The overview's `Stack fidelity` line is derived from Phase 0's `push_notifications` fact:

- `firebase_in_manifest_only: true` + `fcm_used: true` → `FCM transport-only ✓` — acceptable per
  the global stack rule: FCM is the Android push transport and its use is unavoidable for that
  purpose. No other Firebase SDK use is assumed.
- `firebase_in_manifest_only: false` + `fcm_used: true` → `⚠ Firebase SDK beyond push detected`
  — flag for review. The global rule (Supabase for auth/DB/storage/realtime, no Firebase SDK for
  other purposes) is potentially violated; the agent must surface this before Phase 3.
- `fcm_used: false` → `no FCM detected` — no push or alternative transport; no stack-fidelity issue.

**Decision note:** FCM as Android push transport is the only accepted Firebase usage in this skill.
Any other `google-services.json` dependency (Firebase Analytics, Crashlytics, Remote Config,
Realtime Database, Firestore, Firebase Auth) is a stack-fidelity violation. Phase 0's
`push_notifications.firebase_in_manifest_only` distinguishes push-only (`google-services.json`
for FCM token only) from broader SDK use.
