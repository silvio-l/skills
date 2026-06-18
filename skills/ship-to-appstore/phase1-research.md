# Phase 1 — Freshness Research

> **Loaded on demand** by the orchestrator (SKILL.md Entry point, step 4).
>
> **Prerequisite tools:** `WebSearch` and `WebFetch` — both must be available in the active session.
> If either is unavailable, halt immediately and tell the user: "Live web access is required for
> freshness research. Training-memory Apple requirements must not be substituted — please re-run
> this skill in a session with web search enabled."

---

## HARD RULE — No Training-Memory Requirements

**No concrete Apple requirement may be asserted from training memory.** This covers version
numbers, pixel dimensions, date deadlines, field names, API endpoint paths, or any other specific
value that Apple controls and may change between OS cycles or policy updates.

Every hard requirement stated during this skill run must either:

1. Come from a live search or fetch performed **in this session**, or
2. Be explicitly flagged inline: *"may be outdated — verify on developer.apple.com before acting."*

When Apple terminology is unclear or a search result is ambiguous, **re-research live** rather
than infer from training. A correct answer one web-search away is never worth hallucinating.

This rule is in effect for all phases that follow — not just Phase 1.

---

## 1. Run the Five Domain Searches

Perform all five searches **before** giving the user any release-step instructions. Use the
current year (and month when useful) in each query to anchor freshness. The order does not
matter; all five must complete before the Freshness Report in §2.

### 1.1 Xcode / SDK Minimum Versions

```
WebSearch: "App Store Connect minimum Xcode version required <YYYY>"
WebSearch: "minimum iOS deployment target App Store required <YYYY>"
```

Establish:
- Minimum Xcode version App Store Connect currently accepts for new binary uploads.
- Minimum iOS deployment target currently enforced.
- Whether an upcoming deadline change is announced (Apple typically posts 90-day advance notices
  on developer.apple.com/news/).

If results conflict or are sparse, fetch the canonical source:

```
WebFetch: https://developer.apple.com/news/releases/
WebFetch: https://developer.apple.com/ios/submit/
```

### 1.2 Screenshot Specifications

```
WebSearch: "App Store Connect screenshot requirements <YYYY> devices pixel sizes required"
WebSearch: "required screenshot sizes iPhone iPad App Store <YYYY>"
```

Establish:
- Which device display sizes are **required** (submission blocked without them) vs. optional.
- Exact pixel dimensions for each required size (width × height at 1× logical resolution).
- Whether Apple recently added or removed a required device size (e.g., after a new iPhone launch
  cycle).
- Whether localizations share the same required sizes or have separate requirements.

Canonical source if needed:

```
WebFetch: https://developer.apple.com/help/app-store-connect/reference/screenshot-specifications
```

### 1.3 Privacy Obligations

```
WebSearch: "App Store privacy nutrition label requirements <YYYY>"
WebSearch: "App Store account deletion requirement status <YYYY>"
WebSearch: "App Tracking Transparency required when App Store <YYYY>"
```

Establish:
- **Nutrition labels:** which data-type categories are required in the App Store Connect privacy
  questionnaire; whether any new data-use disclosures have been added.
- **Account-deletion mandate:** what Apple requires (in-app deletion flow), where it must appear,
  and whether the enforcement deadline has passed or is pending.
- **ATT (App Tracking Transparency):** when `NSUserTrackingUsageDescription` is mandatory, which
  tracking uses trigger the prompt, and current review consequences for omitting it.
- Any new privacy-related review guideline changes announced for the current year.

Canonical sources if needed:

```
WebFetch: https://developer.apple.com/app-store/app-privacy-details/
WebFetch: https://developer.apple.com/news/
```

### 1.4 Export Compliance / Encryption Declaration

```
WebSearch: "App Store export compliance encryption declaration rules <YYYY>"
WebSearch: "ITSAppUsesNonExemptEncryption HTTPS exempt App Store Connect <YYYY>"
```

Establish:
- Current rules for when an app must declare encryption use (Yes / No / Exempt categories).
- Whether standard HTTPS/TLS usage still qualifies as exempt and what the expected plist key
  value is for a standard-networking-only app.
- Any recent changes to US Bureau of Industry and Security (BIS) classification that affect
  App Store submissions.
- What documentation or ERN (Encryption Registration Number) is required if encryption is used.

### 1.5 App Store Connect API State

```
WebSearch: "App Store Connect API current version <YYYY> changes deprecations"
WebSearch: "Transporter altool notarytool App Store Connect status <YYYY>"
```

