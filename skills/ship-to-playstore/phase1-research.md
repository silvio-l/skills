# Phase 1 — Freshness Research

> **Loaded on demand** by the orchestrator (SKILL.md Entry point, step 4).
>
> **Prerequisite tools:** `WebSearch` and `WebFetch` — both must be available in the active session.
> If either is unavailable, halt immediately and tell the user: "Live web access is required for
> freshness research. Training-memory Google Play requirements must not be substituted — please
> re-run this skill in a session with web search enabled."

---

## HARD RULE — No Training-Memory Requirements

**No concrete Google Play / Android requirement may be asserted from training memory.** This
covers SDK levels, pixel dimensions, date deadlines, AAB size thresholds, Play Billing Library
versions, policy clause identifiers, API endpoint paths, form field names, or any other specific
value that Google controls and may change between Android release cycles, Play Console updates, or
policy revisions.

Every hard requirement stated during this skill run must either:

1. Come from a live search or fetch performed **in this session**, or
2. Be explicitly flagged inline: *"may be outdated — verify on developer.android.com /
   play.google.com before acting."*

When Google terminology is unclear or a search result is ambiguous, **re-research live** rather
than infer from training. Play's `targetSdk` floor, the Play Billing Library version enforcement,
and the account/data-deletion mandate details all move on Google's schedule — a correct answer one
web-search away is never worth hallucinating.

This rule is in effect for all phases that follow — not just Phase 1. It applies to the freshness
report (§2), the Phase 0 cross-reference (§3), the Phase 2 situation overview, and every guided
release step in Phase 3.

> **This document deliberately states no concrete version, date, dimension, or policy number.**
> It is a research **protocol** that directs the runtime agent to fetch the current values live
> every invocation. Any concrete value written into this file would itself violate the HARD RULE.

---

## 1. Run the Nine Play Domain Searches

Perform all nine searches **before** giving the user any release-step instructions. Use the
current year (and month when useful) in each query to anchor freshness. The order does not
matter; all nine must complete before the Freshness Report in §2.

Each domain below names the **canonical source to consult** (the authoritative URL/path to fetch
or to cross-check a search hit against). Do not paraphrase a finding as authoritative unless you
have either fetched the canonical page in-session or cross-referenced a search hit against it and
flagged any divergence.

### 1.1 Target API level / minimum Android

```
WebSearch: "Google Play target API level requirement current minimum <YYYY>"
WebSearch: "Android targetSdkVersion Play Store deadline <YYYY>"
WebFetch: https://developer.android.com/distribute/best-practices/develop/target-sdk
```

Establish:
- The current `targetSdk` floor Play enforces for new apps **and** for updates to existing apps
  (these can differ; new apps are usually held to a higher floor).
- Whether an upcoming `targetSdk` deadline is announced (Google typically posts these in the
  Play Console and on developer.android.com with a compliance window).
- Implications for `minSdkVersion` (device coverage, Play's "minimum Android version" field) —
  informational, not a blocker on its own.

> Cross-reference target: Phase 0 `target_sdk_version` (§3, blocker row).

### 1.2 AAB rules

```
WebSearch: "Google Play Android App Bundle AAB required new apps <YYYY>"
WebSearch: "Play Store APK upload accepted track <YYYY>"
WebFetch: https://developer.android.com/guide/app-bundle
```

Establish:
- Whether APK is still accepted on any track for the app's situation (new app vs. existing app,
  and which track), or whether AAB is the only accepted format.
- Current AAB size thresholds and any Play Asset Delivery / Play Feature Delivery applicability.
- Any bundle-size warnings that affect listing or delivery (Play may serve APKs from the AAB).

### 1.3 Screenshot & listing specs

```
WebSearch: "Google Play Console screenshot requirements sizes <YYYY>"
WebSearch: "Play Store feature graphic dimensions icon specs <YYYY>"
WebFetch: https://support.google.com/googleplay/android-developer/answer/1078870
```

Establish:
- Which device/form-factor screenshot configurations are currently required (phone, tablet, TV,
  Foldable, Wear OS) and the exact pixel dimensions Play Console enforces for each.
- Feature graphic current dimensions and limits.
- App icon specs Play Console reads from the listing (distinct from the repo launcher icon
  densities surfaced by Phase 0 — listing icon lives in Play Console).
- Whether localizations share the same required assets or have separate requirements.

