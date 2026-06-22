# Pre-Submit Verification — LLM/vision-assisted gates (Play Store)

Loaded by Phase 3 **before Step 11 (Release to track + commit)**. These catch the reject reasons
that are *not* expressible as an API field — they need judgement over text, images, and code. Gates
A–B come straight from real Play policy rejections the API-only checks missed; Gates D–M extend the
same idea to the other high-frequency Play policies a solo-dev trips over.

Run them as the last gate before commit (Step 10c). Every gate produces a **tri-state verdict**:

- `✓ verified` — gate passed; no issues found; loop proceeds.
- `? cannot-verify` — gate cannot be resolved mechanically; user must confirm manually before Step 11.
- `□ confirmed-open` — gate found a concrete issue; Step 11 is **blocked** until the issue is resolved.

Where a vision model is unavailable, fall back to the mechanical scan and tell the user the visual
pass was skipped (do not silently drop it).

**Applicability is driven by Phase 0 facts — run only the gates in scope, don't interrogate.** Each
gate below names the Phase 0 field that scopes it; if that field says the feature is absent, state
that as a fact and skip the gate. Gate index:

| Gate | Play policy / concern | Scope (Phase 0) |
|---|---|---|
| A — price references in store listing/screenshots | *Store Listing and Promotional Content* / *Misleading claims* | always |
| B — listing/feature claims vs code | *Functionality* / *Misleading claims* | always |
| D — Data Safety form vs actual data + deletion field | *Privacy and Security* / *User Data* | always |
| E — permissions: declared, used, not excessive | *Permissions* | `permissions` (always present) |
| F — (n/a — Sign in with Apple is Apple-only; see note) | — | dropped |
| G — subscription disclosure (price/period/contents + links) | *Subscriptions* / *Payments* | `play_billing.likely_present` (subscriptions) |
| H — no external payment steering for digital goods | *Payments* | `play_billing.likely_present` |
| I — Privacy/Support URL liveness | *Privacy and Security* | always (needs `WebFetch`) |
| J — demo account in review notes | *Functionality* | when login gates content |
| K — account-deletion depth + web deletion URL | *User Data* (account/data deletion) | `data_safety_hints.account_deletion.likely_present` |
| L — UGC safety controls | *User Generated Content* | `user_generated_content.likely_present` |
| M — placeholder / minimum functionality | *Minimum Functionality* / *Completeness* | always |
| C — reject-text classification | — | reject handler only (§3.8) |

---

## Gate A — Price references in store listing/screenshots (Store Listing and Promotional Content)

**Why.** Play rejects under *Store Listing and Promotional Content* / *Misleading claims* when the
store listing or screenshot overlays contain price references — including *free*, *gratis*,
*kostenlos*, discounts, percentage-off claims, or currency amounts. These are considered inaccurate
or misleading metadata once pricing changes. Unlike the long-form description, the title, short
description, and screenshot captions are scrutinised most closely.

**Play policy anchor:** *Store Listing and Promotional Content* policy — Misleading claims.

### A.1 Mechanical scan (always)

Find where store listing text and screenshot captions are authored. On Flutter projects using
Fastlane, this is commonly `fastlane/metadata/android/` (locale subdirectories with `title.txt`,
`short_description.txt`, `full_description.txt`, `changelogs/`). Also check any screenshot-generator
config (e.g. `tools/appstore-screens/`, `fastlane/Screengrabfile`).

```bash
# Adjust the path glob to where captions/screenshot configs live in THIS repo.
grep -rniE 'free|gratis|kostenlos|umsonst|spar|rabatt|discount|sale|% off|gutschein|\
[€$£¥][0-9]|[0-9][.,][0-9]{2}\s*(€|eur|usd|\$)' \
  fastlane/metadata/android/ tools/ assets/ 2>/dev/null
```

Any hit in the **title, short description, screenshot overlay text, or feature graphic copy** is a
*Store Listing and Promotional Content* blocker. A price reference inside the long description may
also be flagged — judge by where the string is rendered. Err on the side of flagging.

### A.2 Vision pass (when a vision model is available)

The mechanical scan misses price text baked into a PNG (a "Free" badge, a struck-through price, a
"0 €" sticker). If the actual exported screenshot PNGs are on disk, Read each image and judge:

