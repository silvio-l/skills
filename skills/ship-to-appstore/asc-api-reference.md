# ASC REST API Reference (hard-won, from real first-release runs)

Loaded on demand by Phase 2/Phase 3 when querying App Store Connect directly. Every entry below
was learned from an actual rejection-recovery run — the traps here are the ones that produced a
**false "missing"** report or a wasted submit. Treat this as the truth source over guessed paths.

> **The bundled `scripts/asc-status` (read-only) already encodes the correct paths below.** Prefer
> it over raw calls; use this file to understand its output and to do follow-up queries it does not
> cover. The few **write** actions worth scripting (review-screenshot upload, reviewNote PATCH,
> re-submit-after-reject, publish) are bundled in `scripts/asc-submit`, which is **dry-run by default**
> and only mutates with an explicit `--yes` — see §11.

---

## 1. Auth (per call)

ES256 JWT, `aud=appstoreconnect-v1`, `kid`=Key ID header, `iss`=Issuer ID, short `exp` (≤20 min).
Mint a fresh token per call; never log it. `scripts/asc-status` and the project's
`tools/asc-api.py` both do this. The `.p8`, the token, and the Issuer ID never go to stdout.

---

## 2. The two-namespace IAP trap (most important)

**Non-consumables / consumables and auto-renewable subscriptions live in SEPARATE resource trees.**
A readiness check that hits only one misses the other entirely (observed: a script that queried only
`inAppPurchasesV2` found 1 of 3 products and reported the app "ready" while two subscriptions were
invisible).

| Product type | List endpoint |
|---|---|
| Non-consumable / consumable | `GET /v1/apps/{app_id}/inAppPurchasesV2?limit=200` |
| Auto-renewable subscription | `GET /v1/apps/{app_id}/subscriptionGroups?limit=200` → for each group `GET /v1/subscriptionGroups/{group_id}/subscriptions?limit=200` |

Both must be queried. Follow `links.next` for pagination (the bundled script does).

`fields[inAppPurchasesV2]=...availableInAllTerritories` returns **HTTP 400** — some field names are
not valid on this resource. If a `fields[]` filter 400s, drop it and take the default attributes.

---

## 3. Per-product state machine

`state` values you will see: `MISSING_METADATA` → `READY_TO_SUBMIT` → `WAITING_FOR_REVIEW` →
`IN_REVIEW` → `APPROVED` (and `DEVELOPER_ACTION_NEEDED`, `REJECTED`).

- `READY_TO_SUBMIT` = "fully configured, never submitted." A product only reaches it once **price +
  at least one App Review screenshot + a localized display name** are all present.
- `WAITING_FOR_REVIEW` is **normal and expected** after submit — not a blocker. Do not flag it.
- The attachment step (adding the IAP to the version in the UI) does **not** flip the state; only the
  actual submit does. So `READY_TO_SUBMIT` + version `READY_FOR_REVIEW` is the correct pre-submit
  resting state.

---

## 4. The App Review screenshot — v1 vs v2 path (silent false-negative)

The single most-missed field, and the one whose **read path lies**. Reading it on the wrong API
version returns a false "none"/404 even when a screenshot exists:

| Product type | Correct read path |
|---|---|
| Non-consumable | `GET /v2/inAppPurchases/{id}/appStoreReviewScreenshot` (the **v2** prefix is required) |
| Subscription | `GET /v1/subscriptions/{id}/appStoreReviewScreenshot` |

