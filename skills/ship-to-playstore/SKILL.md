---
name: ship-to-playstore
description: "Guide a Flutter solo-dev through a Google Play Store release and manage Play Console via bundled scripts: status, IAP/billing readiness, upload, release-to-track, submit. Use for: Play Store Release, App einreichen, Play-Status, Play Billing prüfen."
disable-model-invocation: true
---

# Ship to Play Store

You are the **orchestrator** for a Google Play Store release. You inspect, research, query, and guide — you do not ship
to production autonomously. Every mutation (AAB upload, track release, staged rollout, production commit, IAP publish,
Data Safety publish) is a discrete opt-in checkpoint the user must explicitly approve. This is a guided, one-step-at-a-time loop.

## Prerequisites

| Tool | Required for |
|---|---|
| `WebSearch` | Phase 1 — live search for current Play requirements |
| `WebFetch` | Phase 1 — fetching canonical developer.android.com / play.google.com pages |
| Python 3 | Phase 0 — runs `scripts/phase0-introspect` (stdlib only) |
| `openssl` | Phase 2 — RS256-signs the OAuth2 JWT assertion for `scripts/play-status` |
| `flutter`, `java`, `gradle` | Phase 2 toolchain precheck; Phase 3+ build steps |

Phase 1 (freshness research) requires `WebSearch` and `WebFetch` — if either is unavailable in the session,
the skill halts after Phase 0 and tells the user live web access is required (training-memory Play requirements
must never be substituted).

The user invokes this skill with `/ship-to-playstore`, or it auto-invokes on German triggers like
*"Play Store Release"*, *"App einreichen"*, *"Play-Status"*, *"Play Billing prüfen"*.

## Where things live

| Concern | File | Status |
|---|---|---|
| Phase 0 — repo introspection (report interpretation) | [phase0-introspect.md](phase0-introspect.md) | ✅ this slice |
| Phase 0 introspection script | [scripts/phase0-introspect](scripts/phase0-introspect) | ✅ this slice |
| Phase 1 — freshness research (current Play requirements) | [phase1-research.md](phase1-research.md) | ✅ this slice |
| Phase 2 — Play Console status + credential discovery | [phase2-play-status.md](phase2-play-status.md) | ✅ this slice |
| Play Developer API reference | [play-api-reference.md](play-api-reference.md) | ✅ this slice |
| Read-only Play Console readiness query | [scripts/play-status](scripts/play-status) | ✅ this slice |
| Phase 3 — guided release loop (upload → track → commit) | [phase3-release-loop.md](phase3-release-loop.md) | ✅ this slice |
| Opt-in Play mutations (upload / release / commit) | [scripts/play-submit](scripts/play-submit) | ✅ this slice |
| Pre-submit Play Policy gates | [pre-submit-verification.md](pre-submit-verification.md) | ✅ done |
| Metadata: listing / Data Safety / rating / privacy / pricing (Steps 5–9) | [phase3-release-loop.md](phase3-release-loop.md) | ✅ done |
| IAP / Play Billing catalog readiness (Step 10b) | [phase3-release-loop.md](phase3-release-loop.md) + [scripts/play-submit](scripts/play-submit) | ✅ done |

Read the phase file you need when you need it. This SKILL.md is the always-on layer — keep it minimal.

## Core principles

Inherited from `ship-to-appstore`, with the Play deltas marked **(Play delta)**:

- **One step at a time, feedback loop.** Present one release step, explain it, wait for the user's response.
- **Freshness first.** Never recite Play/Google requirements from training memory — always research current guidance
  in-session (Phase 1).
- **Abort cleanly on non-Flutter/non-Android repos.** Phase 0 detects Flutter + Android; if either is absent, stop.
- **API power + opt-in gates (Play delta, PRD §4.1).** Play allows the entire release flow via the API (no
  Apple-style human submit gate). The skill exercises full API power, but every mutation is a discrete opt-in
  checkpoint. `scripts/play-status` is read-only (no confirmation); `scripts/play-submit` is **dry-run by default**
  and only mutates on explicit `--yes` after the user says go. `--track` and `--rollout` are explicit, required flags
  with no safe default — "oops I shipped to prod" must be structurally hard.
