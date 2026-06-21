# Pre-Submit Verification — LLM/vision-assisted gates

Loaded by Phase 3 **before Step 11 (Submit for Review)**. These catch the reject reasons that are
*not* expressible as an API field — they need judgement over text, images, and code. Gates A–B come
straight from real rejections the API-only checks missed; Gates D–M extend the same idea to the
other high-frequency Apple guidelines a solo-dev trips over.

Run them as the last gate before submit. Each is a hard blocker only when it finds a concrete hit;
a clean pass is logged and the loop proceeds. Where a vision model is unavailable, fall back to the
mechanical scan and tell the user the visual pass was skipped (do not silently drop it).

**Applicability is driven by Phase 0 facts — run only the gates in scope, don't interrogate.** Each
gate below names the Phase 0 field that scopes it; if that field says the feature is absent, state
that as a fact and skip the gate. Gate index:

| Gate | Guideline | Scope (Phase 0) |
|---|---|---|
| A — price references in visual metadata | 2.3.7 | always |
| B — store/review-note claims vs code | 2.3 | always |
| D — privacy label vs actual data collection | 5.1.2 | always |
| E — Info.plist purpose strings present/specific/used | 5.1.1, 5.1.5 | `ios_permissions` |
| F — Sign in with Apple required | 5.1.1(iv) | `social_login.siwa_required` |
| G — subscription disclosure + Terms/Privacy links | 3.1.2 | `in_app_purchases` (subscriptions) |
| H — external purchase / steering links | 3.1.1 | `in_app_purchases` |
| I — privacy & support URL liveness | 2.3 / 5.1.1 | always (needs `WebFetch`) |
| J — demo account in review notes | 2.1 | when the app requires login |
| K — account-deletion depth | 5.1.1(v) | `account_deletion` |
| L — UGC safety controls | 1.2 | `user_generated_content.likely_present` |
| M — placeholder / completeness | 2.1 | always |
| C — reject-text classification | — | reject handler only (§3.8) |

---

## Gate A — Screenshot / metadata price-reference scan (Guideline 2.3.7)

**Why.** A real submission was rejected under **2.3.7 — Accurate Metadata** because two screenshot
captions read *"Kostenlos starten"* / *"Free to start"*. Apple treats **any** reference to price —
including *free*, *gratis*, *kostenlos*, discounts, or a currency amount — as inappropriate in
screenshots, app preview, name, subtitle, and promotional text. This is invisible to every ASC API
query and is not in the per-IAP gate.

### A.1 Mechanical scan (always)

Find where the screenshots/captions are authored. Screenshots are usually **generated** from a
config in the repo (the highest-yield target), e.g. a fastlane `Snapfile`/`Screengrabfile`, a
`fastlane/screenshots/` tree, or a custom generator config (the real case lived in
`tools/appstore-screens/config.js`). Grep those plus any committed caption/`.strings` files for
price tokens:

```bash
# Adjust the path glob to where captions/screenshot configs live in THIS repo.
grep -rniE 'free|gratis|kostenlos|umsonst|spar|rabatt|discount|sale|% off|gutschein|\
[€$£¥][0-9]|[0-9][.,][0-9]{2}\s*(€|eur|usd|\$)' \
  fastlane/ tools/ assets/ 2>/dev/null
```

Any hit in a string that ends up **on a screenshot, in the app name/subtitle, the preview, or
promotional text** is a 2.3.7 blocker. (A price reference inside the long *description* is allowed —
2.3.7 is about the visual metadata items. Judge by where the string is rendered.)

### A.2 Vision pass (when a vision model is available)

The mechanical scan misses price text baked into an image (a PNG with a "Free" badge, a struck-through
price, a "0 €" sticker). If the actual uploaded/exported screenshot PNGs are on disk, Read each image
and judge:

> "Does this screenshot contain any reference to price, cost, being free/gratis/kostenlos, a
> discount, a percentage off, or a currency amount — anywhere in the image, including badges,
> stickers, or device-frame overlays? Answer yes/no and quote the text."

Flag every yes as a 2.3.7 blocker with the file name and the offending text. If the PNGs are not on
disk (uploaded straight to ASC), tell the user to eyeball each screenshot for price words, and cite
the exact rule so they know what counts.

### A.3 Verdict

Present a short block, e.g.:

```
2.3.7 price-reference scan:
  ⚠ tools/appstore-screens/config.js:36  caption "Kostenlos starten"  → price reference, must change
  ⚠ tools/appstore-screens/config.js:37  caption "Free to start"      → price reference, must change
  ✓ no currency amounts in name/subtitle/promo text
```

Any `⚠` blocks Step 11: the caption must be reworded (e.g. "Jetzt loslegen" / "Get started") and the
screenshots regenerated + re-uploaded before submitting.