> Cross-reference target: Phase 0 `icon_set.missing_densities` (§3, warning row — repo densities,
> not the Play Console listing icon).

### 1.4 Data Safety

```
WebSearch: "Google Play Data safety form fields requirements <YYYY>"
WebSearch: "Play Store data deletion declaration Data safety <YYYY>"
WebFetch: https://support.google.com/googleplay/android-developer/answer/10787469
```

Establish:
- Current Data Safety form sections and data-type categories.
- The **"data deletion"** declaration field (whether data deletion is offered) and how it maps to
  the account/data-deletion mandate (§1.7).
- The encryption / security practices section and the US export-compliance answers (declared in
  Play Console, not a manifest key — the iOS `ITSAppUsesNonExemptEncryption` analogue is here).

> Cross-reference target: Phase 0 `data_safety_hints` (§3, drives the Data Safety rows).

### 1.5 Play Billing

```
WebSearch: "Google Play Billing Library version requirement current <YYYY>"
WebSearch: "Play Billing PBLT migration deadline <YYYY>"
WebFetch: https://developer.android.com/google/play/billing
```

Establish:
- The current Play Billing Library version Play enforces (apps must use a version at or above the
  enforced floor; older versions are rejected at submission).
- Any active PBLT (Play Billing Library) migration deadline and what happens to apps that miss it.
- Subscription base-plan / offer rules (a subscription needs a base plan; offers are optional).
- The two catalog namespaces: `inappproducts` (one-time) vs `monetization.subscriptions`.

> Cross-reference target: Phase 0 `play_billing.likely_present` + the version gate (§3).

### 1.6 Play Developer API state

```
WebSearch: "Google Play Developer API v3 current status <YYYY> deprecations"
WebSearch: "Play Developer API androidpublisher scope OAuth <YYYY>"
WebFetch: https://developers.google.com/android-publisher
```

Establish:
- Current stable version of the Play Developer API (the `androidpublisher` REST surface) and any
  endpoint deprecations relevant to the edits/tracks/bundles/inappproducts flow Phase 3 uses.
- Whether the OAuth scope (`androidpublisher`) is unchanged and how service-account JWT minting
  currently works.
- The current edits transaction surface (`edits.insert → mutations → edits.commit`) and whether
  any part has moved or gained a replacement.

### 1.7 Account-deletion mandate

```
WebSearch: "Google Play account deletion requirement in-app flow <YYYY>"
WebSearch: "Play Store data deletion webhook requirement <YYYY>"
WebFetch: https://support.google.com/googleplay/android-developer/answer/13327243
```

Establish:
- What Play's account-deletion mandate requires of an in-app flow (where the entry point must
  live, what it must do, how long deletion takes).
- Whether a **data-deletion webhook / URL** must be declared in Play Console for user data
  associated with an account, and the current shape of that requirement.
- Whether the mandate applies to this app at all (apps that do not create accounts are out of
  scope — but a Supabase-auth app almost always is in scope).

> Free-tier discipline (PRD §4.2): if a deletion endpoint is required, prefer a Supabase Postgres
> function over an Edge Function as the backend for the webhook. Do not assume a serverless worker
> is needed — the webhook can usually be served by the existing Supabase project.

> Cross-reference target: Phase 0 `data_safety_hints.account_deletion` (§3, drives mandate applicability).

### 1.8 Review / suspension model

```
WebSearch: "Google Play app review process what triggers human review <YYYY>"
WebSearch: "Play Store app suspension reinstatement <YYYY>"
WebFetch: https://support.google.com/googleplay/android-developer/answer/9907922
```

Establish:
- What currently triggers human review vs. immediate publish (new apps vs. updates; sensitive
  permissions vs. ordinary; the exact current trigger set is Phase-1 research, not training memory).
- Automated checks (pre-launch report, malware scan) and whether they block or are advisory.
- Post-hoc suspension mechanics: an update may ship immediately and be flagged later; reinstatement
  is a separate flow from a release reject.

> Stack fidelity: do not assume any Firebase-SDK-specific review behaviour. Play's automated
> checks scan the delivered APK from the AAB; flag only what the live source states.

### 1.9 (If IAP) Subscription / one-time product submission

> **Skip this domain only if Phase 0 reported `play_billing.likely_present: false`.**
> Otherwise it is mandatory — an unpublished product blocks the release commit (the Play-Billing
> analogue of the iOS 2.1(b) App-Completeness reject).