A `404`/`400` on these is **cannot-verify**, not "missing" — classify it as `?` and confirm in the
UI. Never report a screenshot as absent from a non-200. (Shortcut: if a product is already
`READY_TO_SUBMIT`, a screenshot is implicitly present — Apple won't grant that state without one.)

**Uploading** a screenshot is a 4-step reservation flow (delete existing → reserve → PUT each
presigned chunk → PATCH `uploaded:true`+checksum). The two product kinds use **different resources
and a different relationship name** — getting these wrong is the usual cause of a failed upload:

| | Non-consumable (IAP) | Subscription |
|---|---|---|
| Reserve `POST` | `/v1/inAppPurchaseAppStoreReviewScreenshots` | `/v1/subscriptionAppStoreReviewScreenshots` |
| Relationship in body | `inAppPurchaseV2` → `{type:"inAppPurchases", id}` (note: rel **type** is the v1 name `inAppPurchases`, not `inAppPurchasesV2`) | `subscription` → `{type:"subscriptions", id}` |
| Delete existing | `DELETE /v1/inAppPurchaseAppStoreReviewScreenshots/{id}` | `DELETE /v1/subscriptionAppStoreReviewScreenshots/{id}` |

Reservation body (IAP shown; `attributes` carry `fileName`+`fileSize`):

```json
{"data":{"type":"inAppPurchaseAppStoreReviewScreenshots",
  "attributes":{"fileName":"paywall.png","fileSize":123456},
  "relationships":{"inAppPurchaseV2":{"data":{"type":"inAppPurchases","id":"<iap_id>"}}}}}
```

The response carries `attributes.uploadOperations` — for each, `PUT` `data[offset:offset+length]`
to `operation.url` with the operation's `requestHeaders` (no Authorization header — it is presigned).
Then commit:

```json
PATCH /v1/inAppPurchaseAppStoreReviewScreenshots/{id}
{"data":{"type":"inAppPurchaseAppStoreReviewScreenshots","id":"{id}",
  "attributes":{"sourceFileChecksum":"<md5-hex>","uploaded":true}}}
```

This is a **mutation**. `scripts/asc-submit screenshot <bundle_id> <product_id> <png>` performs the
whole flow (auto-detecting IAP vs subscription) — dry-run unless `--yes` is passed. Otherwise guide
the user through the ASC UI (Monetization → the product → App Review Information → upload).

---

## 5. Price is not directly readable — read the schedule, not the tier table

`GET /v2/inAppPurchases/{id}/pricePoints` returns **all ~800 possible tiers**, not the configured
price. The configured price lives in the *schedule*:

- Non-consumable: `GET /v1/inAppPurchasePriceSchedules/{id}?include=manualPrices,automaticPrices,baseTerritory`
- Subscription: `GET /v1/subscriptions/{id}/prices?include=subscriptionPricePoint`

`manualPrices.total == 0` = price genuinely unset. The resource is named
`inAppPurchasePriceSchedules` (not `iapPriceSchedules`).

---

## 6. Following relationship links beats guessing paths

For IAP sub-resources (price, localizations, screenshot, content), `GET` the product object and read
`relationships.<name>.links.related` — ASC returns the correct URL itself. Guessing v1-style paths
(`?include=iapPriceSchedule`, `/prices`) on a v2 product returns `400`/`404` and is the root of most
false "not configured" reports.

---

## 7. Submission is `reviewSubmissions`, not `appStoreVersionSubmissions`

Apple migrated submission to the `reviewSubmissions` resource. The old one is read/delete-only:
`POST /v1/appStoreVersionSubmissions` → **403** *"Allowed operation is: DELETE."*

- **Read open submission state:** `GET /v1/reviewSubmissions?filter[app]={app_id}&filter[platform]=IOS`
  → `state`: `READY_FOR_REVIEW`, `WAITING_FOR_REVIEW`, `IN_REVIEW`, `UNRESOLVED_ISSUES` (an open
  reject), `COMPLETING`, `COMPLETE`. This catches a `REJECTED`/`UNRESOLVED_ISSUES` app **without the
  web UI**.
- **Re-submit after a reject** (when the existing submission is `UNRESOLVED_ISSUES` and the cause is
  fixed): `PATCH /v1/reviewSubmissions/{id}` with `{"data":{"type":"reviewSubmissions","id":"…",
  "attributes":{"submitted":true}}}` → state flips to `WAITING_FOR_REVIEW`. This is a mutation — do
  it only with explicit user confirmation.

Also useful: `GET /v1/apps/{app_id}/appStoreVersions?fields[appStoreVersions]=versionString,appVersionState`
→ `appVersionState=REJECTED` is the version-level reject signal.

---

## 8. What the API genuinely **cannot** see (always `?` cannot-verify → ASC UI)

1. **Resolution Center rejection text.** The `iris` backend returns `401`/`404` to an API-key token —
   it needs a 2FA web session. **You must ask the user to paste the rejection email/Resolution Center
   text**; it can never be fetched automatically. (Phase 3 §3.8.1 already does this — this is *why*.)
2. **Privacy nutrition label** (publish state and contents). Confirmed 404 on 18+ path variants;
   fastlane has no `download_app_privacy_details`. UI-only.
3. **Paid Apps Agreement** status (App Store Connect → Business). If it is not accepted, IAPs **cannot
   be purchased** and the reviewer hits *"product is not available for purchase"* → a 2.1(b) reject.
   Not API-readable — confirm in the UI before any first IAP release.
4. **Whether an IAP is attached to the specific version.** `GET /v1/appStoreVersions/{id}/inAppPurchases`
   → 404 (deprecated). No current endpoint reads the version→IAP link. *Indirect* signal: after a
   manual attach in the UI, a previously `REJECTED` version flips to `READY_FOR_REVIEW`; and after a
   successful submit, ready+attached products flip `READY_TO_SUBMIT → WAITING_FOR_REVIEW`. For a
   first submission with no prior rejection there is **no** API signal — confirm attachment in the UI.

---

## 9. fastlane `deliver` re-submit-after-reject bug

After a reject is resolved and the version is back to `READY_FOR_REVIEW`, `fastlane deliver`'s
`ensure_version!` tries to **POST a new version** with the same version string → 422 *"version number
has been previously used."* fastlane is unaware a `READY_FOR_REVIEW` version already exists. **Do not
re-run the release lane to re-submit after a reject** — use the `PATCH /v1/reviewSubmissions/{id}`
path in §7 instead.

---

## 10. "Upload a new binary" is often boilerplate

A 2.1(b) reject email almost always says *"submit your In-App Purchases and upload a new binary."*
When the **sole** cause is that the IAPs were not submitted (not a code/binary defect), no new binary
is needed — attach the IAPs + re-submit with the existing build. Judge the email's instructions
against the actual blocking condition rather than rebuilding reflexively.

---

## 11. Releasing an approved version is scriptable (no ASC UI needed)

A version in `PENDING_DEVELOPER_RELEASE` (the state after Apple approves a *manual*-release
submission) does **not** require clicking "Release this version" in the web UI. Release it via:

```
POST /v1/appStoreVersionReleaseRequests
{"data":{"type":"appStoreVersionReleaseRequests",
  "relationships":{"appStoreVersion":{"data":{"type":"appStoreVersions","id":"<version_id>"}}}}}
```

`scripts/asc-submit publish <bundle_id>` finds the `PENDING_DEVELOPER_RELEASE` version and does this
(dry-run unless `--yes`). **RevenueCat/StoreKit note:** after release, allow up to ~24 h for newly
approved IAP products to propagate to StoreKit before announcing — fresh products can briefly read as
unavailable on device.

---

## 12. The Review-Submission API has no item type for IAPs/subscriptions

`reviewSubmissions` carries an `items` relationship, but the only valid item types are
`appStoreVersion`, `appEvent`, `customProductPage`, `experiment`, `gameCenter`, and
`backgroundAsset` — there is **no** IAP/subscription item type (verified against the REST schema).
This is *why* the very **first** submission of a subscription/IAP must be attached to the version
**manually in the ASC UI** before submitting (App → Distribution → the version → "In-App Purchases
and Subscriptions" → select the products). After the first approval, subscriptions submit
independently and the manual attach disappears. There is no API path that creates the version→IAP
attachment — confirm it in the UI (§8, item 4).

---

## 13. The MISSING_METADATA → empty-paywall chain (why the screenshot gate is functional, not cosmetic)

A product stuck on `MISSING_METADATA` (most often: no App Review screenshot) is not just a review
blocker — it is **invisible to StoreKit**. RevenueCat SDK v9 (StoreKit 2) filters out offering
packages whose store products StoreKit cannot resolve, so `offerings.current` comes back `null` and
the in-app paywall shows "prices unavailable". So clearing every product to `READY_TO_SUBMIT` (which
requires the screenshot) fixes both the 2.1(b) reject **and** a broken live paywall. Treat the
screenshot as functionally required, not optional polish.

---

## 14. fastlane `deliver` traps when submitting with an API key

- **`precheck_include_in_app_purchases: false` is mandatory.** With API-key auth, spaceship cannot
  inspect IAPs, and `deliver`'s precheck aborts the submit if this is left on. Set it false on any
  `release`-style lane.
- **Pin `app_version` + `build_number` from `pubspec.yaml`.** Otherwise `deliver` attaches "whatever
  is newest" on ASC rather than the exact build you uploaded.
- **Export-compliance at submit:** pass `submission_information: {export_compliance_uses_encryption:
  false, export_compliance_is_exempt: true, add_id_info_uses_idfa: false}` for a standard
  HTTPS-only app so the submit does not stop to ask.
