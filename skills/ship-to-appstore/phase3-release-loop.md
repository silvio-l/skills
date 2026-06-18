# Phase 3 — Guided Release Loop

Loaded by the orchestrator after Phase 2 delivers the compact situation overview. This phase
drives the user step by step from "project ready to build" to "app live on the App Store."

---

## HARD RULES (inherited from SKILL.md, repeated here for emphasis)

- **One step per round.** Present exactly one release step, explain it, execute any safely-automatable
  part, then **stop and wait**. Never advance without the user's explicit "done" (or request for help).
- **No wall of text.** Keep each step presentation compact: one header, one clear action, one prompt.
- **No autonomous submission.** The submit-for-review button is a human action in the ASC Web UI —
  the skill guides but does not press it.
- **No secrets emitted.** Identifiers (bundle ID, team ID, key ID) may appear in instructions;
  API keys, `.p8` content, and passwords must never be logged, printed, committed, or included in
  the status note.
- **Stack fidelity.** All recommendations use Supabase + Flutter; never propose Firebase for any
  purpose. iOS push notifications use APNs directly — FCM is only an Android transport and is not
  relevant to an iOS App Store release. Never recommend a paid or free-tier-burning third-party
  service as a default — all tools cited here (Xcode, Simulator, altool/notarytool, Transporter)
  are free and bundled with the Apple developer toolchain.

---

## 3.0 — Load Phase State

Before presenting any step, consolidate the three prior outputs:

| Source | What to extract |
|---|---|
| Phase 0 situation report (JSON, already shown) | `bundle_id`, `marketing_version`, `build_number`, `signing_style`, `team_id`, `credentials.*`, `fastlane_lanes`, `analytics_tracking`, `account_deletion`, `in_app_purchases`, `ruby_env`, icon/launch assets |
| Phase 1 freshness report (table, already shown) | Minimum Xcode version, minimum iOS target, required screenshot sizes, privacy requirements, export-compliance rule, current recommended upload tool |
| Phase 2 situation overview (block, already shown) | App record exists?, latest build upload/processing status, metadata completeness gap list, access strategy used |

Construct the **Ordered Release Checklist** (§3.1) from these inputs. Steps already confirmed
complete in the Phase 2 overview are marked ✓ and skipped in the loop.

---

## 3.1 — Build the Ordered Release Checklist

Evaluate each candidate step against the loaded state. Include a step if and only if it is not
yet confirmed complete. Present the resulting list to the user before starting the loop:

```
=== Release Checklist (derived {YYYY-MM-DD}) ===

Marker legend:  ✓ verified done   ? cannot-verify via API (confirm in ASC UI)   □ confirmed open

Remaining steps:
  □ 1.  Version bump
  □ 2.  Signing & certificates
  □ 3.  Build & archive  (flutter build ipa)
  □ 4.  Upload to TestFlight
  □ 5.  Build processing wait
  □ 6.  Store metadata
  □ 7.  Privacy nutrition labels
  □ 8.  Age rating questionnaire
  □ 9.  Export compliance
  □ 10. Screenshots
  □ 10a Pricing & availability        ← first-release blocker if unset
  □ 10b IAPs/submissions ready+attached ← first-release only; each product must be READY_TO_SUBMIT (screenshot!) + attached or 2.1(b) reject
  □ 11. Submit for Review     ← this is on you in ASC
  □ 12. Review period + release options

Steps skipped (confirmed done in Phase 2):
  (list, or "none")

We will work through these one at a time.
Ready? Say "start" or "let's go".
```

Adjust step numbering after filtering confirmed-done steps. Do not show filtered steps in the
checklist — keep the list short and scannable.

**Tri-state, not binary.** A step is "done" (✓) only when Phase 2 returned HTTP 200 + data
confirming it. If the state could not be verified (non-200, or no read endpoint exists — e.g.
privacy publish state, IAP-to-version attachment), mark it `?` and present it as "confirm in the
ASC UI", **never** as an open `□` TODO. Telling the user to redo already-done work is the cardinal
failure of this loop. The **IAP product `state`** (`MISSING_METADATA`, `READY_TO_SUBMIT`, …) *is*
API-readable via `inAppPurchasesV2`, so check it there and only fall back to `?`-confirm for the
"is this product attached to this specific version" relationship. Include **10a (pricing)** and
**10b (IAP submission gate)** for any first release with paid tiers or in-app purchases — both are
blockers that the first real run hit.

---

## 3.2 — Loop Mechanic (state machine)

```
WHILE steps remain in checklist:
    Present current step (§3.3)
    Execute safely-automatable part (commands defined per step below)
    Prompt: "Let me know when step N is done, or 'stuck here: <error>' if you hit a problem."
    WAIT for user reply

    CASE user reply:
        "done" / "next" / "✓"
            → Mark step ✓ in status note (§3.4)
            → Advance to next step

        "stuck here: <error>" / pastes error output
            → Run stuck handler (§3.5)
            → Re-present current step after resolution; do not advance until user confirms fix

        "skip" / "already done"
            → Mark step ✓ (skipped) in status note
            → Advance to next step

        Question (does not start with "done" / "stuck" / "skip")
            → Answer inline, concisely
            → Re-prompt: "Still on step N — done or stuck?"

        "pause" / "stop" / "exit"
            → Write status note update (§3.4)
            → Print resume instructions (§3.6)
            → Stop

ALL steps ✓:
    → Print completion block (§3.7)
```