> "Does this screenshot contain any reference to price, cost, being free/gratis/kostenlos, a
> discount, a percentage off, or a currency amount — anywhere in the image, including badges,
> stickers, or device-frame overlays? Answer yes/no and quote the text."

Flag every yes as a blocker with the file name and the offending text. If the PNGs are not on disk,
tell the user to eyeball each screenshot for price words and cite the exact rule.

### A.3 Verdict

```
Store Listing / price-reference scan:
  ⚠ fastlane/metadata/android/en-US/short_description.txt:1  "Start for free"  → price reference, must change
  ✓ no currency amounts in title or feature graphic text
```

Any `⚠` blocks Step 11: the copy must be reworded and screenshots regenerated + re-uploaded before
commit.

---

## Gate B — Listing/feature claims vs code (Functionality / Misleading claims)

**Why.** Play rejects under *Functionality* and *Store Listing and Promotional Content* / *Misleading
claims* when the store listing describes features that are absent, broken, or non-functional in the
submitted binary. A claimed feature the reviewer cannot exercise causes a functional test failure.

**Play policy anchor:** *Functionality* policy; *Store Listing and Promotional Content* — Misleading
claims.

### B.1 What to cross-check

Collect the app's outward claims:
- Store **title**, **short description**, **full description**, **What's New** text (from
  `fastlane/metadata/android/` or Play Console).
- Per-product display names and IAP review notes.
- Any feature list in screenshot captions or the feature graphic overlay.

For each concrete, testable claim (auth method, cloud sync, widget, reminders, export, offline mode,
push notifications, a named integration), verify against the codebase:

```bash
# Example checks — adapt to the claims found:
grep -rniE 'supabase|SupabaseClient' lib/ pubspec.yaml              # claim: "cloud sync" / auth
grep -rniE 'home.?screen widget|app_widget|FlutterWidgetProvider' lib/ android/ # claim: widget
grep -rniE 'pdf|export|csv|download' lib/ 2>/dev/null               # claim: export feature
grep -rniE 'offline|local.?db|sqflite|hive|isar' lib/ 2>/dev/null   # claim: offline mode
```

A claim is a **blocker** when the feature is named in store text / review notes but **absent or
non-functional** in code (dead dependency, removed flow, stubbed call). Cross-reference `docs/adr/`
if present — removed features are often documented there. A `grep` for the package name alone is not
enough — a dead dependency still appears in `pubspec.yaml`; confirm there are real call sites.

### B.2 Verdict

```
Functionality / listing-claims audit:
  ✓ Cloud sync       — implemented (lib/services/sync_service.dart)
  ✓ Push notifications — FCM wired (firebase_messaging detected)
  ⚠ "Offline mode" in full description — no offline/local-DB code path found → remove claim or implement
```

Any `⚠` blocks Step 11 until the store text is corrected or the feature is shipped.

---

## Gate D — Data Safety form vs actual data + deletion field (Privacy and Security / User Data)

**Why.** Google cross-checks the Data Safety form against what the binary actually collects and
shares. A mismatch in **either** direction is a *Privacy and Security* reject: declaring a data type
the app never collects, **or** collecting / sharing one that is not declared. Additionally, the Data
Safety form's **"Does your app provide a way to request data deletion?"** field must be set to
**"Yes"** when `data_safety_hints.account_deletion.likely_present = true`.

**Play policy anchor:** *Privacy and Security* policy — *User Data* section; *Account and Data
Deletion policy*.

**Inputs.** Phase 0 `data_safety_hints`, `permissions.declared`, `supabase_used`,
`push_notifications.fcm_used`. Do **not** ask the user what the app collects — derive from facts.

### D.1 Derive the "actually collected" set

| Phase 0 field | Data Safety declaration |
|---|---|
| `data_safety_hints.analytics_tracking[].category = "crash/diagnostics"` | Crash logs |
| `data_safety_hints.analytics_tracking[].category = "analytics/usage"` | App interactions |
| `supabase_used = true` | Email address; User IDs (Supabase Auth standard data) |
| `push_notifications.fcm_used = true` | Device or other IDs (FCM registration token) |
| `permissions.declared` contains `CAMERA` | Photos and videos |
| `permissions.declared` contains `ACCESS_FINE_LOCATION` | Precise location |
| `permissions.declared` contains `ACCESS_COARSE_LOCATION` | Approximate location |
| `permissions.declared` contains `READ_CONTACTS` or `WRITE_CONTACTS` | Contacts |
| `permissions.declared` contains `RECORD_AUDIO` | Audio files |

