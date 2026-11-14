---
name: lan-computer-use
description: "Control native apps on this Mac or LAN Macs/Windows PCs via local accessibility APIs and SSH, using compact refs. Supports Codex and Claude Code. Use for 'Rechner steuern', 'Computer Use', 'klick in der App', 'Windows-PC bedienen'."
---

# LAN Computer Use

Use the bundled `scripts/cu` with Codex or Claude Code. Resolve its absolute path from this `SKILL.md` location; no agent-specific path variable is required. Below, `cu` means that quoted absolute path. The controller requires Python 3.8+ on macOS/POSIX; targets are macOS and Windows. Control uses local AX/UIA APIs and SSH without a cloud computer-use service; the calling model may still be cloud-hosted.

## Control loop

1. **Plan, then announce.** Tell the user which machine you will control and why before automation. Name yourself accurately: set `LCU_AGENT=Codex` or `LCU_AGENT='Claude Code'` on calls if session detection is unavailable. `cu` speaks before input for targets with `announce: true` (default: `local`); otherwise announce aloud with `say` on the controlling Mac.
2. **Lease.** `cu task "Check export dialog" --eta 2m` shows the operator, session, action and countdown. Estimate realistically; maximum `5m`. Renew with `task --eta` only while work remains. Input requires a lease; the agent exits 60 s after expiry.
3. **Read narrowly.** `cu snapshot -i` gives actionable refs, e.g. `[e7] button "Save"`. Use `-a APP` or `-w TITLE` and a small `--max` for large windows. Prefer `find --id ID` for known testIDs or `find "Label"`. Refs last until the next `snapshot`/`find` on that target; reacquire after UI transitions or stale-ref errors.
4. **Act and check the reply.** Prefer `press e7` and `set-value e3 "text"`, then `click e7`, `type "text" --ref e3`, or `key cmd+s`. Replies include the resulting window and focus. Snapshot again only when needed to choose the next action. Verify completion with targeted `find` or `wait "Done" --timeout 20`; no unconditional follow-up snapshot.
5. **Release immediately.** Run `cu task --done`, then `cu down`, including after errors. Do this before analysis, reporting or questions. Later work starts a new lease.

## Keep calls and context small

- Default target: `local`; `-t NAME` selects a LAN target or SSH alias. `hello` diagnoses permissions, locked desktops and UAC. Read [REFERENCE.md](REFERENCE.md) only for setup, options or troubleshooting.
- Batch known steps via JSON lines on stdin (`{"cmd":"press","ref":"e7"}`) to `cu batch`: one connection, stops on error. Stop at transitions requiring observation; do not guess subsequent refs. Manage leases with `task` outside batches.
- Prefer compact text; use `--json` for machine processing only. Narrow queries before raising limits. Avoid `--rects` unless positions matter. Use `wait` instead of sleeps.
- Use `shot` only for visual evidence or inaccessible UI; crop with `--ref`/`--region` or select a window. Open its PNG path with the caller's image tool. `click --img X Y` maps pixels of that last shot. macOS also offers `click --text "Label"` with OCR fallback.
- The overlay moves away from mouse targets. If it obscures inspection, announce `cu hide 20s` in chat first (maximum `60s`, unavailable during the first 5s); `hide 0` restores it.
- Never type secrets without explicit consent: `--password-ok` bypasses password protection only with authorization in this conversation.
- Use `chrome-playwright`/`pwc` for websites; this skill handles native apps and OS dialogs. Do not send parallel input to a shared desktop.