**Never** advance to the next step inside a stuck handler without the user confirming the
resolution. When in doubt, re-prompt for the same step.

---

## 3.3 — Step Presentation Template

Each step follows this compact format:

```
## Step N — <Title>

**What:** <one sentence — what this step does and why>
**Mode:** <"Automatable — running now" | "Partially automatable — agent checks, you decide" | "Manual — this is on you in ASC">

<One-paragraph context (blocker risk, wait times, common pitfalls)>

<Commands the agent runs automatically, if any>

<If manual: exact Web UI path or shell command for the user>

---
Let me know when step N is done, or "stuck here: <description>" if you hit a problem.
```

---

## 3.4 — Persistent Status Note

**Default path:** `.scratch/ship-to-appstore/status.md`

Create this file on first load (if absent). After every step completion or state change, append
a timestamped line — never overwrite earlier lines. The file is an append-only history; any
future session can read the last few lines to identify where the release was interrupted.

**Security note:** the status note must contain only step identifiers, version strings, and
timestamps. Never write API keys, `.p8` content, Apple IDs, passwords, or any credential secret
to this file. Because it lives under `.scratch/`, add it to `.gitignore` now if not already
present (`echo '.scratch/ship-to-appstore/status.md' >> .gitignore`).

### Format

```markdown
# App Store Release Status — {bundle_id}

## Run started: {ISO-8601 timestamp}

Phase 0: {marketing_version} ({build_number}) — {commit_sha}
Phase 1: researched {YYYY-MM-DD}
Phase 2: access strategy {A|B|C|D}, app record {exists|missing}, last build {processed|pending|none}

---

## Progress log (append-only)

{timestamp} ✓ Step 1  — Version bump: 1.4.2+47 → 1.4.3+48
{timestamp} ✓ Step 2  — Signing: distribution identity confirmed
{timestamp} ✓ Step 3  — Build: flutter build ipa OK, size 42 MB
{timestamp} ✓ Step 4  — Uploaded to TestFlight
{timestamp} ⏸ PAUSED  at Step 5 — waiting for build processing
```

### Resume

When the user re-invokes the skill after a pause, the agent must:

1. Check for an existing status note at the default path.
2. If found, read the last few lines and identify the open step.
3. Present: "Resuming from Step N — {title}. Last note: {last line}. Continue from here?"
4. On confirmation, resume the loop from that step; do not re-run Phase 0/1/2.
5. If no status note is found and Phase 0/1/2 outputs are absent from context, instruct the
   user to re-invoke the full skill so phases run fresh.

---

## 3.5 — Stuck Handler

When the user says "stuck here: <error>" or pastes error output:

1. **Parse and classify.** Match to a known error class (table below) or flag as unknown.
2. **Address it.** Run a diagnostic command if automatable; provide targeted guidance otherwise.
3. **Research if needed.** For unfamiliar or version-specific errors, run a live search before
   guessing from training memory:
   ```
   WebSearch: "flutter build ipa {error keyword} {YYYY}"
   WebSearch: "App Store Connect {error keyword} {YYYY}"
   ```
4. **Confirm resolution.** Ask the user to confirm the fix worked before re-presenting the step.
5. **Log in status note.** Append `{timestamp} ⚠ Step N stuck: {error class} — resolved: Y/N`.

### Known error classes