Compare this derived set against what is actually declared in Play Console → Policy → Data Safety.
Flag every **declared-but-not-collected** (over-declaration) and **collected-but-not-declared**
(under-declaration).

### D.2 Data-deletion field check

When `data_safety_hints.account_deletion.likely_present = true`:

- The Data Safety form's **"Does your app provide a way to request data deletion?"** must be set to
  **"Yes"** (see Step 6 guidance for the full declaration map).
- The in-app deletion flow (Step 6a) must reach a real server-side deletion — not just a local
  sign-out or cache clear.
- A **web-based deletion request URL** must be registered in Play Console → Policy → Data Safety →
  Account deletion section (required by Play's account deletion policy, separate from the in-app
  flow).

When `account_deletion.likely_present = false` but the app creates accounts (`supabase_used = true`):
surface as a contradiction and ask the user to confirm whether account deletion is implemented.

### D.3 Verdict

```
Data Safety audit:
  ⚠ "Contacts" declared in Data Safety form but no contacts plugin / code path found → remove or justify
  ⚠ Crash logs collected (sentry_flutter) but NOT declared in form → add "Crash logs"
  ✓ Email / User IDs declared, matches Supabase Auth
  ✓ data_safety_hints.account_deletion.likely_present = true → "data deletion provided" = YES — confirm in Console
  ✓ FCM registration token declared (Device or other IDs)
```

The form's *published* state is `? cannot-verify` via the API — confirm in Play Console after entry.
Any `⚠` blocks Step 11.

---

## Gate E — Permissions: declared, used, not excessive (Permissions policy)

**Why.** Play rejects under the *Permissions* policy and *Personal and Sensitive User Information*
section when the app declares permissions not needed for any apparent functionality. Over-broad
permissions are also a ranking penalty. Conversely, a permission used at runtime but absent from
`AndroidManifest.xml` is a runtime crash.

**Play policy anchor:** *Permissions* policy; *Personal and Sensitive User Information* section.

**Inputs.** Phase 0 `permissions` — `declared`, `expected_from_plugins`, `excessive`, `missing`.

### E.1 Checks

- **Excessive** (`permissions.excessive` — declared but no detected plugin needs it): Play ranking
  penalty + possible *Permissions* reject. Present as **"verify, likely remove"** — native code may
  legitimately use it. Each excessive permission must be individually justified before Step 11.
- **Missing** (`permissions.missing` — a plugin needs it, but it is not declared): runtime-crash
  risk. Flutter plugin manifests merge their own permissions at build time, so `missing` is a hint —
  but a permission the app's own runtime code requests with no manifest entry will crash. Confirm the
  plugin's own `AndroidManifest.xml` handles it.
- **Specificity** — check whether a coarser permission suffices:
  - `ACCESS_FINE_LOCATION` declared but only coarse coordinates needed → replace with
    `ACCESS_COARSE_LOCATION`.
  - `READ_EXTERNAL_STORAGE` declared on `targetSdk ≥ 33` → should use scoped storage APIs instead
    (the broad permission is denied on Android 13+ regardless).
- **`INTERNET`** is baseline-expected for any Flutter app and is **never** flagged as excessive.

```bash
# Confirm declared permissions match what plugins expect:
grep -E 'uses-permission' android/app/src/main/AndroidManifest.xml
```

### E.2 Verdict

```
Permissions audit:
  ⚠ ACCESS_FINE_LOCATION declared but no precise-location plugin in permissions.expected_from_plugins → verify native use; likely remove (Permissions policy)
  ⚠ READ_EXTERNAL_STORAGE declared on targetSdk 34 → replace with scoped storage; image_picker handles this
  ✓ CAMERA declared and expected by camera plugin
  ✓ POST_NOTIFICATIONS declared and expected by FCM
  ✓ INTERNET declared — baseline, not flagged
```

Any `⚠` blocks Step 11 until the manifest is corrected and the AAB rebuilt.