Establish:
- Current stable version of the App Store Connect REST API.
- Any endpoint or resource deprecations relevant to app submission, metadata upload, or build
  management that affect the guided release loop in Phase 3.
- Status of upload tools: whether `altool` is deprecated in favor of `notarytool` or
  Transporter, and what the current recommended binary-upload path is.
- Any mandatory API authentication changes (e.g., API key requirements, JWT scopes).

### 1.6 In-App Purchase / Submission Requirements

> **Skip this domain only if Phase 0 reported `in_app_purchases.likely_present: false`.**
> Otherwise it is mandatory — the 2.1(b) App-Completeness reject is one of the most
> common IAP-related rejections and is entirely a metadata/submission-state failure,
> not a code bug.

```
WebSearch: "App Store In-App Purchase submission requirements <YYYY>"
WebSearch: "auto-renewable subscription App Review screenshot requirement App Store <YYYY>"
WebSearch: "Guideline 2.1b App Completeness In-App Purchase not submitted <YYYY>"
```

Establish:
- The full per-IAP metadata checklist required before a product can flip to
  `READY_TO_SUBMIT` — in particular the **App Review screenshot** per IAP and
  (for subscriptions) the **subscription group** + reference name + description
  + price tier. Without these the IAP cannot be submitted alongside the build,
  which is exactly the 2.1(b) reject trigger.
- Whether the IAPs must be **attached to the version** before `Submit for Review`
  (yes — and attached IAPs are submitted *together* with the build only when each
  is `READY_TO_SUBMIT`).
- The current success signal: IAPs flip `READY_TO_SUBMIT → WAITING_FOR_REVIEW`
  when the version is submitted. If they stay on `READY_TO_SUBMIT`, they were
  not submitted (almost always missing metadata or not attached).
- Whether Apple added any new IAP metadata field, localisation requirement, or
  subscription-pricing change for the current year.

Canonical sources if needed:

```
WebFetch: https://developer.apple.com/app-store/in-app-purchase/
WebFetch: https://developer.apple.com/help/app-store-connect/manage-in-app-purchases
```

---

## 2. Consolidate into a Freshness Report

After all five searches complete, produce a **Freshness Report** for the user before proceeding.

Format it as a compact table:

```
## Current Apple Requirements (researched <YYYY-MM-DD>)

| Domain                  | Finding                          | Source URL |
|-------------------------|----------------------------------|------------|
| Xcode min version       | …                                | …          |
| iOS deployment target   | …                                | …          |
| Required screenshots    | …                                | …          |
| Privacy nutrition label | …                                | …          |
| Account deletion        | …                                | …          |
| ATT / tracking          | …                                | …          |
| Export compliance       | …                                | …          |
| ASC API / upload tool   | …                                | …          |
| IAP submission rules    | … (skip row if no IAPs detected) | …          |
```

For any domain where searches returned ambiguous or conflicting results, add a note in the
Finding column: *"conflicting results — manual verification recommended before submission."*

For any domain that could not be resolved by search, flag it explicitly rather than falling
back to training memory: *"search inconclusive — may be outdated, verify on
developer.apple.com."*

---

## 3. Cross-Reference Against Phase 0 Findings

Before handing off to Phase 2, compare the Freshness Report against the Phase 0 situation
report (already presented to the user). Flag mismatches as blockers or warnings:

| Check | Blocker if… |
|---|---|
| iOS deployment target | Repo target < current App Store minimum |
| Xcode version | Installed Xcode < current accepted minimum |
| Screenshot coverage | Required device sizes missing from the asset catalog |
| Privacy manifest | `NSPrivacyAccessedAPITypes` absent but Phase 0 detected APIs that need it |
| ATT | `NSUserTrackingUsageDescription` absent but Phase 0 suggests tracking-adjacent SDKs |
| Account deletion | No in-app delete flow detected and mandate is active |
| In-App Purchases | Phase 0 `in_app_purchases.likely_present: true` but no IAP/submission research row (the 2.1(b) gate will be un-checked) |

Present blockers in a numbered list before optional items. A blocker means: "submission will
be rejected unless this is fixed." A warning means: "may cause issues — confirm before
submitting."

---

## 4. Proceed to Phase 2

When the Freshness Report is presented and blockers/warnings have been communicated, tell the
user:

> "Freshness research done. I've listed what's current and what your project may need to
> address. When you're ready to check your App Store Connect status and credentials, say 'next'."

Then read [phase2-asc-status.md](phase2-asc-status.md).
