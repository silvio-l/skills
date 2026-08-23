---
name: fetch-shared-chat
description: Fetch a shared AI chat link (chatgpt.com/share, gemini.google.com/share, claude.ai/share) without a browser and distill it into a structured knowledge base by default. Use for share links, 'Wissensbasis erstellen', 'Chat aufbereiten'.
---

# Fetch Shared Chat

Extract the complete conversation text from a shared ChatGPT, Gemini, or Claude.ai chat link — no visible browser window, no browser extension, no login, no copy-paste from the user required. Once fetched, either answer the user's question about it directly, or — when they want the work preserved and continuable — distill it into a structured, source-faithful knowledge base.

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

## Step 3: Pick the response mode

**Default to knowledge-base mode.** Someone reaching for this skill at all is almost always trying to preserve or continue work, not just satisfy a one-off curiosity — and a quick answer that turns out to be the wrong call is expensive: the user has to notice something's missing, re-ask, and wait for a second full read of the transcript. Go to **Knowledge-base mode** below unless one of these clearly applies:

- **Quick mode** — the user asked a narrow, specific question ("what did they conclude about X", "did they land on Y or Z") where a direct answer *is* the whole ask, not a partial one; or they explicitly want the raw text verbatim. Go to **Quick mode** below.
- The user explicitly asks for "just a summary" / "just give me the gist" with no indication they want to keep working from it.

If it's genuinely ambiguous, default to knowledge-base mode rather than asking — the cost of an unwanted file is low (they can ignore it), the cost of a missing one is a second round trip through the whole transcript.

## Quick mode

Read the saved file and give the user what they actually asked for — a summary, an answer extracted from the conversation, or the raw text if they want it verbatim. The script strips hidden system scaffolding messages already; what remains is the real back-and-forth. Answer inline in the chat; no separate file needed.

## Knowledge-base mode

The goal is not to reproduce the final result of the chat, but to reconstruct the relevant thread of reasoning, decisions, and change history behind it — read fully enough that a human or agent could continue the work from your output alone, without ever reopening the original chat.

### What to capture

Work through the whole transcript and pull out, wherever present:

- **Topics/goals** and how they relate to each other
- **Facts and states** established during the conversation
- **Requirements, preferences, and constraints**
- **Decisions**, with their reasoning and any alternatives that were considered
- **Changes/supersessions** — an earlier statement or decision replaced by a later one, and why
- **Insights and the reasoning behind them**
- **Solutions, concepts, architectures, and concrete results**
- **Problems, errors, risks, and limitations**
- **Discarded approaches**, with the reason they were dropped
- **Open questions, unresolved points, and next steps**
- **Technical specifics worth keeping** — values, names, commands, URLs, artifacts — if they matter for continuing the work

### Ground rules

These aren't arbitrary formatting preferences — each one exists because skipping it produces a document that looks complete but silently misleads whoever reads it next:

- **Tag the epistemic status of every claim.** Keep "the user said this", "this was verified as fact", "this is an assumption/hypothesis", and "the assistant proposed this" visibly distinct — collapsing them into one voice is how a tentative suggestion gets mistaken for a settled fact by the next reader.
- **Never show two contradicting statements as both still valid.** When a position changed mid-conversation, reconstruct the sequence and mark which one is the current, load-bearing state — a knowledge base that presents both without resolving them is worse than useless, because it forces the reader to re-derive what you already had in front of you.
- **Don't invent, fill in, or interpret missing information as fact.** A gap in the transcript stays a gap. If something is unclear or unresolved, say so explicitly in the open-questions/uncertainties section rather than smoothing it over.
- **Compress redundancy and small talk, not substance.** Cutting a superseded detail whose history no longer matters is fine; cutting a decision's reasoning, a dependency, or the context needed to understand why something was chosen is not — that's exactly the information a re-read of the original chat would have to recover, and the whole point is that it shouldn't have to.
- **Organize by topic and dependency, not strictly by timeline.** A chronological transcript already exists — it's the source. The value of this document is grouping what belongs together even when it surfaced in scattered turns.

### Output structure

Write the knowledge base as a single Markdown file with exactly these five sections, in this order. **Default the knowledge base's language to German**, matching this repo's convention for artifacts explicitly meant for the user's own reference (see the `deep-monograph` skill for the same precedent) — regardless of the source chat's language, and use a different language only if the user explicitly asks for one. The headings below are therefore given in German (the mandated output), with an English gloss for reference:

```markdown
# <Titel, der das Thema des Chats wiedergibt>

## 1. Gesamtbild / aktueller Stand              (overall picture / current state)
## 2. Themenbereiche                            (topic areas — one subsection per topic,
                                                  each with its own facts, requirements,
                                                  decisions, insights, and results)
## 3. Entscheidungs- und Änderungshistorie       (decision & change history)
## 4. Offene Punkte / Risiken / nächste Schritte (open points / risks / next steps)
## 5. Unsicherheiten / Widersprüche              (uncertainties / unresolved contradictions)
```

This is a deliberate exception to writing everything else in English; it applies only to the produced document's content, not to your own reasoning or any code.

Don't let this turn into one bloated §2 with four thin cross-reference stubs around it — §3 and §5 carry real content, not pointers. §2 holds the per-topic detail (facts, requirements, current decisions); §3 holds the actual earlier→current transitions with their reasons, even where a topic subsection in §2 already mentions the current state; §5 holds the actual unresolved items and open contradictions, not a link back to where they're mentioned. Only §1 (a short current-state overview) and §4 (a punch list) are legitimately summary-style, pointing into §2/§3 rather than repeating them.

### Definition of done

Before delivering, check the draft against the checklist that made it necessary in the first place: every part of the transcript that carried decisions, reasoning, or results has been considered; current information is separated from superseded information; decisions carry their reasoning; uncertainties are marked as such rather than silently resolved one way; and someone could pick up the work from this document alone.

### Delivering the result

This is a keep-forever artifact, not a working file — it must never end up in a scratch/temp directory (including this session's own scratchpad, which exists for intermediate files, not deliverables). Where it belongs depends on what the conversation is *about*, not which directory happens to be open right now — a chat about some other project must not land inside whatever repo the current session happens to be sitting in. Pick the location, save there, and announce the path when you deliver the file — don't pause mid-task to check it in first; knowledge-base mode is now the default response, so stopping to confirm a save location on every run would defeat the point of not interrupting the user.

- **The conversation is clearly about a specific project/repo you can locate** (it names the project, or the user is actively working in that exact project right now): look for that project's existing documentation home first — a `docs/` folder, `CONTEXT.md` + `docs/adr/`, a `notes/` directory, whatever it already has — and file the knowledge base there, following its existing naming pattern. If nothing like that exists yet, create one sensible, clearly-named location under that project's root (e.g. `docs/knowledge-base/<topic-slug>.md`).
- **No specific project applies, or it's ambiguous which one does**: save to a fixed personal location instead, `~/Documents/Chat-Wissensbasen/<topic-slug>.md` (create the folder if it doesn't exist yet).

Name the file with a descriptive kebab-case slug of the chat's subject — that alone already avoids the collision a generic `knowledge-base.md` would hit the moment this runs a second time. Then send it to the user with `SendUserFile` pointing at that real path — this is the deliverable, not a summary of it. A short inline note (what it covers, roughly how long) is enough alongside the file; don't also paste the full document into the chat.

## Dependencies

`turbo_stream_decode.py` (bundled, no install needed) handles the ChatGPT path. The Gemini and Claude.ai paths need Playwright's headless Chromium: `pip install playwright && playwright install chromium` if not already present.
