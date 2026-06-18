# Phase 2 — ASC Status + Credential Discovery

Determine the current state of the app record in App Store Connect (ASC) and
identify which automated access strategy is available. Present the findings as a
compact situation overview so the user knows exactly what exists, what is missing,
and what the next required action is.

---

## 2.0 Ruby / fastlane environment precheck (do this FIRST)

Any ASC access via fastlane/`bundle exec` depends on the project's pinned Ruby being active.
The #1 first-run failure is `bundle exec` resolving against **system Ruby** while the project pins
a different version via rbenv — because the agent's Bash runs in a **non-interactive** shell that
does **not** load `~/.zshrc`, so rbenv shims are inactive. The symptom is:

```
Could not find 'bundler' (X.Y.Z) required by your Gemfile.lock. (Gem::GemNotFoundException)
```

Read Phase 0's `ruby_env` block. If `rbenv_present` (or `rvm_present`) is true and a
`ruby_version_file` is set, **prefix every fastlane / `bundle exec` command** — both the ones the
agent runs and the ones it hands the user to run — with the shim PATH:

```bash
PATH="$HOME/.rbenv/shims:$PATH" bundle exec fastlane ios status
```

Verify once up front (should print the pinned version + `ruby_env.bundler_locked`, not system 2.6):

```bash
PATH="$HOME/.rbenv/shims:$PATH" ruby -v
PATH="$HOME/.rbenv/shims:$PATH" bundle -v
```

If the user wants a permanent fix, offer to append an idempotent rbenv init to `~/.zshrc`
(`eval "$(rbenv init - zsh)"`) — but note it only affects **new interactive** shells, so the
agent's own commands still need the PATH prefix this session. **Caveat:** `zsh -l -c '…'` is a
*login* shell, not interactive, and still won't load `~/.zshrc`; verify with `zsh -i -c '…'`.

Do not skip this and "discover" the mismatch through a failed fastlane run — it costs two
round-trips every time.

---

## 2.1 Research available ASC access methods (live — always first)

Before attempting any access, run a short live web search to confirm which methods
are currently valid. Apple tooling changes regularly; never rely solely on training
memory for method availability or API versions.

```
WebSearch: "App Store Connect REST API current authentication methods 2025"
WebSearch: "fastlane deliver ASC access current year"
```

Synthesise findings. If search is unavailable, proceed with the known methods
below but note in the situation overview that freshness verification was skipped.

---

## 2.2 Credential discovery order

Always discover credentials in this exact order. Stop at the first level that
yields enough to proceed; ask the user only for what is specifically missing.

### Level 1 — Repo (already discovered by Phase 0 script)

The `phase0-introspect` script has already populated `credentials` in the
situation report. Read those fields now:

| Field | What it means |
|---|---|
| `credentials.p8_files` | List of `{path}` entries for `*.p8` files found in the repo |
| `credentials.fastlane_appfile` | `{path}` or `null` — fastlane Appfile present |
| `credentials.fastlane_env` | `{path}` or `null` — `.env` file present |
| `credentials.env_hints` | List of env var *names* that are SET (values never included) |

If `p8_files` is non-empty the ASC REST API path may be available (needs Issuer ID
and Key ID too — checked below).

### Level 2 — Local environment

Check whether the user's shell environment provides the needed credentials:

```bash
# Print only the NAMES of set variables — never their values
for v in ASC_ISSUER_ID APP_STORE_CONNECT_API_KEY_ISSUER_ID \
          ASC_KEY_ID APP_STORE_CONNECT_KEY_ID \
          APP_STORE_CONNECT_API_KEY_KEY_ID \
          FASTLANE_ITC_TEAM_ID; do
  [ -n "${!v}" ] && echo "SET: $v" || echo "unset: $v"
done
```

If any hint name from `credentials.env_hints` matches what the chosen strategy
needs, note it as available.

### Level 3 — Ask the user (pointedly)

Only ask when a specific credential is needed and provably absent at Levels 1–2.
Never guess, never silently assume a value. State exactly what is missing and why
it is required:

> "To use the ASC REST API, I need:
> - **Issuer ID** — visible in App Store Connect → Users & Access → Integrations → App Store Connect API
> - **Key ID** — the identifier shown next to the `.p8` file when you download it
> - **The `.p8` file** — downloaded once from the same page (cannot be re-downloaded; store it safely)
>
> Which of these do you have, and where?"

