# Phase 3 — Guided Release Loop (Play Store)

Loaded by the orchestrator after Phase 2 delivers the situation overview. This phase drives the
user step by step from "project ready to build" to "app live on Google Play."

---

## HARD RULES (inherited from SKILL.md)

- **One step per round.** Present exactly one release step, explain it, execute any safely-
  automatable part, then **stop and wait**. Never advance without the user's explicit "done."
- **No wall of text.** Keep each step presentation compact: one header, one clear action, one prompt.
- **Full API power, every mutation a discrete opt-in checkpoint (PRD §4.1).** Unlike Apple,
  Play allows the entire release flow via the API — production included. The skill exercises this
  power, but every mutation (upload / release / commit) is a separate `--yes` checkpoint.
  `scripts/play-submit` is dry-run by default; `scripts/play-status` is read-only.
- **No secrets emitted.** Keystore passwords, service-account JSON contents, and OAuth tokens
  must never be logged, printed, committed, or included in the status note.
- **Stack fidelity.** Supabase (not Firebase) for auth/DB/storage/realtime. FCM is only an
  Android push transport. All tools cited (flutter, gradle, bundletool, Play Developer API)
  are free.

---

## 3.0 — Load Phase State

Before presenting any step, consolidate prior phase outputs:

| Source | What to extract |
|---|---|
| Phase 0 JSON | `application_id`, `version_name`, `version_code`, `signing.*`, `gradle.*`, `credentials.*`, `fastlane_lanes`, `permissions`, `play_billing`, `data_safety_hints`, `push_notifications` |
| Phase 1 freshness report | targetSdk floor, AAB rules, screenshot specs, Data Safety form state |
| Phase 2 situation overview | Tracks (existing version codes per track), signing enrolled?, listing gaps, strategy letter, IAP product states |

Construct the **Ordered Release Checklist** (§3.1) from these inputs. Steps already confirmed
complete in the Phase 2 overview are marked ✓ and skipped in the loop.

---

## 3.1 — Ordered Release Checklist (this slice: Steps 0–4, 10a, 11, 12)

```
=== Release Checklist (derived YYYY-MM-DD) ===
Marker legend:  ✓ verified   ? cannot-verify (confirm in Play Console)   □ confirmed open

Remaining steps (slice 4 — binary→track→commit spine):
  □ 0.  Pre-flight gate (toolchain · AGP/Gradle/Java · targetSdk floor · signing)
  □ 1.  Version bump (versionName + versionCode — strictly > last track code)
  □ 2.  Signing (upload keystore · Play App Signing enrolment for first release)
  □ 3.  Build AAB (flutter build appbundle --release)
  □ 4.  Upload AAB (scripts/play-submit --yes upload — dry-run default)
  □ 5.  Store listing + assets          ← slice 05
  □ 6.  Data Safety form                ← slice 05
  □ 7.  Content rating (IARC)           ← slice 05
  □ 8.  Privacy Policy URL              ← slice 05
  □ 9.  Pricing / availability          ← slice 05
  □ 10a Choose track + staged rollout fraction
  □ 10b Play Billing catalog ready      ← slice 05 (if play_billing.likely_present)
  □ 10c Pre-submit verification gates   ← slice 05
  □ 11. Release to track + commit (scripts/play-submit --yes release --yes commit)
  □ 12. Rollout monitoring + halt/promote

Steps skipped (confirmed done in Phase 2):
  (list from Phase 2 overview, or "none")

We will work through steps 0–4, 10a, 11, 12 one at a time.
Ready? Say "start" or "let's go".
```

**Tri-state, not binary.** A step is ✓ only when Phase 2 returned HTTP 200 + data confirming
it. Cannot-verify → mark `?` and guide the user to Play Console, never assert "not done."

---

## 3.2 — Loop Mechanic (state machine)

```
WHILE steps remain in checklist:
    Present current step (§3.3)
    Execute any safely-automatable part
    Prompt: "Let me know when step N is done, or 'stuck here: <error>' if you hit a problem."
    WAIT for user reply

    CASE user reply:
        "done" / "next" / "✓"
            → Mark step ✓ in status note (§3.4)
            → Advance to next step

        "stuck here: <error>" / pastes error output
            → Run stuck handler (§3.5)
            → Re-present current step; do not advance until user confirms fix

        "skip" / "already done"
            → Mark step ✓ (skipped) in status note
            → Advance to next step

        Question
            → Answer inline, concisely
            → Re-prompt: "Still on step N — done or stuck?"

        "pause" / "stop" / "exit"
            → Write status note update (§3.4)
            → Print resume instructions (§3.6)
            → Stop

ALL steps ✓:
    → Print completion block (§3.7)
```