---

## Gate B — App-features-vs-store-claims audit (2.3 accuracy, IAP review notes)

**Why.** A real IAP review note claimed *"Sign in with Apple authentication"* for a feature that had
been deliberately removed (the `sign_in_with_apple` package was a dead dependency with no call
sites). A reviewer testing that claim fails the flow. This is a semantic mismatch between **what the
store text/review notes promise** and **what the code actually does** — not a single API field.

### B.1 What to cross-check

Collect the app's outward claims:
- store **description**, **subtitle**, **promotional text**, **What's New** (from ASC / `fastlane/metadata/`);
- per-IAP / per-subscription **review notes** and **display names**;
- any feature list in screenshots' captions.

For each concrete, testable claim (auth method, cloud sync, widget, reminders, export, offline mode,
"sign in with X", a specific price), verify it against the codebase:

```bash
# Example checks — adapt to the claims found:
grep -rniE 'sign_in_with_apple|SignInWithApple' lib/ ios/ pubspec.yaml   # claim: "Sign in with Apple"
grep -rniE 'widgetkit|home.?screen widget|app_widget' lib/ ios/ android/ # claim: home-screen widget
```

A claim is a **blocker** when the feature is named in store text/review notes but **absent or
non-functional** in code (dead dependency, removed flow, stubbed call). A claim the code *does*
implement is ✓. Cross-reference `docs/adr/` if present — a removed feature is often documented there
(the real case was recorded in an ADR).

> This is genuine multi-file LLM judgement: read the claim, understand what it means functionally,
> grep for call sites (not just the dependency), check the entitlement/config, and decide whether it
> actually works. A `grep` for the package name alone is not enough — a dead dependency still
> appears in `pubspec.yaml`.

### B.2 Verdict

```
Features-vs-claims audit:
  ✓ Cloud sync         — implemented (sync_service.dart)
  ✓ Home-screen widget — implemented (iOS WidgetKit + Android AppWidget)
  ⚠ "Sign in with Apple" in IAP review note — NO call sites in lib/; package is a dead dependency
       → fix: remove the claim from the review note (and drop the dead dependency)
```

Any `⚠` blocks Step 11 until the store text / review note is corrected (PATCH the review note via the
API per `asc-api-reference.md` §3, or edit `fastlane/metadata/`), or the feature is actually shipped.

---

## Gate D — Privacy nutrition label vs actual data collection (5.1.2)

**Why.** Apple cross-checks the App Privacy "nutrition label" against what the binary actually does.
A mismatch in **either** direction is a 5.1.2 reject: declaring a data type the app never collects,
**or** collecting one that is not declared. No single API field expresses "is this accurate" — it is
a judgement over code vs declarations.

**Inputs.** Phase 0 `analytics_tracking` (+ a quick scan of `pubspec.yaml`/`lib/` for other
data-collecting surfaces) for the *actual* side; the *declared* side **is** API-readable:

```bash
SCRIPT=~/.claude/skills/ship-to-appstore/scripts/asc-status
python3 "$SCRIPT" raw GET "/v1/apps/{app_id}/appDataUsages?limit=100&include=appDataUsageCategory,appDataUsagePurpose"
```

**Check.** Build the "actually collected" set from facts and compare to the declared usages:

| If the app… | Declare | Detected from |
|---|---|---|
| uses Supabase Auth | Email / User ID | auth usage in `lib/` |
| ships Sentry/crash SDK | Crash Data (App Functionality, Not Linked) | `analytics_tracking` crash/diagnostics |
| ships an analytics SDK | Usage Data | `analytics_tracking` analytics |
| picks/uploads photos | Photos or Videos | `image_picker`/Storage upload |
| reads location | Location | a location plugin |
| reads contacts | Contacts | a contacts plugin |

Flag every **declared-but-not-collected** (over-declaration) and **collected-but-not-declared**
(under-declaration). The publish *state* stays `? cannot-verify` (Phase 2) — this gate audits the
*contents*, which are readable.

```
5.1.2 privacy-label audit:
  ⚠ "Contacts" declared but no contacts plugin / code path found → remove or justify
  ⚠ Crash Data collected (sentry_flutter) but NOT declared → add it
  ✓ Email / User ID declared, matches Supabase Auth
```

---

## Gate E — Info.plist purpose strings: present, specific, not unused (5.1.1 / 5.1.5)

**Why.** Each sensitive iOS API needs an `NS*UsageDescription`. Missing one is a 5.1.1 reject (and an
on-device crash); a **generic** one ("This app needs camera access") is also rejected; and a purpose
string for a permission the app never exercises is a 5.1.5 reject.

**Inputs.** Phase 0 `ios_permissions` (`declared_usage_keys` vs `expected_from_plugins`).

