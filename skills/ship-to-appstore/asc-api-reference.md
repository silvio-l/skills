# ASC REST API Reference (hard-won, from real first-release runs)

Loaded on demand by Phase 2/Phase 3 when querying App Store Connect directly. Every entry below
was learned from an actual rejection-recovery run — the traps here are the ones that produced a
**false "missing"** report or a wasted submit. Treat this as the truth source over guessed paths.

> **The bundled `scripts/asc-status` already encodes the correct paths below.** Prefer it over raw
> calls; use this file to understand its output and to do follow-up queries it does not cover.

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

**Uploading** a screenshot is a 5-call reservation flow (create reservation → PUT each presigned
chunk → PATCH `uploaded:true`+checksum), with non-consumables using
`inAppPurchaseAppStoreReviewScreenshots` and subscriptions
`subscriptionAppStoreReviewScreenshots`. It is a **mutation** — out of scope for the read-only
bundled script; guide the user through the ASC UI (Monetization → the product → App Review
Information → upload) unless they explicitly ask the agent to script the upload.

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