---

## 2.3 Strategy selection (most automated → least)

**Before the generic strategies below, check Phase 0's `fastlane_lanes`.** If the project defines
a `status` lane, run it (with the §2.0 PATH prefix) — it encodes the developer's exact API-key
wiring and reports versions/builds/IAPs in one shot, more reliably than raw endpoint calls. If it
defines a `release`/`publish` lane, that is the Phase 3 submission path. Only fall back to the
generic strategies when no Fastfile lane covers the need.

### Reading ASC state: verified vs cannot-verify vs not-done (HARD RULE)

Every ASC read has **three** possible outcomes — never collapse them into two:

| State | Meaning | How to present |
|---|---|---|
| **✓ verified** | HTTP 200 + real data confirming it is done | "done" — skip it |
| **? cannot-verify** | the API cannot express this fact, or returned a non-200 | "I can't see this via the API — please confirm in the ASC UI" |
| **□ not-done** | HTTP 200 + data confirming the field is genuinely empty | "this is missing — here's how to set it" |

The cardinal error (observed in the first real run): treating **cannot-verify as not-done** and
telling the user to "do" something that was already done. Two concrete traps:

1. **Always check the HTTP status explicitly.** Never wrap an API call in a bare `rescue {}` /
   ignore-errors that turns a `404`/`401` into an empty `{}`. A 404 on a wrong endpoint path looks
   identical to "no data" if you don't check the status — and you will report a published field as
   "empty". Print the status code; on non-200, classify as **cannot-verify**, not not-done.
2. **Some facts are not queryable at all.** The App-Privacy **publish state** and whether IAPs are
   **attached to a version** have no reliable read endpoint. These are always **cannot-verify** →
   ask the user to confirm in the UI. Never assert them as open TODOs from inference alone.

After any **mutating** action (e.g. a `release` lane run), re-read the state via API to confirm the
mutation landed — do not trust the success log alone.

### Strategy ordering

Try strategies in this order. Switch to the next when a required input is absent.

### Strategy A — ASC REST API via `.p8` / Issuer ID / Key ID

**Required inputs:** `*.p8` file path, Issuer ID, Key ID.

When all three are available (discovered at Levels 1–2 above), the agent can
call the ASC REST API directly to query app record, version, build, and metadata
status.

Endpoints to call (refer to live-researched API docs):
1. `GET /v1/apps?filter[bundleId]={bundle_id}` — confirm app record exists
2. `GET /v1/apps/{id}/appStoreVersions?filter[appStoreState]=PREPARE_FOR_SUBMISSION,WAITING_FOR_REVIEW,IN_REVIEW,READY_FOR_SALE` — current versions
3. `GET /v1/builds?filter[app]={id}&sort=-uploadedDate&limit=1` — latest build
4. `GET /v1/apps/{id}/appInfos` — metadata completeness hints
5. `GET /v1/apps/{id}/inAppPurchasesV2?limit=200` — **only if Phase 0 reported
   `in_app_purchases.likely_present: true`.** Returns every IAP/subscription
   product with its `state` (`MISSING_METADATA`, `READY_TO_SUBMIT`,
   `WAITING_FOR_REVIEW`, `APPROVED`, …). This is the read-side of the 2.1(b)
   gate: any product that is not at least `READY_TO_SUBMIT` (most often because
   the App Review screenshot or another required field is missing → state stays
   `MISSING_METADATA`) will not be submitted with the build and triggers
   Guideline 2.1(b). For auto-renewable subscriptions the per-product state is
   nested under a subscription group; if `inAppPurchasesV2` is empty but Phase
   0 detected IAP usage, classify as `? cannot-verify` (may live in a different
   group endpoint) and confirm in the UI.

Parse responses to populate the situation overview (§ 2.5).

### Strategy B — fastlane config

**Required inputs:** `fastlane/Appfile` (and optionally Matchfile).

When Strategy A is unavailable but a fastlane config exists, instruct the user
to run:
```bash
bundle exec fastlane run get_app_store_version_release_date app_identifier:<bundle_id>
```
Or use `fastlane deliver --skip_binary_upload --skip_metadata` as a dry-run to
surface what metadata is missing. Report the output.

### Strategy C — Local tokens / env (altool / notarytool)

**Required inputs:** Apple ID + app-specific password OR ASC API key via env.