**Never** advance inside a stuck handler without user confirmation of the fix.

---

## 3.3 — Step Presentation Template

```
## Step N — <Title>

**What:** <one sentence — what this step does and why>
**Mode:** <"Automatable" | "Partially automatable" | "Manual — this is on you in Play Console">

<One-paragraph context (blocker risk, Play-specific pitfalls, how this differs from iOS)>

<Commands the agent runs, if any>

<If manual: exact Play Console path or shell command for the user>

---
Let me know when step N is done, or "stuck here: <description>" if you hit a problem.
```

---

## 3.4 — Persistent Status Note

**Default path:** `.scratch/ship-to-playstore/status.md`

Create this file on first load (if absent). After every step completion or state change,
append a timestamped line — never overwrite earlier lines. The file is append-only history;
any future session reads the last few lines to identify where the release was interrupted.

**Security note:** the status note holds **only** step identifiers, version strings, track names,
rollout fractions, and timestamps. Never write keystore passwords, service-account JSON
contents, or OAuth tokens. Because it lives under `.scratch/`, ensure it is gitignored:

```bash
grep -qxF '.scratch/ship-to-playstore/status.md' .gitignore \
  || echo '.scratch/ship-to-playstore/status.md' >> .gitignore
```

### Format

```markdown
# Google Play Release Status — {application_id}

## Run started: {ISO-8601 timestamp}

Phase 0: {version_name} ({version_code}) — {commit_sha}
Phase 1: researched {YYYY-MM-DD}
Phase 2: access strategy {A|B|C|D}, app record {exists|missing}

---

## Progress log (append-only)

{timestamp} ✓ Step 0  — Pre-flight: toolchain OK, targetSdk 35 OK
{timestamp} ✓ Step 1  — Version bump: 1.2.3 (41) → 1.2.4 (42)
{timestamp} ✓ Step 2  — Signing: upload key confirmed; first-release enrolment confirmed
{timestamp} ✓ Step 3  — Build: flutter build appbundle OK
{timestamp} ✓ Step 4  — Upload: versionCode 42, track internal
{timestamp} □ Step 10a — Track selected: internal; promoted to production at 0.01
{timestamp} ⏸ PAUSED  at Step 11 — pending --yes release --yes commit
```

### Resume

When the user re-invokes the skill after a pause:

1. Check for an existing status note at the default path.
2. If found, read the last few lines and identify the open step.
3. Present: "Resuming from Step N — {title}. Last note: {last line}. Continue from here?"
4. On confirmation, resume the loop from that step; do not re-run Phase 0/1/2.
5. If no status note and Phase 0/1/2 outputs are absent, instruct the user to re-invoke the
   full skill so phases run fresh.

---

## 3.5 — Stuck Handler

When the user says "stuck here: <error>" or pastes error output:

1. **Parse and classify.** Match to a known error class (table below) or flag as unknown.
2. **Address it.** Run a diagnostic command if automatable; provide targeted guidance otherwise.
3. **Research if needed.** For unfamiliar errors, run a live search before guessing:
   ```
   WebSearch: "flutter build appbundle {error keyword} {YYYY}"
   WebSearch: "Google Play Developer API {error keyword} {YYYY}"
   ```
4. **Confirm resolution.** Ask the user to confirm before re-presenting the step.
5. **Log in status note:** `{timestamp} ⚠ Step N stuck: {error class} — resolved: Y/N`

### Known error classes