**Check.**
- **Missing:** any key in `expected_from_plugins` not in `declared_usage_keys` → blocker; add it to
  `ios/Runner/Info.plist`.
- **Unused:** any declared key no plugin needs → likely 5.1.5; verify no native code uses it, then
  remove. Present as "verify, likely remove".
- **Generic:** read each present key's value and judge specificity — it must say *what the app does
  with the data* ("Scan receipts to add expenses", not "needs camera access"). Reword weak ones.

```
5.1.1 / 5.1.5 purpose-string audit:
  ⚠ NSCameraUsageDescription missing — mobile_scanner uses the camera → add it (blocker)
  ⚠ NSPhotoLibraryUsageDescription present but no plugin uses it → verify native, likely remove (5.1.5)
  ⚠ NSLocationWhenInUseUsageDescription = "Allow location" → too generic, reword (5.1.1)
```

---

## Gate F — Sign in with Apple required (5.1.1(iv))

**Why.** An app that offers a third-party or social login (Google, Facebook, …) **must** also offer
Sign in with Apple. Missing it is a hard 5.1.1(iv) reject.

**Inputs.** Phase 0 `social_login`.

**Check.** If `siwa_required` is true and `has_sign_in_with_apple` is false → blocker: add Sign in
with Apple alongside the existing providers. If `has_sign_in_with_apple` is true, confirm it is
**actually wired** (a real button + call site), not a dead dependency — the same dead-dependency trap
Gate B caught in reverse. Email/password or Supabase-native auth alone does **not** trigger this — say
so and pass.

```
5.1.1(iv) Sign in with Apple:
  ⚠ google_sign_in present, no sign_in_with_apple → add Sign in with Apple (blocker)
  ✓ (or) no third-party login → not required
```

---

## Gate G — Subscription disclosure + Terms/Privacy links (3.1.2)

**Why.** A subscription paywall must disclose, on the purchase screen itself: the subscription **title**,
**duration**, **price per period**, and **what's included** — and the binary must contain **functional
links** to the Terms of Use (EULA) and Privacy Policy. Missing disclosures are a very common 3.1.2
reject for first subscriptions.

**Inputs.** Phase 0 `paywall_hints` (+ `in_app_purchases`). Only in scope when the app has
auto-renewable subscriptions.