---

## Gate F — (n/a — intentionally dropped)

**Why absent.** Gate F in the iOS skill (`ship-to-appstore`) enforces the **Sign in with Apple**
mandate (App Store Review Guideline 5.1.1(iv)): any app with third-party social login must also
offer Sign in with Apple. **Android / Google Play has no equivalent mandate.** Google does not
require apps that ship Google Sign-In or any other third-party login to also offer an alternative
Google-native auth method. There is no Play policy with an analogous rule.

Gate F is therefore absent from this gate set. The gap in the letter sequence is intentional — it
preserves alignment with the iOS gate index for cross-referencing, and documents the deliberate drop
rather than silently renumbering. If a future Play policy introduces an analogous social-login
requirement, Gate F is the reserved slot to add it.

---

## Gate G — Subscription disclosure: price/period/contents + links (Subscriptions / Payments)

**Why.** Play rejects under the *Subscriptions* and *Payments* policies when a subscription paywall
does not clearly disclose the subscription title, duration, price per period, and what is included —
and when the binary does not contain functional links to the Privacy Policy and Terms of Service.
First-subscription submissions are audited most closely.

**Play policy anchor:** *Subscriptions* policy; *Payments* policy.

**Scope.** Only in scope when `play_billing.likely_present = true` **and** subscription products are
detected (Phase 2 subscription catalog, or `play_billing.code_markers` contains subscription API
markers such as `BillingClient`, `queryProductDetails`). If only one-time purchases are present, state
that and skip.

### G.1 What to check

Inspect the paywall file(s) in `lib/` for:
- Each subscription plan's **price + period** rendered (e.g. "€9.99 / month").
- A **benefits / what's-included** list.
- Functional links (tappable, not just `Text` widgets) to:
  - **Privacy Policy** (`privacyPolicy` URL from store metadata or `fastlane/metadata/android/`).
  - **Terms of Service / EULA** (a custom EULA or a link to one).

```bash
grep -rniE 'subscription|terms|privacy|TermsOfService|PrivacyPolicy|EulaUrl|\
price|period|monthly|yearly|annual' lib/ 2>/dev/null
```

Confirm the app's **store metadata** has a Privacy Policy URL set — mandatory for any app with
user data or permissions, and required by Play for subscriptions.

### G.2 Verdict

```
Subscriptions / Payments audit:
  ✓ Monthly/Yearly plans show price + period on the paywall (lib/paywall_screen.dart)
  ⚠ No Terms of Service link on paywall → add a tappable link (Subscriptions policy blocker)
  ✓ Privacy Policy link present; privacyPolicy URL set in store metadata
```

Any `⚠` blocks Step 11.

---

## Gate H — No external payment steering for digital goods (Payments policy)

**Why.** Play's *Payments* policy requires that digital goods and services consumed within the app
use Play Billing. A link or CTA steering users to purchase or subscribe **outside** the app (a web
checkout, "manage your plan on our website", Stripe/PayPal for digital content) is a *Payments*
policy reject. Play's *User Choice Billing* programme is a narrow opt-in exception — do not assume
it applies.

**Play policy anchor:** *Payments* policy — in-app billing section.

**Scope.** Only in scope when `play_billing.likely_present = true`.

### H.1 Scan

```bash
grep -rniE 'stripe|paypal|checkout\.|buy (on|at) (our )?(web|site)|subscribe on (the )?web|\
manage (your )?(subscription|plan) (on|at)|payment(s)?\.(com|io)|lemonsqueezy|paddle|\
external.?pay|web.?checkout|billing.?portal' \
  lib/ fastlane/metadata/android/ 2>/dev/null
```

A hit that routes **digital** purchases or subscriptions off-platform is a blocker. Physical-goods
purchases are exempt — judge what is being sold. Service-level links (e.g. "manage enterprise plan"
for B2B SaaS) may qualify for the *External links for apps* exception — confirm it applies before
passing.

### H.2 Verdict

```
Payments / external-purchase scan:
  ⚠ lib/settings_screen.dart: "Manage subscription on our website" link → digital goods must use Play Billing (blocker)
  ✓ no Stripe/PayPal/web-checkout paths for digital content
```

Any `⚠` blocks Step 11.

---

