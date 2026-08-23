---
name: fetch-open-chat-tab
description: Extract the full conversation from a ChatGPT/Claude.ai/Gemini chat open in Safari's frontmost tab when no share link exists. Use when the user wants to read/summarize/save a Safari chat tab, "diesen Chat aus Safari holen", or sharing is unavailable.
---

# Fetch Open Chat Tab

Extract the complete conversation text from a ChatGPT, Claude.ai, or Gemini chat that is open right now in Safari's frontmost tab — for sessions that cannot be turned into a `fetch-shared-chat` share link (sharing disabled for that conversation, or not supported at all).

## Why not `fetch-shared-chat`

That skill needs a public share URL. Many conversations never get one. This skill instead drives the user's own, already-authenticated Safari tab directly: it reads the live, JavaScript-rendered DOM through `do JavaScript` (via a small JXA driver) — no headless browser, no login, and critically **no screenshot/OCR** — real text extracted straight from the DOM.

## Step 0: One-time Safari setting (tell the user if extraction fails with this reason)

Safari blocks script automation by default. The user must enable it once: **Safari menu bar → Develop → "Allow JavaScript from Apple Events"** (if the Develop menu isn't visible: Safari → Settings → Advanced → "Show features for web developers" first). The driver detects this exact failure and returns it as `reason` — relay it verbatim, don't guess at a workaround.

## Step 1: Make sure the target chat is the frontmost Safari tab

This skill always reads Safari's **current tab of the frontmost window** — there is no URL parameter. If the user means a different tab than whatever is currently active, ask them to switch to it first.

## Step 2: Run the script

```bash
S=~/.agents/skills/fetch-open-chat-tab/scripts/fetch_open_chat_tab.py
"$S" --output "<scratch-path>/conversation.md"
```

The script shells out to `osascript -l JavaScript` (`scripts/safari_driver.js`), which injects `scripts/extract_dom.js` into the tab and polls for its result — `do JavaScript` does not await promises, so the in-page script runs as a fire-and-forget async IIFE writing to a polled variable, not a blocking call.

Site detection is by hostname (`chatgpt.com`/`chat.openai.com`, `claude.ai`, `gemini.google.com`), each with its own verified-live DOM selectors:

- **ChatGPT** — `[data-message-author-role]`, keyed by ChatGPT's own stable `data-message-id` (a UUID) for dedup.
- **Claude.ai** — `[role="article"][aria-posinset]` (one per turn, both roles). `[data-test-render-count]` looked assistant-specific at first but is **not** — Claude runs every turn's content through the same markdown renderer, so an earlier version of this skill double-counted every user turn as a duplicate "assistant" entry. `aria-posinset` is the fix: a stable, purely-numeric, globally-unique turn position that survives virtualization remounts and is used both to dedup and (since collection order during a virtualized scroll sweep is not reading order) to sort the final transcript.
- **Gemini** — the `<user-query>`/`<model-response>` custom elements. Text is read from a cleaned clone with `.cdk-visually-hidden` elements stripped first — Gemini's DOM includes screen-reader-only labels (e.g. "Du hast gesagt") directly in `innerText` otherwise.

**Long conversations are DOM-virtualized** on claude.ai and (same Angular `infinite-scroller` component family) very likely gemini.google.com: scrolling away un-mounts earlier messages, so a single DOM snapshot silently misses most of a long chat. The script scrolls to the top repeatedly until the history stops growing, then sweeps top→bottom in overlapping steps, accumulating whatever is mounted at each step into a deduplicated list. This is why extraction on a long conversation can take up to ~30–90s — that is expected, not a hang.

**Completion criteria and exit codes:**

- `0` — structured extraction succeeded.
- `3` — the page's host/structure wasn't recognized, but a generic unstructured text fallback (cleaned `body.innerText`) was captured and saved instead. **Relay to the user that this is unstructured** (the saved file also carries a banner saying so) — treat it as raw material, not a clean transcript. Pass `--no-fallback` to disable this and get a hard `2` failure instead.
- `2` — hard failure, nothing usable extracted. The `reason` on stderr is concrete (e.g. the Apple-Events permission, Safari not running, no messages found) — relay it verbatim, same "never fabricate a summary of content that could not be retrieved" discipline as `fetch-shared-chat`.

## Step 3: Read and synthesize

On success (exit `0` or `3`), read the saved file and give the user what they asked for. On `3`, say plainly that the structure wasn't recognized and this is a raw page-text dump. On `2`, relay the failure reason and stop — do not guess at what the conversation might have contained.

## Distilling into a knowledge base

If the user wants this preserved as a structured, reusable knowledge base rather than a quick answer — same triggers as `fetch-shared-chat`: "Wissensbasis erstellen", "diesen Chat aufbereiten", wanting to continue the work later without re-reading the chat — follow `fetch-shared-chat`'s **Knowledge-base mode** section (what to capture, ground rules, output structure, and where to save the result) against the transcript you just saved here. The distillation method is independent of how the text was fetched.

## Known limitation

Two genuinely identical consecutive messages with no distinguishing id (Claude.ai's `aria-posinset` and ChatGPT's `data-message-id` both make this a non-issue on those two sites; only a scenario with neither would hit it) can collapse into a single entry during dedup. Rare in practice, disclosed rather than silently wrong.

## Dependencies

None beyond macOS + Safari + Python 3 (stdlib only). No Playwright, no network access, no login step — the whole point is using the session that is already open.