| Class | Symptoms | First action |
|---|---|---|
| Signing — no identity | "No signing certificate" / "provisioning profile" error | Check identity list (`security find-identity -v -p codesigning`); offer to open Xcode |
| Build number collision | "A build with that number already exists in ASC" | Bump `build_number` in `pubspec.yaml`, retry build |
| Deployment target mismatch | "requires a higher iOS deployment target" | Edit `ios/Podfile` `platform :ios, 'X.Y'` + Xcode `IPHONEOS_DEPLOYMENT_TARGET`; run `cd ios && pod install` |
| CocoaPods conflict | "CocoaPods could not find compatible versions" | `cd ios && pod repo update && pod install` |
| Build processing stalled | Status "Processing" > 60 min in TestFlight | Check [developer.apple.com/system-status](https://developer.apple.com/system-status/); do not re-upload yet |
| Invalid binary (ITMS) | "ITMS-90XXX" code in email or ASC | Classify by code (§3.9); fix and re-upload |
| Missing export-compliance key | "ITSAppUsesNonExemptEncryption" warning | Add plist key (§3.9); rebuild |
| Flutter/Xcode version | "requires Xcode X.Y or later" | Install/select correct Xcode; `xcode-select -s /Applications/Xcode_{version}.app` |
| Metadata blocked | "Missing required field" in ASC | Identify field; guide through the ASC Web UI step |
| Missing pricing | "App is missing required pricing. … not eligible for submission until pricing has been set" | Set a price tier (Free/0 or paid) in ASC → Pricing and Availability; then re-run submit (Step 10a) |
| Bundler/Ruby mismatch | "Could not find 'bundler' (X) required by your Gemfile.lock" | System Ruby is active instead of the pinned one — re-run with `PATH="$HOME/.rbenv/shims:$PATH"` prefix (Phase 2 §2.0); not a fastlane bug |
| Version "not in valid state" | "appStoreVersions … is not in valid state … check associated errors" | A precondition (pricing, privacy, missing metadata) is unmet — read the *associated* error line; it names the real blocker |

---

## Release Steps (Detailed)

---

### Step 1 — Version Bump

**Mode:** Automatable — agent runs the check and proposes the edit.

**What:** Ensure the marketing version (`CFBundleShortVersionString`) and build number
(`CFBundleVersion`) are consistent across `pubspec.yaml` and the Xcode project, and that the
new build number is strictly higher than the last uploaded build in ASC.

```bash
# Read current values from pubspec.yaml
grep '^version:' pubspec.yaml
# Expected format: version: 1.4.2+47
# marketing_version = "1.4.2", build_number = 47
```

The agent reads Phase 0's `marketing_version` / `build_number` fields and Phase 2's "latest
build" number, then proposes:

- If Phase 2 reports no uploaded build: current number is acceptable if ≥ 1.
- If Phase 2 reports a processed build N: new `build_number` must be ≥ N + 1.
- Marketing version: increment the patch or minor component if this release contains user-visible
  changes since the last live version. The agent asks if it is unclear.

The agent applies the updated `version:` line in `pubspec.yaml` via the Edit tool. It then
verifies that `ios/Runner/Info.plist` does **not** hard-code a conflicting version:

```bash
grep -E 'CFBundleShortVersionString|CFBundleVersion' ios/Runner/Info.plist
# Expected: $(FLUTTER_BUILD_NAME) / $(FLUTTER_BUILD_NUMBER)
# If hard-coded values appear: the agent flags this as a manual correction in Xcode
```

---

### Step 2 — Signing and Certificates

**Mode:** Partially automatable — agent checks, you correct in Xcode if needed.

**What:** Confirm that a valid distribution code-signing identity and provisioning profile are
present before attempting the build. A signing error at build time is easier to fix now than
after a long compile.

```bash
# List available distribution identities
security find-identity -v -p codesigning | grep -i "distribution\|developer"

# Check for downloaded provisioning profiles
ls ~/Library/MobileDevice/Provisioning\ Profiles/ 2>/dev/null | wc -l
```

Decision table based on Phase 0 `signing` fields:

| Phase 0 finding | Outcome |
|---|---|
| `code_signing_style: Automatic` + valid Apple Developer Team set | Usually fine; Xcode resolves at build time |
| `code_signing_style: Manual` + `has_provisioning_profile: true` | Verify the profile has not expired (`security cms -D -i ~/Library/MobileDevice/Provisioning\ Profiles/*.mobileprovision \| grep ExpirationDate`) |
| `code_signing_style: Manual` + `has_provisioning_profile: false` | User must create and download a distribution profile from developer.apple.com |

**If manual fix needed:**
1. Open `ios/Runner.xcworkspace` in Xcode.
2. Runner target → Signing & Capabilities → confirm Team is set to the correct Apple Developer account.
3. For Manual signing: download the App Store distribution profile from
   developer.apple.com → Certificates, Identifiers & Profiles → Profiles.

---

### Step 3 — Build & Archive

**Mode:** Automatable — agent runs the command.

**What:** Compile the release IPA from the Flutter project. This binary is what gets
uploaded to TestFlight.

```bash
flutter build ipa --release
```

The agent runs this command and monitors the output. On success, the IPA is at
`build/ios/ipa/{AppName}.ipa`. The agent confirms the path and file size — a result under 1 MB
suggests a misconfigured or empty build and is flagged immediately.

**Common errors and responses (handled by the stuck handler §3.5):**

| Error signal | Response |
|---|---|
| Signing error | Revisit Step 2 checks |
| `pod install` required | `cd ios && pod install && cd ..`, then retry |
| Deployment target error | Edit `ios/Podfile` `platform :ios, 'X.Y'` + Xcode `IPHONEOS_DEPLOYMENT_TARGET` |
| Dart compile error | Show first error line; search live if unfamiliar |
| Build succeeded with exit 1 | Show last 30 lines; identify root cause before retrying |

---

### Step 4 — Upload to TestFlight

**Mode:** Automatable if credentials are available; manual fallback via Xcode Organizer or
Transporter.

**What:** Upload the IPA to App Store Connect so Apple can process the binary for TestFlight
and eventual submission.

The upload method depends on the access strategy established in Phase 2:

**Strategy A — ASC API key (`.p8` + Issuer ID + Key ID):**

```bash
# altool (check Phase 1 for current deprecation status)
xcrun altool --upload-app \
  --type ios \
  --file "build/ios/ipa/{AppName}.ipa" \
  --apiKey {KEY_ID} \
  --apiIssuer {ISSUER_ID}
# The .p8 file is read from ~/.appstoreconnect/private_keys/AuthKey_{KEY_ID}.p8
# (or from APPLE_API_KEY_PATH env var) — the agent references the path, never the content
```

If Phase 1 indicated that `altool` is deprecated in favor of `notarytool` or Transporter CLI,
use the current recommended command from the Phase 1 Freshness Report instead.

**Strategy D fallback — no automated credential available:**

> **This is on you.** Two free options:
> - **Xcode Organizer:** open Xcode → Window → Organizer → Archives → select today's archive →
>   "Distribute App" → "App Store Connect" → follow the wizard.
> - **Transporter.app:** download free from the Mac App Store; drag-and-drop the IPA file.

After initiating the upload, proceed to Step 5.

---

### Step 5 — Build Processing Wait

**Mode:** Manual — no automation possible for the processing itself.

**What:** After upload, ASC processes the binary (dSYM extraction, entitlement checks, notarization).
This is an Apple-side operation; no action is required on your end during this time.

Expected processing time: **5–30 minutes** for most builds. Occasionally up to 60 minutes after a
new Xcode/SDK release or during high-traffic periods. If processing exceeds 2 hours, check
[developer.apple.com/system-status](https://developer.apple.com/system-status/).

**While waiting**, move on to Step 6 (store metadata) — metadata can be filled in at any time and
does not depend on build processing completing.

**Outcomes to watch for:**

| ASC status | Meaning | Action |
|---|---|---|
| "Ready to Submit" / "Ready for TestFlight" | Processing succeeded | Proceed with remaining steps |
| "Invalid Binary" | Build rejected during processing | See §3.9 (ITMS error codes); fix and re-upload |
| No status change after 60 min | Processing queue delay | Check system status; do not re-upload yet |
| Email: "We noticed an issue with your submission" | Rejection during processing | Treat as Invalid Binary — see §3.9 |

---

### Step 6 — Store Metadata

**Mode:** Manual — this is on you in ASC.

**What:** Fill in all required text metadata fields. Submission is blocked until all required
fields are complete and show no red warnings in ASC.

Go to: **App Store Connect → My Apps → {App} → App Store → {Version}**

| Field | Limit | Notes |
|---|---|---|
| App Name | 30 chars | Must match the name registered at app creation |
| Subtitle | 30 chars | Optional but recommended for search visibility |
| Description | 4 000 chars | Communicate user value; avoid promotional superlatives |
| Keywords | 100 chars total, comma-separated | High-value search terms; do not repeat the app name |
| Support URL | Valid `https://` URL | Must be reachable; cannot be a social media link |
| Privacy Policy URL | Valid `https://` URL | Required for all apps that collect user data (applies here — Supabase Auth stores email or phone) |
| Primary Category | Pick from Apple's list | Determines App Store placement |
| Secondary Category | Optional | |
| "What's New" | 4 000 chars | For updates: describe what changed since the previous live version |

Screenshots are covered separately in Step 10. Age rating is set in Step 8.

After filling in all fields, tell the agent "done".

---

### Step 7 — Privacy Nutrition Labels

**Mode:** Manual — this is on you in ASC. Agent provides the Supabase-derived declaration map.

**What:** Declare which data types the app collects and how they are used. Apple displays this
as the "App Privacy" section on the App Store product page. Inaccurate or missing declarations
are a common reject reason.

Go to: **App Store Connect → My Apps → {App} → App Privacy**

**Drive this from Phase 0 facts, not from questions.** Phase 0's `analytics_tracking` already
answers what the app collects for diagnostics/analytics — use it directly:
- a `crash/diagnostics` SDK (e.g. `sentry_flutter`) present → declare **Crash Data** (App
  Functionality, Not Linked, not tracking).
- an `analytics` SDK present → declare **Usage Data**.
- if `analytics_tracking` is empty → declare neither; say so as a fact.

Do **not** ask the user "do you use tracking?" — state what was detected and let them correct it.
The privacy-label **publish state** is not reliably API-readable (Phase 2 §2.3): if you cannot
confirm it, mark `?` and ask the user to check the App Privacy section in ASC — never assert it is
empty from a failed/404 query.

**Supabase-derived declaration map**

This is the standard starting point for a Flutter app using Supabase (auth + database +
storage + realtime). Adjust only where the app's actual behavior differs.

| Data Type | Collected? | Use | Linked to Identity? | Condition |
|---|---|---|---|---|
| Email Address | Yes | Account creation, authentication | Yes | If Supabase email auth is enabled |
| Phone Number | Conditional | Authentication | Yes | Only if Supabase phone auth is enabled |
| User ID (UUID) | Yes | App functionality | Yes | Supabase Auth assigns a UUID per user |
| Name / Display Name | Conditional | App functionality | Yes | Only if the app's DB schema stores a display name |
| Photos or Videos | Conditional | User content | Yes | Only if the app allows uploads to Supabase Storage |
| Device ID | No | — | — | Supabase Dart client does not collect device identifiers by default |
| Crash Data | Conditional | Developer diagnostics | No | Only if Sentry or PostHog is integrated |
| Usage Data | Conditional | Analytics | No | Only if PostHog or a similar analytics SDK is integrated |

**Account deletion** (read Phase 0 `account_deletion`, do not ask blind)

Apple requires that any app allowing account creation also provides an in-app account deletion
flow. Phase 0 already scanned `lib/` for it:
- `account_deletion.likely_present: true` → tell the user the flow **was found** (cite the `hints`,
  e.g. "Konto löschen", `deleteAccount`) and treat the requirement as satisfied unless they say
  otherwise. Do not present it as an open question or TODO.
- `likely_present: false` → flag as a **blocker** before Step 11. The deletion should call the
  Supabase Auth Admin API (`DELETE /auth/v1/admin/users/{id}`) from a server-side path. (Per the
  free-tier discipline, avoid an Edge Function if it can be a Postgres function / client-with-RLS
  path — but a single user-triggered deletion is the rare acceptable Edge-Function case.)

**App Tracking Transparency (ATT)** (read Phase 0 `analytics_tracking`)

ATT is required only when the app tracks users across other companies' apps or websites. If
Phase 0's `analytics_tracking` contains **no** `att/tracking`-category SDK, `NSUserTrackingUsageDescription`
is **not** required — state that as a fact. If one is present (e.g. `facebook_app_events`,
`appsflyer_sdk`), ATT **is** required: the plist key and a runtime prompt must exist.

After completing the privacy questionnaire in ASC, tell the agent "done".

---

### Step 8 — Age Rating Questionnaire

**Mode:** Manual — this is on you in ASC.

**What:** Apple's questionnaire sets the minimum age rating displayed on the App Store product
page. Inaccurate answers trigger review rejection.

Go to: **App Store Connect → My Apps → {App} → App Store → {Version} → Age Rating**

Answer based on the app's actual content:
- For a typical productivity or social app built on Supabase with no violence, sexual content,
  gambling, or horror: all categories answer "None", resulting in a **4+** rating.
- If the app allows unrestricted user-generated content (e.g., open text posts), Apple may
  classify it as 17+ for "Unrestricted Web Access" — read the questionnaire guidance carefully.
- Do not understate content; a mismatch found during review is a rejection.

After saving the questionnaire, the age rating populates automatically. Tell the agent "done".

---

### Step 9 — Export Compliance

**Mode:** Partially automatable — agent checks the `Info.plist` key.

**What:** Declare whether the app uses encryption beyond standard OS-provided HTTPS/TLS. This
is a US export-control requirement (Bureau of Industry and Security); false declarations are a
legal matter, not merely a review rejection.

```bash
grep -A1 'ITSAppUsesNonExemptEncryption' ios/Runner/Info.plist
```

**Standard Supabase/Flutter classification**

A Flutter app that communicates with Supabase exclusively over HTTPS (the default — the Supabase
Dart client uses HTTPS/TLS for all requests, including Realtime WebSocket over TLS) qualifies
as using only standard OS-provided encryption. This means:

- `ITSAppUsesNonExemptEncryption` should be `NO` in `ios/Runner/Info.plist`.
- No ERN (Encryption Registration Number) is required.
- Answer "No" to the export-compliance question in ASC.

If Phase 1's freshness research indicated any change to this classification, that finding takes
precedence over the above.

**If the key is absent from `Info.plist`**, the agent adds it automatically:

```xml
<!-- ios/Runner/Info.plist — insert before the closing </dict> tag -->
<key>ITSAppUsesNonExemptEncryption</key>
<false/>
```

The agent applies this edit via the Edit tool and then rebuilds in Step 3 if the key was
missing and the IPA has not yet been uploaded.

**If the app uses custom encryption** (beyond TLS): answer "Yes" in ASC and follow Apple's
ERN documentation. This is a manual process outside the scope of this guided loop.

---

### Step 10 — Screenshots

**Mode:** Manual — this is on you. Agent provides required sizes from Phase 1.

**What:** Upload all required device screenshots to App Store Connect. Missing required sizes
block submission.

Go to: **App Store Connect → My Apps → {App} → App Store → {Version} → iPhone / iPad**

Required sizes (substituted at runtime from the Phase 1 Freshness Report "Required screenshots"
row — do not use training-memory values here):

```
{Insert from Phase 1 Freshness Report}
```

**Generating screenshots with the iOS Simulator (free, no paid service needed):**

```bash
# 1. Open the Simulator at the correct device size
open -a Simulator
# In Simulator: File → Open Simulator → iOS {version} → {required device model}

# 2. Run the app
flutter run --release

# 3. Capture each required screen
xcrun simctl io booted screenshot ~/Desktop/{screen_name}.png
# Repeat for each screen and each required device size
```

Screenshots are taken at logical resolution by the Simulator (the Simulator sets pixel density
automatically — do not scale manually). Upload via drag-and-drop in the ASC Web UI.

After uploading all required sizes, tell the agent "done".

---

### Step 10a — Pricing & Availability

**Mode:** Manual — this is on you in ASC. Agent verifies via API where possible.

**What:** A price tier must be set before Apple accepts a submission. A **first** release with no
price tier fails at submit with *"App is missing required pricing. — App is not eligible for
submission until pricing has been set."* (the exact error the first real run hit). This is easy to
miss because every other field can be green while pricing is silently unset.

The agent checks the price-schedule relationship via the ASC API if Strategy A is available
(price-schedule exists but with **0** manual prices = unset). Because this is a frequent
first-release blocker, surface it proactively — do not wait for the submit to fail.

**Path:** App Store Connect → {App} → **Pricing and Availability** → choose a price tier
(**Free / 0** for a freemium app whose premium is sold via IAP/subscriptions, or a paid tier) →
set availability (default: all countries) → **Save**.

> For a Supabase + Flutter freemium app (base app free, premium via subscriptions), the base price
> is **Free**. Confirm with the user before assuming paid.

After saving, tell the agent "done".

---

### Step 10b — In-App Purchases / Subscriptions Submitted (first release only)

**Mode:** Manual — this is on you in ASC. Agent reads per-product state via API where
possible; the rest is `?`/confirm.

**What:** On the **first** submission of an app that offers premium content, **every**
IAP/subscription product must be fully completed, attached to the version, and in state
`READY_TO_SUBMIT` **before** the build is submitted. If any product is not at that state,
Apple will approve the binary alone and reject the submission under **Guideline 2.1(b) —
Performance: App Completeness** with *"one or more of the In-App Purchase products have not
been submitted for review"*. The reject is almost always one of:

- the per-IAP **App Review Screenshot** is missing (Apple's reject mail even says *"you must
  provide an App Review screenshot in App Store Connect in order to submit In-App Purchases
  for review"*), or
- the product was never **attached to the version**, or
- another required field is unset so the product is stuck on `MISSING_METADATA`.

**In scope only if Phase 0 reported `in_app_purchases.likely_present: true`.** If Phase 0
reported `false`, say so as a fact and skip this step — do not ask the user.

**Read the current state first.** If Strategy A is available, query
`GET /v1/apps/{id}/inAppPurchasesV2?limit=200` (Phase 2 §2.3 Strategy A, endpoint 5) and list
every product with its `state`. Present the per-product table to the user:

```
IAP gate state:
  lifetime    : READY_TO_SUBMIT   ✓ can submit
  monthly     : MISSING_METADATA  ⚠ blocked — fill required fields (screenshot?)
  yearly      : (not attached)    ⚠ blocked — attach to version
```

Any row that is not `READY_TO_SUBMIT` or `APPROVED` is a **hard blocker** for Step 11 — do
not let the user submit the build until every row is ✓. If the API cannot see the IAPs
(non-200, or subscriptions nested under a group endpoint the key cannot read), classify as
`? cannot-verify` and have the user confirm each product's state in the ASC UI.

**Per-product checklist (ASC → {App} → Monetization → In-App Purchases → open each product):**

For **every** IAP / subscription product, all of:

- Reference Name and **Product ID** set (the Product ID must match what the app code requests
  — cross-check against Phase 0 `in_app_purchases.code_markers` if visible).
- **Cleared for Sale** = on.
- **Price Tier** set (and for subscriptions: a **Subscription Group** exists and the product
  is a member of it).
- **App Store Localization**: Display Name + Description (at least the primary language).
- **App Review Screenshot** uploaded — one screenshot per product, **required** to leave
  `MISSING_METADATA`. This is the single most-missed field.
- **Review Notes** (optional but recommended) + a sandbox-test account if the purchase flow
  is non-trivial.

After the per-product fields are complete, **attach** the products to the version:

**Path:** App Store Connect → {App} → open the version → section **In-App Purchases and
Subscriptions** → **select/add** each product → **Save**.

**The hard gate before Step 11:** every product shows state `READY_TO_SUBMIT` (or already
`APPROVED` from a prior version) **and** is attached to the version. Re-query the API (or have
the user confirm in the UI) and only then proceed.

**Success signal (checked post-submit in §3.7):** once the version is submitted, attached +
ready IAPs flip `READY_TO_SUBMIT → WAITING_FOR_REVIEW`. If they stay on `READY_TO_SUBMIT`
after the build went to review, they were **not** submitted with it — expect a 2.1(b) reject;
recovery is: complete the missing field / attach, upload a new binary, re-submit.

After every product is ✓ and attached, tell the agent "done" (or "confirmed").

---

### Step 11 — Submit for Review

**Mode:** Manual — THIS IS ON YOU. The agent does not and cannot press this button.

**What:** The final action that sends the app to Apple's review team. Once submitted, the
version enters the review queue.

**Pre-submission self-check (agent verifies where possible, user verifies in ASC):**

```
□ Build status in ASC: "Ready to Submit" (not still "Processing")
□ All required metadata fields: no red warnings in ASC
□ Screenshots: all required sizes uploaded for all required devices
□ Privacy nutrition labels: questionnaire saved + label published
□ Age rating: set
□ Export compliance: answered
□ Pricing & availability: a price tier is set (Free or paid)   ← else submit fails
□ IAPs/subscriptions: each product state READY_TO_SUBMIT (screenshot + metadata complete) + attached to the version (first release)  ← else 2.1(b) reject
□ "What's New" text: filled in (for an update release)
□ Privacy policy URL: reachable from a browser
□ Support URL: reachable from a browser
□ Account deletion flow: implemented (Phase 0 account_deletion) — confirmed, not asked
```

Go to: **App Store Connect → My Apps → {App} → App Store → {Version} → "Submit for Review"**

Before clicking "Submit", select the release option (see Step 12 for tradeoffs):
- **Automatically release after Apple's approval**
- **Manually release this version** (you click "Release" in ASC after approval)
- **Automatically release after Apple's approval, with a phased release over 7 days**

After clicking "Submit for Review", the version status changes to "Waiting for Review".
Tell the agent "done".

---

### Step 12 — Review Period + Release Options

**Mode:** Inform only — no action required while in review.

**What:** Apple's review team evaluates the submission. No action is needed during this period
unless Apple requests clarification or issues a rejection.

**Realistic review time expectations**

Apple does not publish SLAs. Community-reported data (see [appreviewtimes.com](https://appreviewtimes.com)
for current averages — this is crowd-sourced, not official):
- Typical: 1–3 days for a standard update.
- Longer: first-time submissions, apps with in-app purchases, apps that Apple's automated
  checks flag for manual review, and submissions during the September–November high-traffic
  period (around iPhone launch season).

**Release option tradeoffs**

| Option | When to choose |
|---|---|
| Automatic release after approval | Fastest time-to-users; Apple publishes immediately after approval |
| Manual release after approval | You want to coordinate the release with a marketing push or prepare your support team before users see it |
| Phased release over 7 days | Safest for an established user base; rolls out to ~1% on day 1, ramps to 100% by day 7; can be paused at any point from ASC if a critical bug appears |

For a solo developer on a first or early release, automatic release is usually appropriate.
Phased release becomes valuable once there is a meaningful installed base to protect.

**After Apple's decision:**
- **Approved:** status changes to "Ready for Sale" (automatic) or "Pending Developer Release"
  (manual). App is live when status is "Ready for Sale".
- **Rejected:** see §3.8. Re-invoke the skill — it will read the status note and enter the
  reject handler immediately.

---

## 3.6 — Resume Instructions

When the user pauses or the session ends before completion, the agent prints:

> "Paused at Step {N} — {title}. Status note updated at
> `.scratch/ship-to-appstore/status.md`. To resume later, re-invoke the
> `ship-to-appstore` skill — it will read the status note and pick up from Step {N}
> without re-running Phase 0/1/2."

---

## 3.7 — Completion Block (all steps done)

When every checklist step is marked done, **verify the submission via API before declaring success
— do not trust the lane's success log alone.** Re-read the version state (Strategy A / `status`
lane) and confirm:

- version is `WAITING_FOR_REVIEW` (or `IN_REVIEW`), and a review submission exists;
- for a first release with IAPs: the products flipped from `READY_TO_SUBMIT` to
  `WAITING_FOR_REVIEW`. If they did **not**, warn loudly — they were not submitted with the
  build (Guideline 2.1(b) reject is incoming: usually a missing App Review screenshot, an
  incomplete metadata field, or the product was not attached to the version). Recovery:
  complete the missing field / attach in the UI, upload a new binary, re-run the release lane.

Then print:

```
=== Release submitted ===

Steps completed: {N}
Build submitted: {marketing_version} ({build_number})
Status note: .scratch/ship-to-appstore/status.md

What to expect:
  - Apple review: 1–3 days typical (check appreviewtimes.com for current data)
  - You will receive an email on approval or rejection
  - On rejection: re-invoke the skill — it enters the reject handler (§3.8)
  - On approval (manual release): go to ASC and click "Release"
  - Status becomes "Ready for Sale" once live
```

Append to the status note:
```
{timestamp} ⏳ SUBMITTED for review — {marketing_version} ({build_number})
```

---

## 3.8 — Reject Handling

A rejection is **not** a process abort — it is a new feedback loop. When the user reports that
Apple rejected the submission:

### 3.8.1 — Obtain the reject details

```
Apple sends an email with the rejection reason(s) and a link to the Resolution Center.
App Store Connect → My Apps → {App} → App Store → Resolution Center

Please paste the full rejection message here so I can classify the reason(s) and
build a correction plan.
```

### 3.8.2 — Classify the reject reason

| Reject category | Common causes | Typical correction |
|---|---|---|
| **2.1 — Performance: App Completeness** | Crash on launch, broken flows, placeholder content | Fix the crash/content; rebuild (Step 3) and re-upload (Step 4) |
| **2.1(b) — App Completeness (IAP not submitted)** | *"one or more of the In-App Purchase products have not been submitted for review"*; app references premium but the IAPs went to review alone | Per-IAP: complete metadata + **App Review screenshot** → state `READY_TO_SUBMIT`; attach to version; **upload a new binary**; re-submit (Step 10b → Step 3 → Step 11) |
| **2.3 — Accurate Metadata** | Screenshots don't match the app; misleading description | Update screenshots (Step 10) or description (Step 6) |
| **3.1.1 — In-App Purchase** | Offers paid features without Apple IAP | Add Apple IAP or remove paid features |
| **4.0 — Design** | Non-standard UI patterns; private API usage | Remove private API calls; follow Apple Human Interface Guidelines |
| **5.1.1 — Privacy: Data Collection and Storage** | Missing privacy policy; inaccurate nutrition labels; ATT prompt missing | Update privacy policy URL (Step 6); correct nutrition labels (Step 7); add ATT prompt if required |
| **5.1.2 — Privacy: Data Use and Sharing** | App collects more data than declared | Update nutrition labels to match actual Supabase data flows |
| **5.1.5 — Account Sign-In** | App offers third-party social login without Sign in with Apple | Add Sign in with Apple alongside existing Supabase social auth options |
| **5.6 — Developer Code of Conduct** | Inappropriate content | Review content moderation and App Review Guidelines §5.6 |
| **Account deletion missing** | App creates accounts (Supabase Auth) but provides no in-app deletion | Implement deletion flow via Supabase Auth Admin API; rebuild and re-upload |
| **Binary rejection (ITMS)** | `ITMS-90XXX` error codes from processing | See §3.9; fix the binary issue; rebuild (Step 3) and re-upload (Step 4) |

### 3.8.3 — Schedule correction steps

After classification, present a compact correction checklist (same one-step-at-a-time mechanic
as the main loop). Example for a 5.1.1 rejection:

```
=== Correction Plan (Reject: Guideline 5.1.1) ===

□ C1. Implement in-app account deletion flow (code change — Supabase Auth Admin API)
□ C2. Update privacy nutrition labels in ASC to reflect actual data collection
□ C3. Rebuild + upload new binary (Steps 3 → 4)
□ C4. Reply to Apple reviewer in ASC Resolution Center
□ C5. Re-submit for review (Step 11)
```

Work through correction steps exactly like the main release steps: one at a time, wait for
user confirmation, record every step in the status note.

### 3.8.4 — Replying to the reviewer

After making all corrections, reply in the Resolution Center **before** re-submitting. A brief,
professional summary of what was changed and where can shorten the re-review time. The agent
can draft this reply if the user provides the full rejection text.

Append to the status note:
```
{timestamp} ✗ REJECTED — reason: {category} — correction plan: {N} steps
{timestamp} ✓ C1 — account deletion flow implemented
...
{timestamp} ⏳ RE-SUBMITTED for review
```

---

## 3.9 — ITMS Binary Error Codes

Common `ITMS-90XXX` codes encountered during TestFlight processing or at submission:

| Code | Meaning | Fix |
|---|---|---|
| ITMS-90167 | No architectures found in binary | Ensure `flutter build ipa --release` completed without signing errors; check export options |
| ITMS-90362 | Invalid provisioning profile | Re-download distribution profile; confirm bundle ID matches exactly |
| ITMS-90535 | Unexpected CFBundleExecutable key in embedded framework | Verify embedded framework `Info.plist` files are not malformed |
| ITMS-90689 | Binary built with outdated Xcode version | Switch Xcode via `xcode-select -s /Applications/Xcode.app`; rebuild |
| ITMS-90725 | SDK version too low for current App Store minimum | Update iOS deployment target (check Phase 1 minimum); rebuild |
| ITMS-90809 | Deprecated API (UIWebView) in binary or a plugin | Run `flutter pub upgrade`; check for plugin updates that remove UIWebView; rebuild |
| ITMS-90899 | Missing or invalid `ITSAppUsesNonExemptEncryption` | Add `<key>ITSAppUsesNonExemptEncryption</key><false/>` to `ios/Runner/Info.plist` (Step 9); rebuild |
| ITMS-91053 | Missing privacy manifest (`PrivacyInfo.xcprivacy`) | Add `PrivacyInfo.xcprivacy` to the Xcode project; check Flutter plugin documentation for required privacy manifests; rebuild |

For any unlisted code, run a live search before acting:

```
WebSearch: "ITMS-{CODE} App Store Connect flutter {YYYY}"
```

---

## 3.10 — Stack Fidelity Summary

These constraints are binding throughout Phase 3. The agent enforces them proactively.

- **Supabase Auth** for user authentication and session management — never Firebase Auth.
  Any step involving user accounts (account deletion, session tokens, social login) uses the
  Supabase Auth API.
- **APNs** for iOS push notifications — not FCM, not Firebase Cloud Messaging. FCM is an
  Android-only transport concern and is not part of an iOS App Store release.
- **Free tools only.** All commands cited — `flutter build ipa`, `xcrun altool`/`notarytool`,
  Transporter, iOS Simulator — are free and bundled with Xcode or Flutter. No paid CI
  pipeline, no paid screenshot service, no paid upload tool is recommended as a default.
- **No secrets emitted.** The agent references credential files by path only. API keys, `.p8`
  file content, Apple ID passwords, and app-specific passwords must never appear in agent
  messages, command output displayed to the user, the status note, or any committed file.
  If a command would print a secret to stdout, the agent instructs the user to run it
  directly in their terminal without relaying the output.