## Gate I — Privacy & Support URL liveness (needs `WebFetch`)

**Why.** Google opens the Privacy Policy URL during review. A 404, a parked domain, or a page that
is not actually a privacy policy draws a *Privacy and Security* reject. "Set in store metadata"
(Phase 2) only proves the field is non-empty — not that the URL resolves and shows the right content.

**Play policy anchor:** *Privacy and Security* policy; Privacy Policy requirement.

**Scope.** Always. Requires `WebFetch`.

### I.1 Check

Retrieve the Privacy Policy URL and Support/Contact URL from `fastlane/metadata/android/` or Phase 2
`appDetails.privacyPolicy`. Then fetch both:

```
WebFetch: {privacy_policy_url}  → "Is this a working privacy policy page (not a 404/parked/login wall)?"
WebFetch: {support_url}         → "Is this a reachable support/contact page (not a bare social profile)?"
```

The Support URL must not be a bare social-media profile (a Twitter/X or Facebook page that does not
serve as a functional support channel). A redirect chain that resolves to 200 on the correct page type
is acceptable. If `WebFetch` is unavailable, tell the user to open both URLs in a browser and confirm —
do not silently skip.

### I.2 Verdict

```
URL liveness:
  ✓ https://example.com/datenschutz → privacy policy page, 200
  ⚠ https://example.com/support → 404 → fix the URL or publish the page (blocker)
```

Any `⚠` blocks Step 11.

---

## Gate J — Demo account in review notes (Functionality policy)

**Why.** If any part of the app requires login, the Play reviewer needs working credentials —
otherwise they cannot exercise the app and reject under *Functionality* ("unable to sign in" /
"app requires authentication to access features"). This is the same failure mode as the iOS
equivalent, re-anchored to Play's *Functionality* policy.

**Play policy anchor:** *Functionality* policy.

**Scope.** Only in scope when the app has a login that gates content. Phase 0 `supabase_used = true`
is a hint; confirm from Phase 2 / listing whether a login gate exists.

### J.1 Check

Confirm the **App access** section in Play Console (Play Console → Policy → App content → App access)
contains a **demo account** (username + password) or an explicit note explaining how the reviewer can
access all features. For a passwordless / anonymous auth model, state that no demo account is needed
and the access note explains the model.

### J.2 Verdict

```
Functionality / reviewer access:
  ⚠ App requires login (Supabase Auth detected); no demo credentials in App content → App access → add them (blocker)
  ✓ (or) no login gate / anonymous-first — App access note explains how to reach all features
```

Any `⚠` blocks Step 11.

---

## Gate K — Account-deletion depth + web deletion URL (User Data policy)

**Why.** Play's *User Data* policy — *Account and data deletion* section — requires that any app
allowing users to create accounts must offer a way to **request deletion of their account and
associated data**, both **in-app** and via a **web form** (so users can request deletion after
uninstalling). An email-to-support flow alone does not satisfy the mandate. This gate verifies
**implementation depth**, extending Gate D's Data Safety form check (§D.2) into the code.

**Play policy anchor:** *User Data* policy — *Account and data deletion* section.

**Scope.** Only in scope when `data_safety_hints.account_deletion.likely_present = true`.

### K.1 Check

When accounts exist, verify the deletion flow:

1. **Server-side deletion in code.** The in-app flow must call a real server-side deletion — not
   just a local sign-out, cache clear, or `supabase.auth.signOut()`. Look for the Supabase Auth
   Admin delete call or a Postgres RPC that removes the `auth.users` row (see Step 6a in
   `phase3-release-loop.md` for the recommended Supabase implementation).

   ```bash
   grep -rniE 'delete.?account|deleteAccount|remove.?user|auth\.admin\.deleteUser|\
   supabase.*delete.*user|rpc.*delete_account|delete.*auth\.users' lib/ 2>/dev/null
   ```

2. **Reachable from UI.** The deletion option must be navigable from the app's Settings or Account
   section without requiring an undocumented sequence.

3. **Web deletion URL registered.** Play Console → Policy → Data Safety → Account deletion section
   must have a URL where users can request data deletion even after uninstalling the app. This is
   the Play-specific addition beyond the iOS equivalent.

### K.2 Verdict

