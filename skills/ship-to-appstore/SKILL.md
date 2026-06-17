---
name: ship-to-appstore
description: "Guides a Flutter solo-dev through publishing to the Apple App Store step-by-step. Use to release, submit, or publish a Flutter app: App Store Release, im App Store veröffentlichen, App einreichen."
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
| Phase 0 introspection script | [scripts/phase0-introspect](scripts/phase0-introspect) |

Read the phase file you need when you need it. This SKILL.md is the always-on layer — keep it minimal.

## Core principles

- **One step at a time, feedback loop.** Present one release step, explain it, wait for the user's response before moving on.
- **Freshness first.** Never recite Apple requirements from training memory — always web-search for current-year guidance before providing step instructions (Phase 1).
- **Abort cleanly on non-Flutter repos.** Phase 0 detects the project type; if not Flutter/iOS, explain clearly and stop.
- **Never submit autonomously.** Submission to App Store Connect is a human action — the skill guides but does not execute it.
- **No credentials emitted.** The situation report includes identifiers (bundle ID, team ID) but never secrets.

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