**Check.** Inspect the paywall file(s) for: each plan's price + period rendered, a benefits/what's-included
list, and two reachable links (Terms/EULA + Privacy). Confirm the store metadata has a Privacy Policy
URL (and, for custom terms, a EULA — else Apple's standard EULA applies). A link that is a dead
`Text` (not a tappable URL) does not count.

```
3.1.2 subscription disclosure:
  ✓ Monthly/Yearly/Lifetime show price + period on the paywall
  ⚠ No "Terms of Use (EULA)" link on the paywall → add a tappable link (blocker)
  ✓ Privacy Policy link present + privacy URL set in ASC
```

---

## Gate H — External purchase / steering links (3.1.1)

**Why.** Digital goods/services consumed in-app must use Apple IAP. A link or CTA that steers users to
buy/subscribe **outside** the app (a web checkout, "manage your plan on our website", Stripe/PayPal
for digital content) is a 3.1.1 reject.

**Check.** Grep code and store/paywall text for outbound purchase paths:

```bash
grep -rniE 'stripe|paypal|checkout\.|buy (on|at) (our )?(web|site)|subscribe on (the )?web|\
manage (your )?(subscription|plan) (on|at)|payment(s)?\.(com|io)|lemonsqueezy|paddle' \
  lib/ fastlane/metadata/ 2>/dev/null
```

A hit that routes **digital** purchases off-platform is a blocker (physical goods/services are exempt —
judge what is being sold). Reader-type and approved external-link entitlements are narrow exceptions;
do not assume one applies.

```
3.1.1 external-purchase scan:
  ⚠ lib/paywall.dart: "Subscribe on hellerio.de" link → digital goods must use IAP (blocker)
  ✓ no Stripe/PayPal/web-checkout paths for digital content
```

---

## Gate I — Privacy & Support URL liveness (needs `WebFetch`)

**Why.** Apple opens the Privacy Policy and Support URLs during review. A 404, a parked domain, or a
page that is not actually a privacy policy / support page draws a reject. "Set in ASC" (Phase 2) only
proves the field is non-empty, not that the URL works.

**Check.** With `WebFetch`, fetch both URLs (from `fastlane/metadata/` or the ASC localizations) and
verify each returns a real page of the right kind:

```
WebFetch: {privacy_policy_url}  → "Is this a working privacy policy page (not a 404/parked/login wall)?"
WebFetch: {support_url}         → "Is this a reachable support/contact page (not a social profile)?"
```

The Support URL must not be a bare social-media profile. If `WebFetch` is unavailable, tell the user to
open both URLs in a browser and confirm — do not silently skip.

```
URL liveness:
  ✓ https://hellerio.de/datenschutz → privacy policy, 200
  ⚠ https://hellerio.de/support → 404 → fix the URL or publish the page (blocker)
```

---

## Gate J — Demo account in review notes (2.1)

**Why.** If any part of the app requires login, the reviewer needs working credentials — otherwise
they cannot exercise the app and reject under 2.1 ("could not sign in / access the app"). 

**Check.** In scope only when the app has a login that gates content. Confirm the **App Review
Information** (ASC) or the IAP/version review notes contain a working demo username + password (or an
explicit note that no login is required and how to reach all features). For a passwordless/anonymous
auth model (like the reference app), state that no demo account is needed and the review note explains
the model.

```
2.1 reviewer access:
  ⚠ App requires login, no demo credentials in App Review Information → add them (blocker)
  ✓ (or) no login gate / passwordless — review note explains access
```

---

## Gate K — Account-deletion depth (5.1.1(v))

**Why.** An app that creates accounts must offer **in-app** account deletion that removes the *account*,
not just local data, and is reachable inside the app (an email-to-support flow alone is insufficient
for most apps). Phase 0 only greps for markers; this gate verifies depth.

**Inputs.** Phase 0 `account_deletion`.

**Check.** When accounts exist, open the deletion flow and confirm it (a) calls a real server-side
deletion (Supabase Auth Admin `DELETE /auth/v1/admin/users/{id}` or an RPC that removes the user), not
just a local sign-out/cache clear, and (b) is reachable from the app UI. If `likely_present: false`
while accounts exist → blocker.

```
5.1.1(v) account deletion:
  ⚠ "deleteAccount" only clears local prefs, no server delete → wire Supabase Auth admin delete (blocker)
  ✓ in-app deletion calls the Supabase Auth admin API and is reachable from Settings
```

---

## Gate L — UGC safety controls (1.2)

**Why.** An app with user-generated content needs a content filter, an in-app **report** mechanism, a
**block** mechanism, and a published EULA. Missing controls are a 1.2 reject.

**Inputs.** Phase 0 `user_generated_content` (conservative heuristic — treat as "investigate").

**Check.** When UGC is present, confirm: a way to flag/report objectionable content, a way to block an
abusive user, some filtering/moderation, and an EULA with a zero-tolerance clause. `has_report_or_block`
is a hint, not proof — verify the controls exist and are reachable.

```
1.2 UGC safety:
  ⚠ Comments feature found, no report/block UI → add report + block + EULA (blocker)
  ✓ (or) no UGC detected → not in scope
```

---

## Gate M — Placeholder / completeness scan (2.1)

**Why.** Placeholder content, lorem ipsum, obvious test/demo data, dead buttons, or empty broken
screens are 2.1 App Completeness rejects. Some of this is visible only in the screenshots.

**Check.** Grep store text and `lib/` for placeholder tokens, and (vision pass) scan the screenshot
PNGs for unfinished UI:

```bash
grep -rniE 'lorem ipsum|todo|fixme|placeholder|dummy|test ?data|coming soon|\
\bxxx\b|\blipsum\b|sample text' lib/ fastlane/metadata/ 2>/dev/null
```

Vision (if available), per screenshot: *"Does this screenshot show placeholder/lorem-ipsum/obviously
fake data, an empty error/broken state, or an unfinished screen?"* Flag every hit.

```
2.1 completeness:
  ⚠ lib/home.dart: "TODO: real data" rendered in the UI → replace before submit
  ⚠ screenshot_03.png shows an empty error state → recapture with real content
  ✓ no placeholder tokens in store text
```

---

## Gate C — Reject-text classification (only in the reject handler)

Not a pre-submit gate — used in Phase 3 §3.8 when a rejection arrives. The Resolution Center text is
**not** API-readable (`asc-api-reference.md` §8), so the user must paste it. Then apply LLM judgement:

1. **Identify the cited guideline(s)** (e.g. `2.1(b)`, `2.3.7`, `5.1.1`) and whether it is
   single- or multi-cause.
2. **Map each cause to the artifact that fixes it** (IAP screenshot, caption reword, privacy label,
   account deletion, …) via the §3.8.2 table.
3. **Separate actionable text from boilerplate.** "Upload a new binary" in a 2.1(b) IAP reject is
   usually boilerplate (`asc-api-reference.md` §10) — judge it against the real blocking condition
   rather than rebuilding reflexively.
4. **Correlate cautiously with telemetry.** Sentry/crash data near review time can *suggest* a cause
   but is not proof — a plausible crash-at-review-time hypothesis was wrong in a real run until the
   pasted reject text corrected it. Never assert a root cause from telemetry timing alone over the
   reviewer's own words.
