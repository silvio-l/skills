---
name: agent-desktop
description: "Operate desktop apps on macOS, Windows and Linux with Vercel agent-desktop and native accessibility refs. Use for Computer Use, Rechner steuern, Desktop bedienen, App klicken, UI lesen, Screenshots or remote desktop tasks."
---

# Desktop control with agent-desktop

Use [Vercel agent-desktop](https://github.com/vercel-labs/agent-desktop) for native desktop interaction. The installed binary supplies version-matched instructions; load them before the first interaction:

```sh
agent-desktop status
agent-desktop skills get desktop
agent-desktop skills get platform
```

Read the `data.content` returned by both guide commands and follow it. Load command-specific help with `agent-desktop <command> --help` and extra guides with `agent-desktop skills get desktop <reference>` when needed.

## Installation

If the executable is missing, install the official package with `npm install -g agent-desktop`. Then check `status` and `permissions`. On macOS, `permissions --guide` explains any missing OS grant; never claim access until a real snapshot succeeds. Do not build or deploy a separate custom desktop daemon.

## Observe, act, verify

1. Identify the intended app and window. For a dense app, start with `snapshot --app "App" --skeleton -i --compact`, then drill one region with `snapshot --root @snapshot:eN`.
2. Use only qualified refs returned by that snapshot. Resolve multiple windows with `--window-id`. Do not reuse refs after the relevant UI changes.
3. Perform the authorized action and read the resulting state to verify its effect. Use `wait` for asynchronous transitions.
4. Inspect `ok`, `error.code`, and `disposition`. Retry or substitute an action only when `disposition.retry` is `safe`; otherwise observe first to avoid duplicate input.

Ref actions are headless by default. Physical input with `--headed` needs explicit authorization for that interaction. Never silently recover a semantic failure with coordinates or by taking focus. Keep private UI text, screenshots, clipboard contents and traces out of public logs. Pass secrets through supported `--stdin` arguments, not process arguments.

## Remote machines and isolated desktops

The executable controls the OS on which it runs. For an already authorized SSH target, run the matching platform binary there and read its platform guide and permission status on that host. Keep snapshot refs and session state on the same host. Preserve SSH host-key verification. A working SSH connection alone does not prove access to the logged-in desktop; verify a snapshot before proceeding.

If `~/.config/agent-desktop/targets.json` exists on the controlling machine, read it for private SSH aliases, executable paths and the verified invocation mode. This is local configuration, not part of the published skill. Recheck permissions each run; stored verification is historical evidence only.

On macOS over SSH, include the user's npm bin directory in PATH. Screen Recording belongs to the responsible launching process (often `sshd-keygen-wrapper`), not necessarily Terminal. Run `permissions --guide` on that host and have the user confirm the required grant with macOS authentication. Never edit the TCC database or disable OS protections. Validate accessibility with a snapshot and capture separately with `screenshot --screen 0 <private-path>`.

On Windows, SSH normally runs in Session 0 and cannot see the signed-in desktop. Use [the interactive launcher](scripts/invoke-interactive.ps1) on the Windows host. It runs one command as the same signed-in user using an `Interactive`, `Limited` scheduled task, then removes the task and temporary command files. It runs under `conhost.exe --headless`, so no console window appears over the app under test; Windows Terminal, the default terminal on Windows 11, ignores `-WindowStyle Hidden`. It neither stores a password nor installs a background daemon. The user must be signed in with an unlocked desktop; secure desktops and elevated apps remain outside this path. A timeout has unknown delivery: observe before retrying an action.

Pass a UTF-8 JSON array of CLI arguments encoded as base64 to `-ArgumentsBase64`. Base64 is transport encoding, not secrecy: never put credentials in these arguments. For example, generate the payload for a read-only check on the controlling host:

```python
import base64, json, subprocess
payload = base64.b64encode(json.dumps([
    "snapshot", "--surface", "taskbar", "--compact"
]).encode("utf-8")).decode("ascii")
subprocess.run(["ssh", "<configured-alias>",
    "powershell -NoProfile -File .agents/skills/agent-desktop/scripts/invoke-interactive.ps1 "
    "-ArgumentsBase64 " + payload], check=True)
```

Keep subsequent ref commands on the same invocation path and user account. Test screenshots and ref resolution across separate invocations before claiming the remote setup works. Local interactive Windows sessions can invoke `agent-desktop` directly.

For a managed macOS VM, consult the bundled sandbox guide and `agent-desktop sandbox --help`. Report provider and guest readiness accurately. Do not assume Linux or Windows has a bundled VM provider, or present untested remote interaction as verified.

For browser-only tasks, use the configured browser skill. For desktop UI audits, combine this runtime with `premium-desktop-pruefung`; keep its evidence and independent-review requirements.
