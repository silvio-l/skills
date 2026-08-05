# Mobile branch: Maestro

[Maestro](https://maestro.dev/) drives iOS/Android simulators, emulators, and real devices from readable YAML flows. It runs Flutter, React Native, native (SwiftUI/UIKit, Compose), .NET MAUI, and mobile-web apps, and can record a flow as it runs — no separate screen recorder needed for this branch.

## Install

```bash
curl -Ls "https://get.maestro.mobile.dev" | bash
```

## Explore and author the storyboard

Maestro ships an MCP server in the CLI (the older standalone `maestro-mcp` package is discontinued):

```bash
maestro mcp
```

```json
{
  "mcpServers": {
    "maestro": { "command": "maestro", "args": ["mcp"] }
  }
}
```

Through it, or through `maestro studio`, inspect the running simulator's view hierarchy and pick elements by their accessible text/id — not by tap coordinates. Write the flow as YAML:

```yaml
appId: com.example.myapp
---
- launchApp:
    clearState: true
- tapOn: "Get Started"
- waitForAnimationToEnd
- tapOn: "New Plan"
- tapOn: "Title"
- inputText: "Marketing Demo"
- tapOn: "Save"
- assertVisible: "Saved successfully"
```

## Dry-run (step 2's completion criterion)

```bash
maestro test storyboard.yaml
```

Run it twice; any selector that occasionally fails to resolve or any step that races the previous screen's animation needs a `waitForAnimationToEnd` or a sharper selector before moving on.

## Capture the take (step 3)

```bash
maestro record --local storyboard.yaml
```

**Always pass `--local`.** Without it, `maestro record` uploads the raw screen capture to mobile.dev's servers and renders it there, handing back a signed download URL — the app's unreleased UI leaves the machine, and rendering may be gated by account/plan limits. `--local` renders on-device with the bundled Skiko library instead: fully offline, no upload, no account needed.

`--local` produces an MP4 of the exact run. Because Maestro drove the app, the recording is the storyboard verbatim — there's nothing to re-time in post beyond the polish pass in [`post-production.md`](post-production.md).
