# lan-computer-use — Reference

`python3 scripts/cu.py [-t TARGET] [--json] <command> …`. It needs Python 3.8 or newer and the stdlib only. Exit codes: `0` ok, `1` the agent reported an error, `2` a usage, config or connection error.

## How it works

- **Agent.** A single source file per OS: `agent/macos/agent.swift` or `agent/windows/agent.cs`. It is compiled on the target on first use (`swiftc` / the .NET Framework `csc.exe`), and the binary name carries a hash of the source, so an edit triggers a rebuild automatically.
- **Session.** The agent runs in the user's interactive desktop session. On Windows a short-lived scheduled task starts it from the SSH session 0; on remote Macs `launchctl` starts it in the `gui/<uid>` domain.
- **Network.** The agent listens on `127.0.0.1` only and checks a 256-bit random token on every request. The client reaches it through an SSH port forward over a ControlMaster connection, so later calls cost only a local TCP round trip, typically 5–50 ms.
- **Idle stop.** The agent exits by itself after `idle_minutes` without requests (default 30). `down` stops it at once and deletes its directory on the target.
- **Client state.** Session state (port, token) lives in `~/.cache/lan-computer-use/` (mode 0700).

## Targets

The built-in target `local` is this Mac and needs no SSH. LAN targets live in `~/.config/lan-computer-use/targets.json`; override the path with `LCU_CONFIG`.

```json
{
  "default": "local",
  "targets": {
    "win": {"os": "windows", "host": "win.lan", "user": "tester", "identity": "~/.ssh/id_ed25519",
            "host_key": "ssh-ed25519 AAAA…", "idle_minutes": 30},
    "mini": {"os": "macos", "host": "mini.lan", "user": "me", "announce": true}
  }
}
```

| key | meaning |
|---|---|
| `os` | `windows` or `macos` (required) |
| `host`, `user`, `port`, `identity` | SSH destination; key auth only (`BatchMode=yes`) |
| `host_key` | optional pinned host key line (`type base64`). It is written to a private known_hosts file with strict checking |
| `ssh_options` | extra `-o` values, e.g. `["ProxyJump=bastion"]` |
| `idle_minutes` | agent auto-stop (default 30) |
| `announce` | print and `say` a notice on the controlling Mac before the first input of a session (default on for `local`) |

Select a target with `-t NAME`, `LCU_TARGET`, or the config `default`. `targets` lists them; `status` shows the client session without secrets. `LCU_TIMING=1` prints the round trip per command to stderr.

### Preparing a target

- **This Mac (`local`):** the terminal app that runs Claude Code needs *Accessibility* and *Screen Recording* (System Settings > Privacy & Security); the agent inherits them. It also needs Xcode Command Line Tools for `swiftc`.
- **Windows 10/11:** turn on the OpenSSH Server and put your public key into `authorized_keys`; for an admin user that is `C:\ProgramData\ssh\administrators_authorized_keys`. The SSH user must be logged on at the desktop. A locked screen is reported, and the agent cannot unlock it. The .NET Framework 4.x compiler that comes with Windows is enough.
- **Remote Mac (experimental):** enable Remote Login and install the Command Line Tools. Grant the agent binary under `~/Library/Caches/lan-computer-use/` *Accessibility* and *Screen Recording* once at that Mac's screen. Without these grants `hello` shows `permissions … NO`.

## Overlay (`task`)

`task "TEXT" [--eta 5m]` shows a compact warning panel in the top right corner of the target's screen. The panel has a yellow border and a yellow warning icon. It shows:

- the header ("Claude steuert diesen Rechner" or "Claude is controlling this computer");
- the task;
- the current action with its age, e.g. "klickt «Speichern» · vor 0:03";
- a countdown, or how far the run is over the ETA;
- when the agent auto-stops.

Typing shows only the number of characters, never the text. `task --done` hides the panel. Every input command updates the action line by itself; `task` again only changes the text or the ETA.

The panel is excluded from screen capture: `NSWindow.sharingType = .none` on macOS and `WDA_EXCLUDEFROMCAPTURE` on Windows. So it never shows up in `shot`, OCR or screen sharing, and it never covers the elements the agent works on, because it ignores the mouse. Its language follows the target's UI language (German or English).

## Reading the UI

