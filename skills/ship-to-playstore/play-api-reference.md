# Play Developer API Reference

Loaded on demand by Phase 2 (`play-status`) and Phase 3 (`play-submit`) when querying or mutating
Google Play directly. This is the **API contract** both scripts build on. The current stable surface
is the Play Developer API **v3** (`androidpublisher.googleapis.com/androidpublisher/v3`); the OAuth
scope and the edits/tracks/bundles model are stable architectural facts. This document deliberately
states **no** transient detail — deprecation windows, quota numbers, or per-field policy shifts —
those are Phase-1 freshness research, never training memory.

> **The bundled `scripts/play-status` (read-only) already encodes the read paths below.** Prefer it
> over hand-rolled calls; use this file to understand its output and to plan the write path. The
> bundled `scripts/play-submit` (slice 04) encodes the **mutation** paths; it is **dry-run by default**
> and only mutates on an explicit `--yes`, one mutation kind per checkpoint (PRD §4.1).

---

## 1. Auth — OAuth2 service-account JWT (RS256)

Play Developer API auth uses a **Google Cloud service-account JSON**, not an interactive login. The
flow is a self-signed JWT exchanged for an access token:

1. Build the unsigned assertion = base64url(header) + "." + base64url(payload), where
   - header = `{"alg":"RS256","typ":"JWT"}`
   - payload = `{"iss": <client_email>, "scope": "https://www.googleapis.com/auth/androidpublisher", "aud": "https://oauth2.googleapis.com/token", "iat": <now>, "exp": <now+3600>}`
2. RS256-sign the assertion with the service-account **private key**.
3. POST to `https://oauth2.googleapis.com/token` with
   `grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer` and `assertion=<signed jwt>` →
   `{"access_token": "...", "expires_in": 3600}`.

**Signing caveat:** Python stdlib has no RS256 signer. `scripts/play-status` shells out to `openssl`
(`openssl dgst -sha256 -sign`) — `openssl` is assumed on PATH (see `phase2-play-status.md`
prerequisites). The private key is fed to openssl on stdin and is **never** written to disk, logged,
or printed. The token mint is the **only** POST this skill's read path makes — it is authentication,
not a Play API mutation.

**Token cache:** the access token is valid for ~1 hour. A long-running Phase 3 loop may reuse it
within its lifetime; minting a fresh token per call is simpler and safe for the read path. Never log
the token, the assertion, the Authorization header, or the private key.

### 1.1 Why a service account (not an API key)

A plain Google API key authorises only a handful of read endpoints. The full Play surface
(tracks, edits, bundles, IAP) requires an **OAuth2 access token minted from a service account** that
has been **linked in Play Console → Users and permissions** with app-level (or account-level) rights
and the Play Console role that grants the intended actions. A service account that exists in Google
Cloud but is **not linked in Play Console** returns **403** — the single most common "I minted a
token and everything 403s" failure. See §8 (cannot-verify causes).

---

## 2. The edits transaction — the safe dry-run primitive

Everything that mutates a Play app lives inside an **edit**: a short-lived transactional context.

```
POST .../applications/{packageName}/edits            → creates an edit (returns editId + expiry)
  … mutations inside the edit (bundles upload, tracks, listings, IAP, …) …
POST .../applications/{packageName}/edits/{editId}/commit   → publishes ALL mutations atomically
DELETE .../applications/{packageName}/edits/{editId}        → discard (or let it expire)
```

**Rollback = don't commit.** An uncommitted edit changes nothing live. This is the cleanest dry-run
primitive in any store API and `scripts/play-submit` leans on it: it creates an edit, stages every
mutation, shows the user exactly what would land, and only calls `commit` on an explicit `--yes` for
the commit checkpoint specifically. If the user declines, the edit is deleted (or left to expire) and
**nothing reaches a track**.

Properties that matter:

- An **edit expires** (on the order of hours) if not committed — a stale edit id is a common error.
- Mutations inside one edit are **atomic**: commit publishes all or none.
- `play-status` (read-only) does **not** create edits. It reads the edit-free GET namespaces live
  (§5, §6) and, when an explicit `--edit-id` is supplied, reads tracks/listings/appDetails **inside
  an existing edit** without mutating it. Creating an edit is `play-submit`'s job.

---

## 3. Bundles — `edits.bundles.upload`