| Class | Symptoms | First action |
|---|---|---|
| Signing not configured | `play-submit` prints "BLOCKER: signing_config_set is false" | Add signingConfig to `android/app/build.gradle`; wire `key.properties`; rebuild |
| versionCode collision | `play-submit` prints "COLLIDES: target track already has codes" | Increment `versionCode` in `android/app/build.gradle` / `pubspec.yaml`; rebuild |
| AGP/Gradle/Java mismatch | `./gradlew assembleRelease` fails on JDK version | Check `android/gradle/wrapper/gradle-wrapper.properties`; `java -version` must match AGP requirements |
| targetSdk below floor | Play rejects the upload: "minimum targetSdk" | Update `targetSdk` in `android/app/build.gradle` + Phase 1 freshness floor; rebuild |
| Service account not linked | 403 on every Play API call | Play Console → Setup → API access → Link service account; grant permissions |
| AAB too large | Upload fails at Google's size limit | Enable Play Asset Delivery / Feature Delivery; check Phase 1 for current limit |
| First-release Play App Signing | Prompted in Play Console after first upload | See Step 2 guidance: accept enrolment (one-time, irrevocable), then continue |
| bundletool verify failure | `bundletool dump manifest` shows wrong versionCode | AAB not rebuilt after version bump; run `flutter build appbundle --release` again |
| Edit expired | `edits.insert` 400 with "editId expired" on a re-run | Old editId timed out; re-run `play-submit` (it opens a fresh edit automatically) |
| Network error (token mint) | `play-submit` prints "token mint failed: network/transport error" | Check internet connectivity; verify `openssl` is on PATH |

---

## Release Steps (Detailed — this slice: Steps 0–4, 10a, 11, 12)

---

### Step 0 — Pre-flight Gate

**Mode:** Automatable — agent runs read-only checks before any expensive build.

**What:** Catch failures that otherwise abort a build after a multi-minute compile. Run these
gates cheaply before Step 3. The most common Play first-run failures:

- AGP/Gradle/Java incompatibility (e.g. AGP 8.x requires Java 17).
- `targetSdk` below Play's current minimum (Phase 1 freshness floor — never from training memory).
- Signing not configured in `build.gradle`.

```bash
# 1. Toolchain present
command -v flutter && command -v java && command -v gradle \
  || echo "BLOCKER: missing toolchain — install before proceeding"

# 2. Gradle wrapper resolves and AGP/Java are compatible
./android/gradlew --version

# 3. Java version (must match android.compileOptions / java toolchain in build.gradle)
java -version

# 4. Signing config presence (path only — never print key.properties contents)
grep -r "signingConfig\|key.properties" android/app/build.gradle \
  || echo "WARNING: no signingConfig detected in build.gradle — Step 2 will surface this"

# 5. targetSdk vs Phase 1 floor (substitute floor from freshness report)
grep targetSdkVersion android/app/build.gradle
```

Cross-reference Phase 0 `gradle.*` fields + Phase 1 freshness table. Any BLOCKER is a hard
stop: fix it before advancing to Step 1.

---

### Step 1 — Version Bump

**Mode:** Automatable — agent checks and proposes the edit.

**What:** Increment `versionName` (human label) and `versionCode` (monotonic int identity).
The `versionCode` must be strictly greater than the last code on the **target track** — Play
rejects equality. This is the Android-specific delta from iOS (where build number semantics
differ): `versionCode` is Play's identity.

```bash
# Read current values
grep -E "versionCode|versionName" android/app/build.gradle

# Verify the AAB carries the correct versionCode (bundletool, if installed)
# Replace path with actual output path
java -jar bundletool.jar dump manifest \
  --bundle build/app/outputs/bundle/release/app-release.aab \
  | grep versionCode
```

The agent reads Phase 0's `version_code` and Phase 2's existing track codes, then proposes:

- If no existing code on the target track: current `versionCode` is acceptable if ≥ 1.
- If Phase 2 shows a max code N on the target track: new `versionCode` must be N + 1 or higher.
- Bump `versionName` for any user-visible change since the last release.

Apply the edit to `android/app/build.gradle` and, if `pubspec.yaml` tracks the version, there too.

---

### Step 2 — Signing

**Mode:** Partially automatable — agent checks; you action in Play Console on first release.

**What:** Confirm the upload keystore is configured and, for the **first release**, enrol in
Play App Signing. This step has a critical Android delta from iOS: **Play App Signing is a
one-time, irrevocable decision** (OQ4, locked in this slice).

**Phase 0 `signing` fields drive this step** — do not ask the user what they have; state
what was detected:

```bash
# Confirm key.properties exists (path only — never print its contents)
ls android/key.properties 2>/dev/null \
  && echo "key.properties present" \
  || echo "WARNING: key.properties not found — signing will fail at build time"

# Confirm signingConfig is wired in build.gradle
grep -A5 "signingConfigs" android/app/build.gradle
```

**First-release enrolment sub-step (Step 2a — OQ4, inline):**

If Phase 0's `signing.play_app_signing_enrollable_from_repo` is `true`, or the app has no
prior release, guide the first-release enrolment:

1. Upload the first AAB (Step 4 with `--yes upload`).
2. Play Console shows a prompt: "Let Google manage and protect your app signing key."
   **Accept.** This is the enrolment. Once done, Google holds the app signing key.