When Strategies A and B are unavailable but an app-specific password is available:
```bash
xcrun altool --list-apps -u <apple_id> -p @keychain:"Application Loader: <apple_id>"
```
Parse to confirm the app record. Note: `altool` is deprecated as of Xcode 14;
prefer Strategy A for new setups.

### Strategy D — Web UI guidance (always available fallback)

When no automated access is possible, guide the user through the App Store Connect
web UI manually:

1. Go to [App Store Connect](https://appstoreconnect.apple.com)
2. Select **My Apps** → find the app by bundle ID (`{bundle_id}`) or name.
3. Note the current version number shown on the app record page.
4. Under **TestFlight**, confirm whether the latest build is uploaded and processed.
5. Under **App Store → Version Information**, check which metadata fields show a
   red warning (screenshot requirements, description, keywords, support URL, etc.).

Report back what you see and the agent will advise next steps.

---

## 2.4 Creating an ASC API key (when none exists)

If the user has no `.p8` key, walk them through this one-time setup to unlock
Strategy A for this release and all future ones:

1. **Go to:** App Store Connect → Users & Access → Integrations tab →
   App Store Connect API → Keys
2. **Click** the "+" button to generate a new key.
   - Name: anything recognisable (e.g. "Release Agent Key")
   - Access: **App Manager** role (sufficient for reads, build submission, and
     metadata updates; Admin is not required).
3. **Record the Key ID** shown in the table immediately after creation (e.g.
   `ABC123DEF4`).
4. **Record the Issuer ID** shown at the top of the Integrations page (same for
   all keys in your account, e.g. `a1b2c3d4-e5f6-...`).
5. **Download the `.p8` file** — Apple shows this link **only once**. Save it
   somewhere safe outside the repo (e.g. `~/.appstoreconnect/private_keys/`).
   If you lose it, you must revoke the key and create a new one.
6. **Place the `.p8` in your repo** under `ios/private_keys/AuthKey_{KEY_ID}.p8`
   (or any path you prefer) and add that path to `.gitignore` immediately.
7. Tell the agent the Issuer ID and Key ID (the `.p8` path will be detected
   automatically the next time Phase 0 runs).

---

## 2.5 Compact situation overview

After completing discovery and at least one strategy attempt, present this summary
block (fill in each field; use "unknown — see below" when a strategy could not
determine a value):

```
=== App Store Connect: Situation Overview ===

App record
  Bundle ID        : {bundle_id}
  App exists       : yes | no | could not determine
  Current live ver : {version} | none | unknown

Build pipeline
  Latest build     : {build_number} ({status}) | none found | unknown
  Uploaded?        : yes | no | unknown
  Processed?       : yes | no | unknown

Metadata
  Description      : complete | missing | unknown
  Screenshots      : complete | {N} sizes missing | unknown
  Keywords         : set | missing | unknown
  Support URL      : set | missing | unknown
  Privacy policy   : set | missing | unknown

Pricing            : set | NOT SET (blocks submission) | ? cannot-verify
Privacy label      : published | not published | ? cannot-verify (confirm in UI)
In-App Purchases   : {per-product state, e.g. "lifetime=READY_TO_SUBMIT, monthly=MISSING_METADATA"} | none | ? cannot-verify
                       ← if any product is not READY_TO_SUBMIT/APPROVED, Step 10b is a HARD BLOCKER
                         before Step 11 (else Guideline 2.1b reject)

Access strategy used : A (ASC REST API) | B (fastlane) | C (altool) | D (Web UI)

Missing / action required:
  - {bullet per gap, or "nothing — ready for Phase 3"}
```

Use the tri-state markers consistently: `✓` verified-done, `?` cannot-verify (point the user to
the ASC UI), `□`/"NOT SET" only when HTTP 200 + data confirm it is genuinely empty. **Pricing**
and the **privacy-label publish state** are frequent first-release blockers — always include them.
Keep the overview to ~15 lines. Do not dump raw API responses. If a field could not be determined,
say "cannot-verify" and point to where the user can confirm it — never guess "missing".

---

## 2.6 Transition to Phase 3

Once the situation overview is presented and the user has confirmed the state is
correct (or has corrected any mismatches), continue to Phase 3 (guided release
loop). Read [phase3-release-loop.md](phase3-release-loop.md).

If any gap in the situation overview is blocking (e.g. no app record exists, no
build uploaded), address it before loading Phase 3 — walking the user through
the remediation step by step, one action at a time, with confirmation at each.