Inside an edit:

```
POST .../applications/{packageName}/edits/{editId}/bundles
       (multipart: the .aab)
  → returns {versionCode: <int>}   # the uploaded bundle's versionCode
```

- The returned **versionCode** is the monotonic identity Play tracks; it must be strictly greater
  than the last versionCode on the target track (Phase 3 Step 1 / Step 4 collision check).
- Upload happens **inside an edit** — nothing is live until `commit`. A bundle uploaded to an
  uncommitted edit is a safe dry-run.
- APK upload via this surface is legacy; AAB is the path for new apps (Phase 1 researches the exact
  current acceptance rules — do not state them from memory here).

`scripts/play-status` never uploads. `scripts/play-submit` (slice 04) uploads inside an edit and
gates `commit` behind `--yes`.

---

## 4. Tracks — releases, `userFraction`, status, and the track ladder

Inside an edit, each track holds a list of `releases`:

```
GET    .../applications/{packageName}/edits/{editId}/tracks
PUT    .../applications/{packageName}/edits/{editId}/tracks/{track}
```

A release object:

```json
{
  "name": "...",
  "versionCodes": ["42"],
  "releases": [{
    "name": "1.2.3",
    "versionCodes": [42],
    "status": "inProgress",
    "userFraction": 0.1,
    "releaseNotes": {...}
  }]
}
```

- **`status` values:** `draft`, `inProgress`, `halted`, `completed`. `inProgress` + `userFraction`
  is a **staged rollout**; `completed` (fraction reaches 1.0) is fully released; `halted` pauses a
  staged rollout without rolling back. Promotion and halt are further `tracks.update` calls.
- **`userFraction`** is a per-release float (e.g. 0.01 → 1.0). Phase 3 Step 10a/12 uses it to stage
  and to halt; there is deliberately **no default fraction** — `--rollout` is explicit and required.
- **Track ladder:** Internal Testing → Closed Testing → Open Testing → Production. Internal is
  instant (no review) and is the recommended smoke-test target first; promotion up the ladder is a
  track reassignment. Phase 3 recommends Internal first, then promote.

`scripts/play-status` reads tracks (with `--edit-id`) and renders each track's top release as
`<version> (<status>) — rollout <pct>%`. `scripts/play-submit` mutates tracks inside an edit with an
explicit `--track` and `--rollout`, gated behind `--yes`.

---

## 5. The two IAP namespaces (the trap ported from iOS)

Play Billing splits the product catalog across **two separate resource trees**. A readiness check
that hits only one **silently misses the other** — the same shape as the iOS `inAppPurchasesV2` vs
`subscriptionGroups` trap. Both namespaces are **edit-free GETs** (no edit needed to list):

| Product type | List endpoint |
|---|---|
| One-time (consumable / non-consumable) | `GET .../applications/{packageName}/inappproducts` |
| Auto-renewing subscriptions | `GET .../applications/{packageName}/subscriptions` (the `monetization.subscriptions` resource; v3 path token is `/subscriptions`) |

`scripts/play-status` queries **both**, always. Reporting from only `inappproducts` would render an
app with only subscriptions as "no IAP" — a false green before a release commit. Per-product
`status` (`published`, `draft`, …) drives the Step 10b gate: any product not publishable is a hard
blocker before commit (the Play-Billing analogue of the iOS 2.1(b) reject).

### 5.1 Subscriptions: base plans + offers

A subscription is not directly purchasable — it exposes **base plans** (the renewing terms), and each
base plan may carry **offers** (introductory/promo). A subscription with no base plan cannot be
published. The hierarchy is read via:

```
GET .../applications/{packageName}/subscriptions
  → each subscription: basePlans[] → each base plan: offers[]
```

First-release readiness = every subscription has at least one base plan in a publishable state. This
is Phase-1-researched detail (base-plan rules evolve); the structural fact that the catalog is
two-namespace and subscriptions need base plans is stable.

---

## 6. Listings, images, appDetails

Also edit-scoped:

- `GET/PUT .../edits/{editId}/listings` — per-locale store listing (title, short/full description,
  etc.). `images` are a sub-resource (`.../listings/{language}/{imageType}`).
- `GET/PUT .../edits/{editId}/details` — `appDetails`: contact email, website, default language,
  privacy policy URL. This is where the **Privacy Policy URL** and **contact details** live.
