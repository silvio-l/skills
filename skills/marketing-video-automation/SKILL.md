---
name: marketing-video-automation
description: "Automate marketing/demo videos for mobile, web, Electron, and macOS/Tauri apps: deterministic storyboard, screen capture, zoom/GIF/WebP polish. Use for 'marketing video', 'App-Demo aufnehmen', 'Screen Studio style', 'App Store preview video'."
---

# Marketing Video Automation

Produces a demo/marketing video by automating the app itself rather than free-hand clicking during the recording. A freely improvising agent driving the app live, on camera, is the unreliable path — jitter, mis-clicks, and dead air all end up baked into the footage with no way to cut them out. The reliable path is a **storyboard**: a script the agent writes and rehearses first, then replays verbatim while a separate recorder captures the screen.

## 1. Pick the platform branch

| App runs as | Automate with | Reference |
|---|---|---|
| iOS/Android app (simulator or device) | Maestro | [`mobile-maestro.md`](mobile-maestro.md) |
| Web app in a browser | Playwright CLI | [`web-playwright.md`](web-playwright.md) |
| Electron app | Playwright (experimental Electron support) | [`web-playwright.md`](web-playwright.md) |
| Native macOS app, or Tauri (WKWebView) desktop app | AppleScript/JXA or Hammerspoon + native screen capture | [`desktop-macos.md`](desktop-macos.md) |

A Tauri app is Rust with a WKWebView front end, not Chromium — Playwright/browser automation does not see the window as it actually renders. Treat it as a native macOS app: the desktop branch, not the web branch, even though the UI is built with web tech. Load the matched reference file before continuing; it carries the install commands, script templates, and capture commands for that branch.

**Done when:** the branch is picked and its reference file is loaded.

## 2. Design the story, then write the storyboard

**One clip, one benefit.** A clip that tours the whole app teaches nothing; a clip built as a three-beat story — starting problem/state, one legible action, a visibly better result — teaches one thing well. Prefer several short, single-benefit clips over one long walkthrough. The payoff has to land in the first few seconds: cut every intro, loading screen, and setup click that doesn't serve that one beat.

**Every motion points at the beat.** Cursor moves, zooms, and highlights exist only to direct attention to what matters right now — never decoration. Zoom only where a detail would otherwise be illegible, move one thing at a time, and let each state change visibly connect its before → action → after, so the sequence reads as cause and effect rather than a slideshow of screens.

Now write the exact, numbered sequence the video will show — every tap/click, every text entered, every wait, every expected resulting screen — as the script format native to the branch (Maestro YAML, a Playwright CLI script, an AppleScript/JXA file, or a Hammerspoon function). Use the branch's exploration tool (Maestro MCP, Playwright MCP, or `macos-automator-mcp`'s accessibility-tree inspection) to find stable selectors — accessibility labels, testIDs, menu items — never fixed screen coordinates, which break the moment a window resizes or a font scales.

The opening steps have to reach a clean demo state: realistic, readable placeholder data, a fixed window/simulator size and position, no notifications, no error states, nothing private — and, for a desktop capture, no other windows and no Dock/menu bar in frame (see the desktop branch reference for how to stage that). If the app already has a way to load that state directly — a debug/demo menu, a seed script, a launch flag, a `?demo=1` URL — use it instead of reconstructing the state by re-typing fixture data through the UI on every take; it's faster, and it can't itself glitch on camera. If the app has no such hook yet, that's worth adding as a small dev-only feature before doing repeat marketing-video work on it, rather than fighting the same manual setup every time.

Pace it like a demo, not a test: a brief settle beat before each key action, and enough hold time on the final screen for the result to actually register. A storyboard that fires every step back-to-back reads as an automated test, not something a person did. If the clip is meant to loop, make the first and last frame match so the loop doesn't visibly jump.

Dry-run the storyboard without recording. Fix every flaky selector and every race (a tap that lands before the previous screen's animation finished) until it is boring: the same outcome, unattended, every time.

**Done when:** the storyboard dry-runs to completion twice in a row with no manual intervention on the second run, its first frame is legible and its last frame reads as a clear result, and — for a looping deliverable — the first and last frames match.

## 3. Capture one raw take

Start the recorder, replay the storyboard **unmodified**, stop the recorder. Never improvise a click or adapt the flow mid-recording — the storyboard from step 2 is the single source of truth for what's on screen; recording is a mechanical replay of it, not a fresh performance. If the app misbehaves during the take, stop, fix the storyboard or the app state, and take again from the top — don't patch around a bad take in post.

**Done when:** one continuous raw video file exists spanning the full storyboard, and `ffprobe` confirms its duration is within a few seconds of the storyboard's expected run time.

## 4. Polish and export

Apply zoom/cursor-highlight polish if the deliverable calls for that look, then export the deliverable that fits where it's going: silent autoplaying `<video>` for a website, GIF/WebP only where the platform specifically needs a static-embeddable format, and a spec-compliant MP4 for an App Store/Play Store preview. Any on-screen text — burned-in captions, callouts, an animated headline — is opt-in: default to none, and add it only when the user actually asks for it; that's separate from the clip's benefit also needing to exist as real page text nearby, which stands regardless. See [`post-production.md`](post-production.md) for exact commands, delivery markup, and format specs.

**Done when:** every requested output file exists, and `ffprobe`/`gifsicle` confirm it opens cleanly at the target resolution — not just that the export command exited zero.