3. Your upload key (in `key.properties`) only signs the AAB you upload to Google. The upload
   key **can be reset** via Play Console if lost — this is safe. The app signing key held by
   Google cannot be lost.
4. After enrolment: confirm in Play Console → Setup → App signing that both keys are shown.

**Subsequent releases:** upload key suffices. No Play Console action needed here.

**If `signing_config_set == false`:** hard blocker. `play-submit` will surface the
`build.gradle` block to add. Do not proceed until signing is configured.

---

### Step 3 — Build AAB

**Mode:** Automatable — agent runs the command.

**What:** Build the release Android App Bundle (AAB). AAB is mandatory for new apps on Play;
APK is legacy. The `--release` flag applies the signingConfig.

```bash
flutter build appbundle --release
```

The agent runs this command and confirms the output path. A successful build produces:
`build/app/outputs/bundle/release/app-release.aab`

**Crash symbolication (if Sentry detected in Phase 0 `analytics_tracking`):**

```bash
flutter build appbundle --release \
  --obfuscate \
  --split-debug-info=build/debug-info \
  --extra-gen-snapshot-options=--save-obfuscation-map=build/debug-info/obfuscation.map.json
# Upload symbols (non-blocking — a failure must not abort the release):
dart run sentry_dart_plugin
```

Symbol upload is non-blocking — skip if no crash-reporting SDK was detected.

**versionCode safety net:** before upload, confirm the AAB carries the expected `versionCode`.
If `bundletool` is available:

```bash
java -jar bundletool.jar dump manifest \
  --bundle build/app/outputs/bundle/release/app-release.aab | grep versionCode
```

If bundletool is not installed, skip — the collision check in `play-submit` catches a mismatch
at the API level.

---

### Step 4 — Upload AAB (dry-run default)

**Mode:** Automatable with explicit opt-in.

**What:** Upload the signed AAB to the Play edits transaction via `scripts/play-submit`. The
script is **dry-run by default** — it opens an edit, reads existing track state, performs the
versionCode collision check, and describes the intended upload without executing it. Confirm
with `--yes upload` when ready.

```bash
SCRIPT=~/.claude/skills/ship-to-playstore/scripts/play-submit

# Dry-run (default): describe what would happen, no mutation
python3 "$SCRIPT" {application_id} \
  --aab build/app/outputs/bundle/release/app-release.aab \
  --track {track} \
  [--rollout {fraction}] \
  [--version-code {version_code}] \
  [--report .scratch/ship-to-playstore/phase0-report.json]

# Execute upload only (still no commit):
python3 "$SCRIPT" {application_id} \
  --aab build/app/outputs/bundle/release/app-release.aab \
  --track {track} \
  [--rollout {fraction}] \
  --yes upload
```

The script checks the versionCode collision pre-upload and reports the result. A collision
(new code ≤ max existing on target track) is a hard stop (exit 2). After `--yes upload`, the
script prints the confirmed versionCode returned by Play's API.

**Nothing is live until `edits.commit`** — the upload stages the AAB in the edit transaction.

---

### Step 10a — Choose Track + Staged Rollout Fraction

**Mode:** Partially automatable — agent explains options; user confirms track and fraction.

**What:** Select the target track and, for production, the initial staged rollout fraction.
`--track` is required (no default) and `--rollout` is required for `--track production`.
"Oops I shipped to prod" is structurally hard.

**Track ladder and recommendation (OQ3, locked):**

| Track | Review | Audience | When to choose |
|---|---|---|---|
| `internal` | Instant (no review) | Up to 100 testers | **Always start here** — smoke-test before any review queue |
| `alpha` (Closed Testing) | May require review | Named tester groups | Limited external testing |
| `beta` (Open Testing) | May require review | Self-opt-in public testers | Broader pre-release |
| `production` | Potentially reviewed | All users, by rollout fraction | Final release |

**Recommendation:** always release to `internal` first, even if the app is ready for production.
Internal Testing is instant (no human review, visible in minutes), making it the cheapest
smoke-test. Then promote up the track ladder. Use `play-status` to confirm the internal release
before promoting.

**Staged rollout fractions for production (OQ3, locked):**
- Conventional first fraction: **0.01 (1%)** — monitors crash rates and negative reviews at
  minimal blast radius.
