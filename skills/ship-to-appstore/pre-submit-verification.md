# Pre-Submit Verification — LLM/vision-assisted gates

Loaded by Phase 3 **before Step 11 (Submit for Review)**. These catch the reject reasons that are
*not* expressible as an API field — they need judgement over text and images. Both gates below come
straight from real rejections the API-only checks missed.

Run these as the last gate before submit. Each is a hard blocker only when it finds a concrete hit;
a clean pass is logged and the loop proceeds. Where a vision model is unavailable, fall back to the
mechanical scan and tell the user the visual pass was skipped (do not silently drop it).

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
