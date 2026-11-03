# Skills

My personal Claude Code skills: a small, deliberately narrow set.

## Quickstart

```bash
npx skills@latest add silvio-l/skills
```

Pick the skills you want and the agents you want to install to. The installer is the generic [`skills` CLI by Vercel Labs](https://github.com/vercel-labs/skills).

Only install `-g` (global) the ones you want available in *every* session; install the rest per-project with `-s <skill-name>` and no `-g`. See the scope tag on each skill below.

## Updating

After new versions land upstream, refresh your local copy:

```bash
npx skills@latest update                    # interactive: picks scope, lists changes
npx skills@latest update -g                 # all global skills, no prompts
npx skills@latest update -g apple-notes     # one specific skill
```

The CLI tracks where each installed skill came from and pulls only what changed.

## The skills

Each skill is tagged **global** (installed with `-g`, available in every session regardless of project) or **project-local** (installed per-project via `add -s <skill-name>`, no `-g`) — install a project-local skill from the target project's root with `npx skills@latest add silvio-l/skills -s <skill-name> -y`.

### `apple-notes` — global

**The Problem.** Non-technical collaborators write bug reports, ideas, and feedback wherever it is comfortable — for me, that is Apple Notes. The agent cannot reach into Notes; the human cannot reach into the issue tracker. The result is a swamp of half-captured intent that never makes it into a session.

**The Fix.** A single dispatcher (`scripts/apple-notes`) wraps AppleScript to read, search, write, and image-extract from Notes on macOS. Subfolders of one configured "company folder" map to projects (auto-resolved from the current git repo). Each project enforces a four-folder layout — `inbox` / `ready` / `done` / `docs` — with title prefixes (`BUG:` `FEAT:` `IDEA:` `FB:` `TECH:`) so the partner drops things in `inbox`, the agent triages from there, and nothing has to leave Notes until it is ready to become a real issue. Note titles are just the first body line, which Apple Notes truncates with an ellipsis — so when a collaborator dumps everything into the first line, the dispatcher still resolves the note from the truncated title, a prefix, or its stable `id` (exposed in `notes --json`).

### `fetch-shared-chat` — global

**The Problem.** Shared ChatGPT/Gemini/Claude.ai chat links are client-rendered SPAs — a plain `curl` or `WebFetch` returns an empty app shell, not the conversation, so the obvious approach silently fails. Worse, ChatGPT's DOM-rendered page client-side-redirects to its homepage both when a share is genuinely inaccessible *and* when nothing is actually wrong, making the two cases indistinguishable without digging further — and a naive fix risks fabricating a summary of content nobody ever actually read. And once the text is actually retrieved, "summarize it" throws away exactly the reasoning, decisions, and dead ends a user often wants to keep and continue working from later.

**The Fix.** A model-invoked skill that dispatches on the share URL's host. ChatGPT goes through its React Router single-fetch `.data` endpoint via plain HTTP — no browser at all — decoded by a from-scratch, cross-validated reimplementation of the `turbo-stream` wire format, which additionally surfaces the *exact* server-side reason a share failed (deleted vs. access-denied vs. workspace-scoped) instead of the ambiguous DOM redirect. Gemini falls back to headless-Chromium rendering, since no server-side data endpoint is known for it. Claude.ai is attempted the same way but currently hits a Cloudflare bot challenge, which the skill detects and reports explicitly rather than passing through as fake content. Every failure path returns a concrete, worded reason instead of an empty or fabricated result. Once fetched, the skill defaults to a knowledge-base mode that distills the transcript into a structured Markdown file organized by topic rather than timeline (current state, per-topic facts/decisions/results, decision and change history, open points, unresolved contradictions), tagging every claim's epistemic status (user statement vs. verified fact vs. assumption vs. assistant proposal) and refusing to paper over superseded or contradicting statements, delivered as a file via `SendUserFile` rather than pasted inline — falling back to a quick inline answer only when the user's ask is genuinely a narrow, one-off question.

### `fetch-open-chat-tab` — global

**The Problem.** Not every conversation can become a `fetch-shared-chat` share link — sharing can be off, or the conversation is one the user never intends to share. The chat still exists, live and fully rendered, in whatever Safari tab has it open — but that content only exists as JavaScript-rendered DOM in an already-authenticated session, invisible to any network-level fetch.

**The Fix.** A model-invoked skill that drives the user's own Safari tab directly via `do JavaScript` (through a small JXA driver), reading the real DOM — never a screenshot or OCR. Built against three live conversations (one per site) rather than assumed selectors, which surfaced two real bugs a naive implementation would have shipped silently: Claude.ai's `[data-test-render-count]` looked assistant-specific but actually tags *every* turn's markdown rendering, so an early version double-counted each user message as a duplicate "assistant" entry — fixed by keying off `[role="article"][aria-posinset]` instead, a stable per-turn position that also fixes collection order once claude.ai's (and likely gemini.google.com's) DOM virtualization is accounted for: long conversations un-mount off-screen messages, so a single DOM snapshot silently misses most of a long chat, requiring a scroll-to-top-then-sweep collection loop instead. A second bug — JXA's Standard Additions `read` command silently mangling non-ASCII text into mojibake — was caught the same way and fixed via the Foundation/NSString bridge for guaranteed UTF-8. An unstructured `body.innerText` fallback (clearly labeled, distinct exit code) covers any site without a dedicated extractor rather than failing outright.

### `omada-admin` — global

**The Problem.** A TP-Link Omada SDN controller exposes two different HTTP API surfaces (OpenAPI v1 and Web API v2) with different auth flows, and its actual base paths and resource names don't match the patterns a naive read of the web UI or older documentation would suggest — a base path with a subtly wrong path segment (singular vs. plural) returns a generic "unsupported path" error indistinguishable from a genuinely missing feature, and DHCP reservations aren't a listed resource at all but a field buried on each client.

**The Fix.** A model-invoked skill documenting both API surfaces from paths verified against a live controller rather than guessed from the UI, including the corrected site-scoped base path, the confirmed working DHCP-reservation read/write recipe (`clients/{mac}.ipSetting`, verified end-to-end including a real two-NIC reservation swap), and an honest split between confirmed-working endpoints and unverified-but-documented payload shapes rather than presenting both with equal confidence. Deliberately excludes browser-DevTools-based endpoint discovery, since a future agent instance typically has no browser access to fall back on.

### `youtube-transcript` — project-local

**The Problem.** YouTube's auto-generated caption files use "rolling captions" — every line of text appears twice in a row (once as a preview of the next block, once as the finalized block) wrapped in inline word-timing tags like `<00:00:00.320><c>word</c>`. An agent reading a `.vtt` file directly gets a transcript with every sentence duplicated or tripled, and has no standing guidance on the right `yt-dlp` flags for metadata, manual-vs-auto subtitle fallback, or comment extraction — so each session reinvents (and sometimes gets wrong) the same handful of commands.

**The Fix.** A thin, deterministic workflow: pull metadata first (`--dump-json`) to decide whether manual subtitles exist before falling back to auto-captions, fetch the transcript, then always pipe the resulting `.vtt` through a bundled stdlib-only script (`scripts/clean_vtt.py`) that strips the timing tags and drops lines already emitted by a recent cue (a small trailing window, not just "equals the previous line" — a cue can carry over more than one prior line unchanged) rather than ever reading the raw file — verified against a real video end-to-end via n-gram redundancy checks, plus its error paths (missing file, empty file). An optional `--timestamps` mode emits `[mm:ss] text` per line for tasks that need to locate a specific moment, not just read the gist. A short pitfalls section covers the harmless `impersonation` warning, `--skip-download` still fetching a tiny metadata format, and mapping common `yt-dlp` failures (private/deleted/region-locked video, no captions available) to a clear message instead of a raw traceback.

## License

[MIT](./LICENSE).
