# Web and Electron branch: Playwright

## Web apps

Playwright's CLI is the token-light way to drive a browser from an agent — Playwright itself now recommends CLI + skill over MCP for this precisely because it loads far less tool schema and DOM tree into context; MCP stays worth it for exploratory, stateful sessions (e.g. the initial storyboard-authoring pass).

```bash
npm install -g @playwright/cli@latest
playwright-cli install --skills
```

Author the storyboard by exploring interactively (MCP is fine here), then freeze it as a deterministic CLI script:

```bash
playwright-cli goto http://localhost:3000
playwright-cli click e5
playwright-cli fill e8 "Marketing Demo"
playwright-cli click e12
```

Dry-run that sequence — same completion bar as every branch: twice clean, no manual fixes on the second pass.

## Capture the take

```bash
playwright-cli video-start demo.webm
# ...replay the frozen storyboard commands...
playwright-cli video-chapter "Result screen"
playwright-cli video-stop
```

Chapters, resolution, and action-overlay options are documented by `playwright-cli video --help`. The Playwright MCP server (`npx @playwright/mcp@latest --caps=devtools`) exposes the same start/chapter/stop controls if the whole run — not just authoring — is happening through MCP.

## Electron apps

Playwright's Electron support (`_electron` module) is still marked experimental, but is materially more stable than coordinate clicks or screenshot-guessing: it launches the Electron process and drives its windows like browser pages, including `page.video()` recording. Treat it as this same branch — write the storyboard against Playwright's Electron API, dry-run, then capture.

## Not for Tauri

A Tauri app's WKWebView on macOS is not something Playwright/browser tooling can attach to the way it renders live for the user. Use the desktop branch ([`desktop-macos.md`](desktop-macos.md)) for Tauri even though its UI is web tech.