- **Feature graphic, phone/tablet screenshots, and the listing icon live in Play Console** — read
  presence via the `images`/listings surface where possible; many are UI-managed and surface as
  `? cannot-verify` when the API does not expose their published state.

`scripts/play-status` reads listings/appDetails with `--edit-id` and renders listing completeness
from the locale count; `play-submit` (slice 04) writes them inside an edit.

---

## 7. Data Safety form

The Data Safety form (declared data collected/shared, encryption, **whether data deletion is
offered**) is **driven from Phase 0 facts** (`data_safety_hints`, `permissions`), never asked of the
user. Its **published state, however, is not reliably API-readable** — there is no clean read
endpoint that says "Data Safety is published and current". So:

- The form's **contents** can be drafted from Phase 0 facts and written through the Console (or the
  available write surface) inside a release.
- The form's **publish state** is `? cannot-verify` — confirm in Play Console. Never report it as
  "not done" from inference alone.

---

## 8. What the API genuinely **cannot** see (always `? cannot-verify` → Play Console UI)

These four are the Play analogues of the ASC "not queryable" set. Each is presented as
`? cannot-verify` with a pointer to the Console — never as "not done" or "missing":

1. **Play App Signing enrolment state.** Whether the app is enrolled (and thus whether the upload key
   can be reset) is only partially exposed. Phase 0's `signing.play_app_signing_enrollable_from_repo`
   is a repo heuristic only; the real enrolled/not-enrolled fact is `? cannot-verify` from the API.
   First-release enrolment is a one-time, irrevocable UI decision (Phase 3 Step 2).
2. **Data Safety *published* state.** §7 — the contents are draftable from facts, the publish state
   is not queryable.
3. **Policy decision text.** A reject / suspension notice cites policy names (*Minimum Functionality*,
   *Payments*, *Permissions*, …) and decision text that is **not reliably API-readable** — the user
   must paste it, exactly as on iOS. Phase 3's reject handler (Gate C) classifies pasted text.
4. **Pre-launch report verdict.** Play auto-runs instrumentation on internal builds; the verdict is
   advisory and surfaces in the Console. The skill **warns, does not block**, on it (it can lag).

---

## 9. The edits transaction as the mutation safety net (summary for `play-submit`)

For slice 04's `play-submit`, the edits transaction is what makes Play's "full API power, every
mutation a discrete opt-in checkpoint" (PRD §4.1) tractable:

- Upload, track release, staged rollout, listing/IAP/Data-Safety writes all stage **inside one edit**
  and publish **only on `commit`**.
- Each distinct mutation kind is a separate `--yes` checkpoint; nothing is batched.
- `--track` and `--rollout` are explicit, required, no defaults — "oops I shipped to prod" is
  structurally hard.
- After any commit, **re-read the target track** via a fresh edit's GET to confirm the version code
  landed and the release `status` is as expected — never trust the commit log alone.

---

## 10. Credential location convention (OQ1, locked)

- **In-repo (gitignored):** `android/api/play-service-account.json`. Phase 0 detects it as
  `credentials.service_account_json[].path`. The path MUST be in `.gitignore` — the JSON contains a
  private key.
- **Out-of-repo alternative:** `~/.config/play/play-service-account.json` (this skill's convention).
  Unlike Apple's `.p8`, the service-account JSON **can** be re-downloaded from Google Cloud Console,
  so an out-of-repo copy is a fine primary source.
- **`key.properties` / keystore:** Phase 0 surfaces **paths and alias presence only** — the passwords
  in `key.properties` (`storePassword`, `keyPassword`, `keyAliasPassword`) are **never** read, logged,
  or emitted. The signing section reports `signing_config_set` + `keystore_hints` (relative paths).

---

## 11. Fastlane `supply` precedence (OQ2, locked)

Lane-first, mirroring the iOS posture: if Phase 0's `fastlane_lanes` contains `supply` or any
`play_*` lane, the skill prefers Fastlane `supply` (e.g. `bundle exec fastlane run supply
--skip_upload_*` for a dry-run) over raw Play Developer API calls. Otherwise the raw API (this skill's
scripts) is the strategy. `scripts/play-status` reports the recommended strategy letter in the
situation overview regardless of which path it used for its own GETs.
