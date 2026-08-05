# Desktop branch: native macOS and Tauri apps

No single free tool both drives a native/Tauri macOS app and records it. The reliable combination is an accessibility-driven automation layer (storyboard authoring + replay) plus a separate screen recorder (raw capture), same two-step separation as every other branch.

## Automate: AppleScript/JXA via macos-automator-mcp

[`steipete/macos-automator-mcp`](https://github.com/steipete/macos-automator-mcp) runs AppleScript and JXA against a running app and ships a knowledge base of common macOS automation patterns.

```json
{
  "mcpServers": {
    "macos_automator": {
      "command": "npx",
      "args": ["-y", "--package", "@steipete/macos-automator-mcp", "macos-automator-mcp"]
    }
  }
}
```

Use it to explore the target app's UI element tree and menu structure, then freeze what works as a standalone `.applescript`/`.js` (JXA) file — that frozen file, not a live MCP session, is what gets replayed during the take. Prefer addressing UI elements (buttons, menu items, accessibility labels) over `click at {x, y}`: coordinates break the instant the window moves, resizes, or the system font scale changes.

For a Tauri app specifically: its window is a normal macOS window hosting a WKWebView, so AppleScript/JXA's window- and menu-level control works the same as on any native app. (A WebDriver bridge into the WebView itself — e.g. `tauri-webdriver-automation` or `@wdio/tauri-service` — exists for automated *testing*, but it drives the DOM, not the window the way it visually renders; it's the wrong tool here, where the point is to film the real live rendering.)

## Automate: Hammerspoon (alternative/complement)

[Hammerspoon](https://www.hammerspoon.org/) scripts macOS in Lua and reaches window management, app launching, and — via `hs.axuielement` — the same accessibility tree AppleScript sees, plus a CLI trigger (`hs.ipc`).

```bash
brew install --cask hammerspoon
```

```lua
-- ~/.hammerspoon/init.lua
require("hs.ipc")

function runStoryboard()
    hs.application.launchOrFocus("My App")
    hs.timer.usleep(1500000)
    local app = hs.application.frontmostApplication()
    -- prefer hs.axuielement lookups over hs.eventtap.leftClick(x, y)
end
```

```bash
hs -c "runStoryboard()"
```

## Fallback: no addressable accessibility elements

Some apps (custom-drawn canvases, games, some cross-platform toolkits) expose little or nothing to the accessibility tree, so `macos-automator-mcp`'s AppleScript/JXA and Hammerspoon's `hs.axuielement` have nothing to address. When that's genuinely the case — confirm it during exploration in step 2, don't assume it — fall back to `hs.eventtap.leftClick({x, y})`/keystrokes against fixed pixel coordinates, exactly as this file's other sections tell you to avoid. Two things make that fallback survivable rather than fragile: fix the window's size and screen position before recording every single time (`hs.window.focusedWindow():setFrame(...)`), since coordinates are only stable relative to a fixed window; and dry-run the storyboard more than the usual twice — coordinate clicks are far more sensitive to a slow-to-render frame landing a click one pixel off target.

## Permissions — review before running

Both routes need Accessibility and Automation permissions granted to whatever process hosts them (Terminal, the MCP server, Hammerspoon), and a script granted those permissions can control anything visible on the Mac, not just the target app. Read a generated script once before running it, the same way you'd read any code before executing it with elevated rights.

## Capture: pick the lightest tool that covers the shot

1. **`screencapture` (built in, no install)** — fine default for a quiet, no-audio product demo. Interactive selection is only turned on by `-i`; without it, `-V<seconds>` starts recording the main screen immediately for the given duration:
   ```bash
   screencapture -V 20 demo.mov
   ```
   Apple's own man page calls this utility "not very well documented" — confirm once on the target machine that this really starts headless before relying on it in an unattended script. `-g`/`-G<id>` only add microphone/named input, not system/app audio; use `-k` to burn in click indicators if that's part of the shot.
2. **[`sck-record`](https://github.com/connerkward/macos-screen-recorder-system-audio)** — a ScreenCaptureKit-based CLI recorder when the video needs the app's own sound; headless, no virtual-audio-device setup required.
3. **OBS Studio + `obs-cmd`/`obs-cli`** — reach for this only when the shot needs scene composition (blurred backdrop, device bezel baked in at capture time) that's easier live than in post. OBS's WebSocket control has shipped in the app since v28:
   ```bash
   obs-cmd recording start
   osascript ./storyboard.applescript
   obs-cmd recording stop
   ```
   Wrap it with a trap so a failed take still stops the recording:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   trap 'obs-cmd recording stop >/dev/null 2>&1 || true' EXIT
   open -a "My App"; sleep 2
   obs-cmd recording start; sleep 1
   osascript ./storyboard.applescript
   sleep 1; obs-cmd recording stop; trap - EXIT
   ```
   Password-protect the OBS WebSocket connection — it's an unauthenticated remote-control surface otherwise.

Whichever recorder is used, it starts, the frozen storyboard script runs unmodified, then it stops — per step 3 of `SKILL.md`.