| command | output |
|---|---|
| `hello` | OS, version, user, host, desktop state (macOS `normal`/`locked`; Windows the input desktop `Default`, `Winlogon` or `(secure desktop)` for UAC), screen size and units, missing permissions |
| `windows [--all]` | top-level windows: title, app, `[x,y,w,h]`, `handle=`, `foreground`/`minimized` |
| `snapshot [-i] [--rects] [-w T\|-a APP\|--handle H] [--max 250] [--depth N] [--all]` | accessibility tree of one window (default: foreground) |
| `find [TEXT] [--role R] [--id ID] [--exact] [--max 20]` | matching elements, flat, with rects |
| `wait [TEXT] [--role R] [--id ID] [--timeout 10] [--gone]` | polls until an element appears (or disappears) |
| `shot [-w T\|-a APP\|--ref eN\|--region x,y,w,h] [--max 1280] [-o FILE]` | PNG on the client; prints path, size, scale and origin |
| `ocr [TEXT] [--region …] [--fast]` | macOS only: recognized lines with rects and center points |

**Snapshot lines** look like `[e12] button "Speichern" #saveBtn focused @812,640,96,32`:

- the ref;
- the normalized role: `button`, `textfield`, `checkbox`, `link`, `menuitem`, `tab`, `row`, `cell`, `text`, …;
- the name;
- `=value` for fields;
- `#id`: automation id, DOM id or testID, shown only when it differs from the name;
- flags: `disabled`, `focused`, `password`, `checked`/`unchecked`/`mixed`, `expanded`/`collapsed`, `selected`, `readonly`, `offscreen`;
- with `--rects`, the rect in screen units.

`-i` keeps only actionable elements, flat and without rects. That is about a third of the tokens and usually all the agent needs. Text rows inside lists and tables are kept with their name. `… truncated` means the limit was reached: narrow the window or raise `--max`. `--all` also lists elements scrolled out of view.

**Units.** macOS uses points (Retina = 2 px per pt); Windows uses physical pixels (the agent is per-monitor DPI aware). `shot` prints `1 px = S units` and the origin. `click --img X Y` maps pixels of the *last* shot back, so you never convert by hand.

**First OCR** on a Mac takes about 1–2 s while Vision loads; later calls are fast. Windows has no OCR: use `shot` and read the image.

## Acting

| command | notes |
|---|---|
| `click X Y \| eN \| --ref eN \| --text T` | `--right`, `--button middle`, `--double`; coordinates are screen units, or with `-w/-a` relative to that window, or with `--img` pixels of the last shot |
| `move …` | same addressing as click (hover) |
| `drag X Y X2 Y2` | left button |
| `scroll [eN \| X Y] --dy N --dx N` | notches; positive = down / right |
| `press eN` | invoke an element via the accessibility API (no mouse, no focus change) |
| `focus eN` | keyboard focus |
| `set-value eN TEXT` | replace a field's value directly (fast; `-` reads stdin) |
| `type TEXT [--ref eN]` | real key events into the focused element (Unicode safe; `-` reads stdin) |
| `key COMBO… [--times N]` | e.g. `cmd+shift+t`, `ctrl+w`, `alt+f4`, `enter`, `cmd++`; aliases: `option`, `command`, `return`, `escape`, `pgdn`, … |
| `activate -w T \| -a APP \| --handle H` | bring to front, restore if minimized |
| `launch APP [--args …] [--wait TITLE] [--timeout 15]` | macOS: app name, bundle id or path; Windows: exe, path or AUMID |
| `batch` | JSON lines `{"cmd": …, args}` on stdin over one connection; `"out"` sets a shot file; stops at the first error |

`--settle MS` makes the agent wait after an input before it reads the post state. Every input reply looks like this:

`ok · fg "Unbenannt – Editor" (Notepad) · focus document "Text-Editor" · at 640,400 · via invoke`

- `fg` is the foreground window afterwards;
- `focus` is the focused element;
- `via` is the method used (`invoke`, `toggle`, `select`, `value pattern`, …).

A change of the input desktop (lock screen, UAC) is reported as `desktop …`.

`click --text` prefers exact names and actionable roles among the visible enabled matches, then the smallest one. On macOS it falls back to OCR and prints `matched via …`.

## Safety

- Password fields (`password` flag, or secure keyboard entry on macOS) are refused by `type` and `set-value`. Pass `--password-ok` only with the user's explicit consent.
- The agent accepts connections from `127.0.0.1` with the session token only. The token never leaves the client's private cache and the target's per-user directory.
- The overlay tells anyone at the machine that it is being controlled. `down` leaves nothing running and nothing on disk on the target.

## Platform notes

- **Windows:**
  - Some system dialogs expose no UIA children, for example Windows Update prompts and some UWP or WebView popups. Use `shot`, then `click --img X Y`.
  - Win32 Notepad's edit area has the role `document`, not `textfield`.
  - A UAC prompt runs on the secure desktop; `hello` reports `(secure desktop)` there, and the agent cannot act on it.
- **macOS:**
  - System Settings panes can be slow; use `wait`.
- **Both:**
  - Windows that are minimized or on other Spaces/desktops are not in `snapshot`; `activate` them first.