- Typical progression: 0.01 → 0.05 → 0.10 → 0.50 → 1.0 (fully rolled out).
- Each fraction change is a new `edits.tracks.update` + `edits.commit` (a separate `--yes`).
- Staged rollout is **haltable** (`status: halted`) and **promotable** at any fraction.

The agent confirms the track and rollout fraction with the user before Step 11.

---

### Step 11 — Release to Track + Commit

**Mode:** Automatable with explicit opt-in — each mutation is a separate `--yes`.

**What:** Update the target track with the uploaded bundle (`edits.tracks.update`), then
commit the edit (`edits.commit`), which publishes the release atomically. Two separate `--yes`
checkpoints — **never batched**.

```bash
SCRIPT=~/.claude/skills/ship-to-playstore/scripts/play-submit

# Release to track (update track, do not commit yet):
python3 "$SCRIPT" {application_id} \
  --aab build/app/outputs/bundle/release/app-release.aab \
  --track {track} [--rollout {fraction}] \
  --yes upload --yes release

# Commit (publish):
python3 "$SCRIPT" {application_id} \
  --aab build/app/outputs/bundle/release/app-release.aab \
  --track {track} [--rollout {fraction}] \
  --yes upload --yes release --yes commit
```

After `edits.commit`, the script opens a fresh read-only edit and re-reads the target track
to verify the versionCode is present and the release status is as expected. **Do not trust the
commit response alone** — always verify via a track re-read (PRD §10.2 Step 11).

**Pre-launch report (OQ6, locked):** Play auto-runs instrumentation tests on internal builds
after upload. The pre-launch report is **advisory and may lag** — the skill does not block
Step 11 waiting for it. Check it in Play Console → Android vitals → Pre-launch report, but
treat any findings as warn-not-block for an internal/testing release.

---

### Step 12 — Rollout Monitoring + Halt/Promote

**Mode:** Inform + periodic check — no forced wait.

**What:** For production staged rollouts, monitor crash rate and ANR rate in Android vitals
and promote or halt as appropriate. For internal/testing tracks, verify the release is visible
to testers in Play Console → Testing.

**Verification after commit:**

```bash
# Read current track state (read-only)
SCRIPT=~/.claude/skills/ship-to-playstore/scripts/play-status
python3 "$SCRIPT" {application_id} \
  --report .scratch/ship-to-playstore/phase0-report.json \
  --edit-id {edit_id}
```

**Promote to higher fraction (production):**

```bash
# Each fraction change requires its own --yes release --yes commit
python3 "$SCRIPT_SUBMIT" {application_id} \
  --aab build/app/outputs/bundle/release/app-release.aab \
  --track production --rollout 0.10 \
  --yes release --yes commit
```

**Halt a staged rollout (if a critical issue is found):**

A halted rollout stops expansion but does not roll back already-updated users. To halt:
- Play Console → Release → Production → current release → "Halt rollout"
- Or: issue a `tracks.update` with `status: halted` via a new edit + commit.

**Promote from internal to production:**

Promotion is a new upload to the target track (same versionCode, different track). Re-run
`play-submit` with `--track production --rollout 0.01 --yes upload --yes release --yes commit`.

**Pre-launch report (OQ6, reminder):** if the pre-launch report from Step 11 is now available,
review it in Play Console → Android vitals → Pre-launch report. Findings are advisory; act on
crashes/ANRs but do not treat a pending report as blocking a promotion decision.

**Review model:** Internal Testing is instant. Closed/Open/Production releases may go through
human review (exact trigger set is Phase-1 research; do not assert from training memory).
New apps on production always go through review. Updates may ship immediately but are subject
to automated policy checks and post-hoc suspension. The release is "live" when the track
status is `completed` or `inProgress` (staged rollout active).

---

## 3.6 — Resume Instructions

When the user pauses or the session ends before completion, print:

> "Paused at Step {N} — {title}. Status note updated at
> `.scratch/ship-to-playstore/status.md`. To resume later, re-invoke the
> `ship-to-playstore` skill — it reads the status note and picks up from Step {N}
> without re-running Phase 0/1/2."

---

## 3.7 — Completion Block (verify before declaring success)

When every checklist step is marked done, re-read the target track via `play-status` and
confirm:

- versionCode is present on the target track.
- Release `status` is `inProgress` (staged rollout), `completed` (fully rolled out), or
  `draft` (internal — visible to testers immediately).
- For a first release with IAP (checked in slice 05): every product is `published`.

Then print:

```
=== Release submitted ===

Steps completed : {N}
Version released: {version_name} ({version_code})
Track           : {track} — status: {status}
Status note     : .scratch/ship-to-playstore/status.md

What to expect (internal track):
  - Visible to internal testers in Play Console within minutes (no review).
  - Promote to production with: play-submit --track production --rollout 0.01 ...

What to expect (production track):
  - New app: review queue (duration varies; Phase-1 freshness report has current estimates).
  - Update: may publish immediately or may go through review.
  - Staged rollout at {rollout}% — monitor Android vitals and promote/halt in Step 12.
  - On policy action/suspension: re-invoke the skill — it enters the reject handler.
```

Append to the status note:

```
{timestamp} ✓ RELEASED — {version_name} ({version_code}) → {track} at {rollout}
```

---

## 3.8 — Play Policy Reject / Suspension Handling

A rejection or suspension is a new feedback loop, not a process abort.

### When Play rejects or suspends:

1. Policy decision text is **not reliably API-readable** — the user must paste it from
   Play Console → Policy status → Policy issues, or from the email notification.
2. Apply `pre-submit-verification.md` Gate C to classify the reason (slice 05).
3. Build a compact correction checklist (same one-step-at-a-time mechanic).
4. Log in status note: `{timestamp} ✗ REJECTED — policy: {name} — correction plan: {N} steps`

### Reject/suspension class table

| Class | Play policy cited | Correction |
|---|---|---|
| Minimum Functionality | *Minimum Functionality* | Fix crashes/placeholders; rebuild; re-upload to same track |
| Permissions | *Permissions* | Remove over-declared permissions from `AndroidManifest.xml`; rebuild |
| Payments / external steering | *Payments* | Remove links to external payment; use Play Billing API |
| Data Safety mismatch | *Privacy and Security / User Data* | Correct Data Safety form; republish |
| Over-broad permissions | *Personal and Sensitive User Information* | Narrow permission set in manifest |
| Store listing misleading | *Store Listing and Promotional Content* | Update title/description/screenshots |
| Subscription disclosure | *Subscriptions* | Show price/period/terms/privacy on paywall |
| App suspended | Varies | Whole app pulled; reinstatement is a separate Play Console flow |

---

## 3.9 — iOS Delta Summary (PRD §10.2 — why these steps differ from ship-to-appstore)

| Step | iOS (`ship-to-appstore`) | Android (`ship-to-playstore`) — delta |
|---|---|---|
| Step 1 — Versioning | `CFBundleVersion` (build number) | `versionCode` (monotonic int) is Play's identity — must be strictly > last code on target track |
| Step 1 — Verify | `PlistBuddy CFBundleVersion` | `bundletool dump manifest | grep versionCode` |
| Step 2 — Signing | Apple cert + provisioning profile | **Play App Signing**: upload key (local, resettable) + app signing key (Google holds, irrevocable enrolment) |
| Step 3 — Build | `flutter build ipa` | `flutter build appbundle --release` |
| Step 4 — Upload | `xcodebuild -exportArchive` upload to TestFlight | `edits.bundles.upload` (inside edit; no commit yet) |
| Step 5 — Wait | Build processing queue (5–30 min) | **No processing wait**: upload returns versionCode immediately |
| Step 10a — Track | TestFlight (internal/external) then submit for review | Internal → Closed → Open → Production track ladder; no "submit for review" API gate |
| Step 11 — Submit | "Submit for Review" button (human UI only) | `edits.tracks.update` + `edits.commit` — fully API-driven; each is a `--yes` checkpoint |
| Step 12 — Rollout | Phased release (7-day Apple-managed) | **Promotable/haltable** staged rollout (`userFraction`) — developer-controlled, no 7-day constraint |
| Review wait | 1–3 days typical | New apps: reviewed; most updates: may publish immediately (Phase-1 research for current rules) |
| Post-hoc action | Resolution Center reject | Policy suspension possible; text not API-readable — user must paste |

---

## 3.10 — Stack Fidelity Constraints

Binding throughout Phase 3:

- **Supabase Auth** for user authentication — never Firebase Auth.
- **FCM** only as Android push transport — no Firebase SDK for any other purpose.
- **Free tools only:** `flutter`, `gradle`, `bundletool` (free), Play Developer API (free tier).
  No paid CI pipeline, no paid upload service, no Edge Functions as a default backend step.
- **No secrets emitted:** keystore passwords, service-account JSON content, OAuth tokens must
  never appear in messages, command output, the status note, or committed files.
