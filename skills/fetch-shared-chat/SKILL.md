---
name: fetch-shared-chat
description: Fetch and extract the full conversation text from a shared AI chat link (chatgpt.com/share, gemini.google.com/share, claude.ai/share) without a browser. Use when the user pastes such a link or asks to read/summarize a shared chat.
---

# Fetch Shared Chat

Extract the complete conversation text from a shared ChatGPT, Gemini, or Claude.ai chat link — no visible browser window, no browser extension, no login, no copy-paste from the user required.

## Why not just fetch the URL

These are all client-side-rendered SPAs: a plain `curl`/`WebFetch` of the share URL returns an empty app shell, not the conversation (the actual messages load via client-side JavaScript after the page mounts). Never try a plain fetch first and fall back later — go straight to the script below.

## Step 1: Run the script

```bash
S=~/.agents/skills/fetch-shared-chat/scripts/fetch_shared_chat.py
"$S" "<SHARE_URL>" --output "<scratch-path>/conversation.md"
```

The script dispatches on the URL host:

- **`chatgpt.com/share/<id>`** — fetches `<url>.data`, the React Router single-fetch data endpoint, with plain HTTP. No browser at all. This endpoint returns the conversation as a `turbo-stream`-encoded payload (decoded by the bundled `turbo_stream_decode.py`) and, critically, states plainly *why* a share failed when it does (e.g. deleted vs. access-denied) — the DOM-rendered page instead just silently client-side-redirects to the homepage, which looks identical for both cases and must not be used as the extraction method.
- **`gemini.google.com/share/<id>`** or **`share.gemini.google/<id>`** — no known server-side data endpoint; rendered with headless Chromium (Playwright) since the conversation only exists in the client-hydrated DOM.
- **`claude.ai/share/<id>`** — attempted the same way, but claude.ai currently serves automated requests a Cloudflare bot-verification challenge on this route. The script detects this and fails explicitly rather than returning the challenge page as if it were content.

**Completion criterion:** exit code `0` and a `Saved conversation text (N chars) to: <path>` line on stderr.

## Step 2: Handle failure honestly

Exit code `2` means the script reached the source and got a concrete, worded reason (printed as `FAILED: ...`) — e.g. "denied access", "scoped to a workspace", "Cloudflare bot-verification challenge", "looks like a login wall". **Relay that reason to the user verbatim and stop. Never synthesize or guess at a summary of content the script could not retrieve** — a plausible-sounding reconstruction of a chat you never actually read is worse than admitting the fetch failed. If the reason suggests a fix the user can make (e.g. ChatGPT's share-visibility setting), say so.

Exit code `1` means the URL's host wasn't recognized — check the URL against the three supported patterns above.

## Step 3: Read and synthesize

On success, read the saved file and give the user what they actually asked for — a summary, an answer extracted from the conversation, or the raw text if they want it verbatim. The script strips hidden system scaffolding messages already; what remains is the real back-and-forth.

## Dependencies

`turbo_stream_decode.py` (bundled, no install needed) handles the ChatGPT path. The Gemini and Claude.ai paths need Playwright's headless Chromium: `pip install playwright && playwright install chromium` if not already present.
