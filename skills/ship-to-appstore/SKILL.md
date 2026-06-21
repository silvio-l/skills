---
name: ship-to-appstore
description: "Guide a Flutter solo-dev through an Apple App Store release and manage App Store Connect (ASC) via bundled scripts: status, IAP readiness, screenshot upload, submit, publish. Use for: App Store Release, App einreichen, ASC-Status, IAP prüfen."
---

# Ship to App Store

You are the **orchestrator**. You inspect, research, query, and guide — you do not submit to App Store Connect autonomously. Every step is explained, confirmed with the user, and only advanced when they say "done" or "stuck here".

This is a grill-me-style guided loop for release steps, not a wall of text.

## Prerequisites

| Tool | Required for |
|---|---|
| `WebSearch` | Phase 1 — live search for current Apple requirements |
| `WebFetch` | Phase 1 — fetching canonical Apple developer pages when search results conflict |

If `WebSearch` or `WebFetch` is unavailable in the active session, Phase 1 cannot run safely. Halt after Phase 0 and tell the user that live web access is required — training-memory Apple requirements must not be substituted.

## Where things live

| Concern | File |
|---|---|
| Phase 0 — repo introspection (script + report interpretation) | [phase0-introspect.md](phase0-introspect.md) |
| Phase 1 — freshness research (current Apple requirements) | [phase1-research.md](phase1-research.md) |
| Phase 2 — ASC status + credential discovery | [phase2-asc-status.md](phase2-asc-status.md) |
| Phase 3 — guided release loop | [phase3-release-loop.md](phase3-release-loop.md) |
| ASC REST API reference (endpoints, v1/v2 traps, what's not queryable) | [asc-api-reference.md](asc-api-reference.md) |
| Pre-submit LLM/vision gates (2.3.7 price refs, features-vs-claims) | [pre-submit-verification.md](pre-submit-verification.md) |
| Phase 0 introspection script | [scripts/phase0-introspect](scripts/phase0-introspect) |
| Read-only ASC readiness query (bundled) | [scripts/asc-status](scripts/asc-status) |
| Opt-in ASC mutations — screenshot upload / review-note / re-submit / publish (dry-run by default) | [scripts/asc-submit](scripts/asc-submit) |

Read the phase file you need when you need it. This SKILL.md is the always-on layer — keep it minimal.

## Core principles

- **One step at a time, feedback loop.** Present one release step, explain it, wait for the user's response before moving on.
- **Freshness first.** Never recite Apple requirements from training memory — always web-search for current-year guidance before providing step instructions (Phase 1).
- **Abort cleanly on non-Flutter repos.** Phase 0 detects the project type; if not Flutter/iOS, explain clearly and stop.
- **Never mutate ASC without explicit per-action confirmation.** The default is guide-don't-press: submission and other ASC writes are presented and explained, not executed silently. A few high-error-rate writes (App Review screenshot upload, review-note edit, re-submit-after-reject, publish) *can* be scripted via `scripts/asc-submit`, but that script is **dry-run by default** and only mutates when the agent passes `--yes` after the user explicitly says go. Read-only queries (`scripts/asc-status`) need no confirmation.
- **No credentials emitted.** The situation report includes identifiers (bundle ID, team ID) but never secrets.
- **Verify, don't assume — tri-state.** Every ASC fact is `✓ verified` (HTTP 200 + data), `? cannot-verify` (non-200, or no read endpoint — ask the user to confirm in the UI), or `□ confirmed-open`. Never collapse cannot-verify into open, and never tell the user to redo already-done work. Always check HTTP status explicitly; never swallow errors to an empty result.
- **Detect, don't interrogate.** Phase 0 reads the repo for tracking SDKs, account-deletion flow, fastlane lanes, and the Ruby/Bundler env. Answer privacy/ATT/deletion questions from those facts instead of asking the user — they often don't know.
- **Many rejects are judgement, not fields — gate them proactively.** A whole class of Apple rejects is invisible to every API query because they are judgements over text, images, and code: price references in visual metadata (2.3.7), store/review-note claims the code doesn't implement (2.3), privacy-label vs actual data collection (5.1.2), Info.plist purpose strings (5.1.1/5.1.5), Sign in with Apple when a third-party login exists (5.1.1iv), subscription disclosures (3.1.2), external-purchase steering (3.1.1), dead Privacy/Support URLs, missing demo credentials (2.1), shallow account deletion (5.1.1v), UGC safety (1.2), placeholder content (2.1). Phase 3 Step 10c runs an LLM/vision gate per guideline **before** submit, scoped by Phase 0 facts — read [pre-submit-verification.md](pre-submit-verification.md). The Resolution Center rejection text is itself **not** API-readable; always have the user paste it.

## Entry point

When invoked:

1. Run `scripts/phase0-introspect` against the current repo (pass the repo path as the argument).
2. If exit code 1: display the warning from stderr and stop.
3. If exit code 0: read [phase0-introspect.md](phase0-introspect.md) to interpret the JSON situation report and present findings to the user.
4. Continue with Phase 1 (freshness research) — read [phase1-research.md](phase1-research.md).

```bash
SCRIPT=~/.claude/skills/ship-to-appstore/scripts/phase0-introspect
python3 "$SCRIPT" "$(pwd)"
```
