---
name: lan-computer-use
description: "Fast GUI control of this Mac or LAN Macs and Windows PCs over SSH via accessibility trees with element refs, clicks, typing and screenshots. Use for 'Rechner steuern', 'Computer Use', 'klick in der App', 'Windows-PC bedienen'."
---

# LAN Computer Use

Drive desktop apps on this Mac (`local`) or on Macs and Windows PCs in the LAN. One CLI talks to a small agent that runs in the target's logged-on desktop session. The agent is compiled on first use and reached over an SSH tunnel; a local agent needs no SSH. It reads the accessibility tree (UI Automation / AX) and acts on elements by ref, which is faster and more reliable than working from pixels.

```sh
"${CLAUDE_SKILL_DIR}/scripts/cu" snapshot -i          # this Mac
"${CLAUDE_SKILL_DIR}/scripts/cu" -t win snapshot -i   # a LAN machine (targets.json entry or SSH host alias)
```

Call `scripts/cu` with its full path in every command. Don't put the command in a shell variable (zsh does not split words, so `$CU snapshot` fails), and don't copy the script elsewhere: the path stays valid across updates. Below, `cu` stands for that full path.

## Workflow

1. **Announce.** Before the first input on a machine, tell the user in text which machine you will control and why. On their own Mac, also say it aloud (`say "…"`); `cu` does this once per session for targets with `"announce": true`. Then start the overlay. It shows the task, the current action and a countdown on the target:
   `cu task "Export im Dialog prüfen" --eta 3m`
2. **Look.** `cu snapshot -i` prints a flat list of clickable or editable elements of the foreground window, each with a ref:
   `[e7] button "Speichern"`. Pick a window with `-w <title>` or `-a <app>`. Add `--rects` only when you need positions.
3. **Act by ref.** Use `click e7`, `type "text" --ref e3`, `set-value e3 "text"`, `press e7`, `key cmd+s`. Every input command answers with the state after the action, i.e. the foreground window and the focused element. Read that line instead of taking a new snapshot.
4. **Verify cheaply.** Use `find "Gespeichert"` or `wait "Fertig" --timeout 20`, then `snapshot -i` again. Take `shot` only when the meaning is visual: layout, images, canvas, or a dialog without an accessibility tree. Read the PNG path it prints.
5. **Finish.** Run `cu task --done` to hide the overlay, then `cu down`. `down` stops the agent and removes it from the target.

Refs (`eN`) are valid until the next `snapshot`/`find` on that machine. A stale ref gives a clear error; then take a new snapshot. No ref for the target? Use `click --text "Label"` (on macOS it falls back to OCR), then `shot` + `click --img X Y` with pixel coordinates from that shot.

## Rules

- Never type secrets. `type`/`set-value` refuse password fields; `--password-ok` is only for the user's explicit consent in this conversation.
- Prefer `press`/`set-value` (no mouse, works in the background) over coordinate clicks; prefer `snapshot -i` over `shot`.
- Chain many steps without a reconnect: `batch` reads JSON lines (`{"cmd":"click","ref":"e3"}`) from stdin.
- `hello` shows the OS, the user, whether the desktop is locked or on a secure desktop (UAC), the screen and missing permissions. Run it first when anything fails.
- Websites: use a browser automation tool, not this skill. This skill is for native apps and OS dialogs.

Read `${CLAUDE_SKILL_DIR}/REFERENCE.md` for target setup (`targets.json`, SSH, permissions), every command and flag, the snapshot format and platform quirks.
