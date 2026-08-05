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

## Stage the shot: no clutter, no Dock, no menu bar

Do this every take, right before starting the recorder — not just the first. What "staged" means depends on whether the shot is one window or several composed together:

**Single window (the default case).** Hide everything else, then capture only that window — this removes the Dock and menu bar structurally rather than by hiding them:

- **Hide every other app.** `osascript -e 'tell application "System Events" to keystroke "h" using {command down, option down}'` — the ⌥⌘H "Hide Others" shortcut — after bringing the target app to the front.
- **Fix the window's size and position**, not just its size: `osascript -e 'tell application "My App" to set bounds of window 1 to {x0, y0, x1, y1}'`. Pick bounds matching the deliverable's target aspect ratio, clear of the screen edges.
- **Capture the window, not the display:**
  - `screencapture`: resolve a window ID with [`GetWindowID`](https://github.com/smokris/GetWindowID) (`brew install smokris/getwindowid/getwindowid`), then `screencapture -l$(GetWindowID "My App") -V20 out.mov`.
  - OBS: a **Window Capture** source (or the newer **macOS Screen Capture** source set to Window/Application, not Display) scoped to the target app.
  - `sck-record` can't do this — its own docs list "main display only, no window or region selection" as a limitation; only reach for it here if system audio matters more than a clean frame.

**A composed scene — several windows/apps choreographed together in one shot** (a desktop app next to a simulator, drag-and-drop between two windows, a multi-app flow). Window-scoped capture is the wrong tool here, since it would cut out the other windows the shot actually needs. Two ways to get it right:

- **Preferred: OBS with one Window Capture source per window**, positioned on the scene canvas wherever the composition calls for — side by side, overlapping, whatever the storyboard needs. Each source is still individually window-scoped, so the Dock and menu bar stay excluded even though multiple windows are in frame. Fix every window's size/position first (same AppleScript pattern as above, once per window), since the scene layout is only reproducible if the windows underneath it are.
- **Fallback: a full-display capture**, when OBS scene composition isn't available. Auto-hide the Dock for the take (`defaults write com.apple.dock autohide -bool true && killall Dock`; restore after with `-bool false`), and either accept the menu bar in frame if the deliverable is fine with a "desktop workspace" look, or crop it out afterward in post — `ffmpeg -i raw.mov -vf "crop=iw:ih-<menubar_height>:0:<menubar_height>" cropped.mov` — rather than relying on an unverified region flag at capture time.

Either way, confirm the first captured frame actually matches what was staged before treating the take as good — a staging step that silently didn't take effect (Hide Others denied by a permissions dialog, window bounds not applied before the app finished launching) is easy to miss until playback.

## Capture: pick the lightest tool that covers the shot

1. **`screencapture` (built in, no install)** — fine default for a quiet, no-audio product demo; prefer the window-scoped `-l<windowid>` form from the staging step above over a bare `-V<seconds>` full-display capture, which pulls in the Dock and menu bar:
   ```bash
   screencapture -l$(GetWindowID "My App") -V 20 demo.mov
   ```
   Apple's own man page calls this utility "not very well documented" — confirm once on the target machine that this really starts headless before relying on it in an unattended script. `-g`/`-G<id>` only add microphone/named input, not system/app audio; use `-k` to burn in click indicators if that's part of the shot.
2. **[`sck-record`](https://github.com/connerkward/macos-screen-recorder-system-audio)** — a ScreenCaptureKit-based CLI recorder when the video needs the app's own sound; headless, no virtual-audio-device setup required. See the staging step above for its Dock/menu-bar caveat.
3. **OBS Studio + `obs-cmd`/`obs-cli`** — reach for this when the shot needs scene composition: several windows arranged together (see "A composed scene" above), a blurred backdrop, or a device bezel baked in at capture time rather than in post. OBS's WebSocket control has shipped in the app since v28:
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