```
User Data / account deletion:
  ⚠ lib/account_page.dart: deleteAccount() only calls supabase.auth.signOut() — no server delete → wire delete_account RPC (blocker)
  ⚠ No web deletion URL registered in Play Console → Policy → Data Safety → Account deletion (blocker)
  ✓ in-app deletion calls delete_account RPC and is reachable from Settings → Account
  ✓ web deletion URL set in Play Console
```

Any `⚠` blocks Step 11.

---

## Gate L — UGC safety controls (User Generated Content policy)

**Why.** An app with user-generated content must provide a content filter, an in-app **report**
mechanism, an in-app **block** mechanism, and a published Terms of Service with a zero-tolerance
clause. Missing controls are a *User Generated Content* reject.

**Play policy anchor:** *User Generated Content* policy.

**Scope.** Only in scope when `user_generated_content.likely_present = true`.

### L.1 Check

When UGC is present, confirm:
- A way to **flag/report** objectionable content (in-app, visible to users).
- A way to **block** an abusive user.
- Some **filtering or moderation** mechanism.
- A published **Terms of Service** (EULA) with a zero-tolerance abuse clause, linked from the store
  listing.

`user_generated_content.has_report_or_block` is a hint — verify the controls are reachable in the
actual UI and that the ToS/EULA is linked.

```bash
grep -rniE 'report|block|flag|moderat|eula|terms.?of.?service|abuse' lib/ 2>/dev/null
```

### L.2 Verdict

```
User Generated Content audit:
  ⚠ Comment feature detected; no report/block UI found in lib/ → add report + block + link EULA (blocker)
  ✓ (or) user_generated_content.likely_present = false → not in scope
```

Any `⚠` blocks Step 11.

---

## Gate M — Placeholder / minimum functionality (Minimum Functionality / Completeness)

**Why.** Placeholder content, lorem ipsum, obviously fake or test data, dead buttons, or empty/broken
screens are *Minimum Functionality* rejects. Some of this is visible only in screenshots.

**Play policy anchor:** *Minimum Functionality* policy.

**Scope.** Always.

### M.1 Mechanical scan

```bash
grep -rniE 'lorem ipsum|todo|fixme|placeholder|dummy|test ?data|coming soon|\
\bxxx\b|\blipsum\b|sample text|not.?yet.?implemented' lib/ fastlane/metadata/android/ 2>/dev/null
```

Flag any hit that would be **rendered to the user** (a `Text` widget, a store description
placeholder, a screenshot caption). `// TODO` code comments and unreachable stubs are warnings,
not blockers on their own — judge whether they surface in the UX.

### M.2 Vision pass (when a vision model is available)

Per screenshot: *"Does this screenshot show placeholder/lorem-ipsum/obviously fake data, an empty
error/broken state, or an unfinished screen?"* Flag every hit with the file name.

### M.3 Verdict

```
Minimum Functionality / completeness:
  ⚠ lib/home_screen.dart: Text("TODO: load real data") → rendered in UI; replace before submit
  ⚠ screenshot_03.png shows an empty error state → recapture with real content
  ✓ no placeholder tokens in store listing text
```

Any `⚠` blocks Step 11.

---

## Gate C — Reject-text classification (reject handler only — §3.8)

Not a pre-submit gate — used in Phase 3 §3.8 when a rejection or policy action arrives. Policy
decision text is **not reliably API-readable** (Play Console → Policy status → Policy issues, or
the emailed notification); the user must paste it. Then apply LLM judgement:

1. **Identify the cited policy name(s)** (e.g. *Minimum Functionality*, *Permissions*, *Payments*,
   *User Generated Content*, *Privacy and Security*, *Subscriptions*) and whether it is single- or
   multi-cause.
2. **Map each cause to the artifact that fixes it** via the §3.8.2 reject-class table in
   `phase3-release-loop.md`.
3. **Separate actionable text from boilerplate.** Some rejection emails carry generic "review the
   policy" language that does not identify the exact violation — do not treat boilerplate as a
   concrete finding. Focus on the specific cited policy and any example the reviewer provides.
4. **For app suspensions** (whole-app pull, not just a release reject): the fix and reinstatement
   flow differs — a suspension requires a formal appeal or policy declaration in Play Console, not
   just a re-upload. Do not assume the same correction steps as a single-release reject.