```
WebSearch: "Google Play in-app product submission required fields <YYYY>"
WebSearch: "Play Console subscription base plan offer publish requirements <YYYY>"
WebFetch: https://developer.android.com/google/play/billing/manage-products
```

Establish:
- The full per-product metadata checklist required before a one-time product can be published.
- For subscriptions: the base-plan requirement (+ optional offers), regional pricing, and what
  Play manages on tax/pricing automatically.
- The current success signal: a product must reach a publishable status before the release
  commits. Any product still draft → hard blocker before Step 11.

> Cross-reference target: Phase 0 `play_billing` (§3, the IAP gate).

---

## 2. Consolidate into a Freshness Report

After all nine searches complete (eight if §1.9 was skipped because Phase 0 reported no Play
Billing), produce a **Freshness Report** for the user before proceeding.

Format it as a compact table. Fill every `…` from a live in-session source; do not leave a cell
populated from training memory.

```
## Current Google Play Requirements (researched <YYYY-MM-DD>)

| Domain                                | Finding  | Source URL |
|---------------------------------------|----------|------------|
| Target API level / min Android        | …        | …          |
| AAB rules                             | …        | …          |
| Screenshot & listing specs            | …        | …          |
| Data Safety                           | …        | …          |
| Play Billing Library version          | …        | …          |
| Play Developer API state              | …        | …          |
| Account-deletion mandate              | …        | …          |
| Review / suspension model             | …        | …          |
| IAP submission rules                  | … (skip row if no Play Billing detected) | … |
```

For any domain where searches returned ambiguous or conflicting results, add a note in the
Finding column: *"conflicting results — manual verification recommended before submission."*

For any domain that could not be resolved by search, flag it explicitly rather than falling back
to training memory: *"search inconclusive — may be outdated, verify on developer.android.com /
play.google.com."*

---

## 3. Cross-Reference Against Phase 0 Findings

Before handing off to Phase 2, compare the Freshness Report against the Phase 0 situation report
(already presented to the user). Flag mismatches as blockers or warnings. Every check below maps
to a Phase 0 field — do not invent checks the situation report does not support.

| Check | Severity | Trigger (from Phase 0 + Freshness Report) |
|---|---|---|
| `target_sdk_version` vs. current floor | **Blocker** | Repo `target_sdk_version` < the live Play minimum researched in §1.1 |
| AAB acceptance vs. app situation | **Blocker** | App requires AAB but repo/track situation (from §1.2) cannot accept the produced artifact |
| Missing icon densities | **Warning** | `icon_set.missing_densities` non-empty (repo launcher icon gaps) |
| Declared-vs-expected permissions | **Warning** | `permissions.excessive` (declared, no plugin needs — ranking penalty / possible reject) or `permissions.missing` (plugin needs, not declared — runtime risk) |
| Play Billing Library version gate | **Blocker** | `play_billing.likely_present: true` but the repo's Billing integration is below the enforced version researched in §1.5 |
| Account-deletion mandate applicability | **Blocker** | `data_safety_hints.account_deletion.likely_present: true` and the mandate (§1.7) applies, but no in-app deletion flow is present |
| Data Safety "data deletion" field | **Warning** | Mandate applies but `account_deletion.likely_present: false` while the app otherwise creates accounts (contradiction to surface) |
| IAP catalog readiness | **Blocker** | `play_billing.likely_present: true` but §1.9 found products that cannot reach a publishable status |

Present blockers in a numbered list before warnings. A **blocker** means: "submission will be
rejected or the release commit cannot succeed unless this is fixed." A **warning** means: "may
cause issues — confirm before submitting."

For any check whose trigger depends on a value that could not be resolved live in §1.x, classify
the row as `? cannot-verify` and point the user at the canonical Play Console / developer page
rather than guessing. Never collapse cannot-verify into either blocker or warning.

---

## 4. Proceed to Phase 2

When the Freshness Report is presented and blockers/warnings have been communicated, tell the
user:

> "Freshness research done. I've listed what's current and what your project may need to address.
> When you're ready to check your Play Console status and credentials, say 'next'."

Then read [phase2-play-status.md](phase2-play-status.md).

> Phase 2 lands in a later slice. Until it ships, halt here after presenting the Freshness Report
> and the Phase 0 cross-reference — do not improvise Phase 2 behaviour from training memory.