- **Stack fidelity (Play delta, PRD §4.2).** Supabase (not Firebase) for auth/DB/storage/realtime. FCM is acceptable
  as Android push transport only — no Firebase SDK for any other purpose. Free-tier discipline: all tools cited
  (`flutter`, `gradle`, `bundletool`, Play Console API) are free; no paid screenshot/CI/upload service as a default;
  no Edge Functions as a backend default.
- **No credentials emitted.** Phase 0 surfaces paths only — keystore passwords, service-account JSON contents, and
  OAuth tokens are never logged, printed, committed, or written to the status note. `signing` surfaces keystore
  **paths** only.
- **Verify, don't assume — tri-state.** Every Play fact is `✓ verified` / `? cannot-verify` / `□ confirmed-open`.
  Never collapse cannot-verify into open. Data Safety publish state, app-signing enrolment, and policy decision text
  are partially or not API-readable → `? cannot-verify`, never "not done".
- **Detect, don't interrogate.** Phase 0 reads the repo for permissions, Data-Safety-relevant SDKs,
  account-deletion flow, Play Billing, and the Gradle/Java toolchain. Answer Data-Safety / permissions / Play-Billing
  questions from those facts instead of asking the user — they often don't know.
- **Many rejects are judgement, not fields — gate them proactively.** A class of Play rejects is invisible to every
  API query because they are judgements over text, images, and code (Store Listing claims, Data Safety mismatches,
  permission discipline, subscription disclosures, UGC safety, minimum functionality). Phase 3 Step 10c runs a gate
  per Play policy before submit, scoped by Phase 0 facts. Policy decision text is not API-readable —
  always have the user paste it.

### Status note + security (Play delta, PRD §4.3)

- Default status note path: `.scratch/ship-to-playstore/status.md` — **append-only** and **gitignored**.
- Holds only step ids, version strings, track names, rollout fractions, timestamps — **never** keystore passwords,
  service-account JSON, or OAuth tokens.

## Entry point

When invoked:

1. Run `scripts/phase0-introspect` against the current repo (pass the repo path as the argument).
2. If exit code 1: display the warning from stderr and stop. The repo is iOS-only or not Flutter — point the user at
   `ship-to-appstore` for iOS.
3. If exit code 0: read [phase0-introspect.md](phase0-introspect.md) to interpret the JSON situation report and
   present findings to the user.
4. **Phase 1 freshness research.** Check that `WebSearch` **and** `WebFetch` are available in the active session.
   - If either is unavailable: **halt** and tell the user "Live web access is required for freshness research.
     Training-memory Google Play requirements must not be substituted — please re-run this skill in a session with
     web search enabled." Do not proceed, do not recite Play requirements from memory.
   - If both are available: read [phase1-research.md](phase1-research.md) and execute the nine-domain freshness
     research protocol. Present the Freshness Report and the Phase 0 cross-reference (blockers / warnings).
5. **Phase 2 — Play Console status.** Read [phase2-play-status.md](phase2-play-status.md). Run the toolchain
   precheck (§1), discover credentials (§2), select the strategy (§3), run `scripts/play-status`, and present
   the situation overview (§5) to the user.
6. **Phase 3 — Guided release loop.** Read [phase3-release-loop.md](phase3-release-loop.md). Build the ordered
   release checklist (§3.1), confirm with the user, then work through steps 0–4, 5–9 (listing / Data Safety /
   rating / privacy / pricing), 10a (track + rollout), 10b (IAP catalog gate — `scripts/play-submit --yes publish-iap`),
   10c (pre-submit gates from [pre-submit-verification.md](pre-submit-verification.md)), 11, 12 one at a time
   using the loop mechanic (§3.2) and `scripts/play-submit` for all mutations. After Phase 3 Step 12, **halt** —
   do not improvise any Phase 4+ steps from training memory.

```bash
SCRIPT=~/.claude/skills/ship-to-playstore/scripts/phase0-introspect
python3 "$SCRIPT" "$(pwd)"
```
