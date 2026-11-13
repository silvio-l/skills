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

### `grundschutz-audit` — global

**The Problem.** A security review of a codebase stops at technical findings. An organisation that has to show conformity with BSI IT-Grundschutz or ISO/IEC 27001 also needs protection needs, a modelled requirement package, a risk analysis, a security concept and tracked measures with evidence. That is the work of an information security officer, and it is usually done by hand with an outdated building-block list.

**The Fix.** A user-invoked procedure (`/grundschutz-audit [audit|verify] [scope] [quick|standard|deep]`) that acts as the information security officer and runs autonomously from end to end:

- **Scope and protection needs.** It fixes the scope and the structure analysis, and rates protection needs before any technical work.
- **Modelling.** It models the current BSI Grundschutz++ user catalog, which is fetched at run time and pinned to a commit, never bundled. A stdlib helper (`scripts/gspp.py`) does the deterministic work: ISMS practices always, category inheritance, raised-level selection, deduplication, and mandatory relevance decisions.
- **Technical check.** It runs Cloudflare's MIT-licensed `security-audit` workflow, bundled unchanged in `technical/` (default profile `standard`).
- **Target/actual check.** It validates the check under the binary UMS rule: evidence for every "implemented", and dependencies respected.
- **Risk analysis and concept.** It performs a risk analysis per BSI 200-3 and writes the full security concept, an implementation plan and an ISO 27001 Annex A statement of applicability.
- **Issues.** It opens one issue per measure. On a public tracker, the issue carries only the measure ID.

All documentation lives outside the audited repo. A `verify` mode re-checks the evidence independently and closes or reopens issues. The result is explicitly an unofficial, certification-oriented best-effort self-declaration, not a certificate.

### `lan-computer-use` — global

**The Problem.** Agents that drive a desktop through screenshots are slow, token-hungry and guess at pixels. Remote machines in the LAN, such as a Windows test PC or a second Mac, are usually out of reach entirely. When the agent controls the machine you are sitting at, you cannot tell what it is doing or when it will stop.

**The Fix.** `scripts/cu.py` controls this Mac or LAN Macs and Windows PCs through a tiny agent: a single Swift or C# file that is compiled on the target on first use and runs in the logged-on desktop session. It is reached through an SSH tunnel with a per-session token, so each command costs only a local round trip.

- **Reading the UI.** `snapshot -i` returns a flat list of actionable accessibility elements with refs (`[e7] button "Save"`). The agent clicks, presses, focuses or sets values by ref instead of by coordinates. Every input answers with the resulting foreground window and focus, which saves follow-up screenshots.
- **When pixels are needed.** Screenshots, OCR on macOS and `click --img` cover UIs without an accessibility tree.
- **Overlay.** A compact yellow warning panel on the target shows the task, the current action and a countdown. It is excluded from screen capture.
- **Safety.** Password fields are refused. `down` removes the agent without a trace.

### `omada-admin` — global

**The Problem.** A TP-Link Omada SDN controller exposes two different HTTP API surfaces (OpenAPI v1 and Web API v2) with different auth flows, and its actual base paths and resource names don't match the patterns a naive read of the web UI or older documentation would suggest — a base path with a subtly wrong path segment (singular vs. plural) returns a generic "unsupported path" error indistinguishable from a genuinely missing feature, and DHCP reservations aren't a listed resource at all but a field buried on each client.

**The Fix.** A model-invoked skill documenting both API surfaces from paths verified against a live controller rather than guessed from the UI, including the corrected site-scoped base path, the confirmed working DHCP-reservation read/write recipe (`clients/{mac}.ipSetting`, verified end-to-end including a real two-NIC reservation swap), and an honest split between confirmed-working endpoints and unverified-but-documented payload shapes rather than presenting both with equal confidence. Deliberately excludes browser-DevTools-based endpoint discovery, since a future agent instance typically has no browser access to fall back on.

### `premium-desktop-pruefung` — global

**The Problem.** "Review the UI" on a desktop app ends in a screenshot tour: the agent grades its own findings, misses the second window, the setting without a visible entry and the focus that is lost after a dialog closes, and calls the audit done. Fanning the work out to many subagents is no fix either — a dozen agents that each build and launch the app saturate the machine and fight over one keyboard focus.

**The Fix.** A user-invoked procedure (`/premium-desktop-pruefung [scope] [focus]`) that audits an existing desktop app against a bundled German premium desktop standard and a 46-rule catalog (onboarding, settings, accessibility, native input), then fixes, verifies and retests. The coordinator surveys four views (product paths, code, running UI, platform/states), cuts disjoint audit units and runs them in waves with a fresh critic after every wave, a fresh verifier per finding, an independent retester and a final critic. Load is capped: `audit.py capacity` suggests at most three parallel subagents from the current load per core, only one subagent drives the GUI, the coordinator builds once and workers reuse that build, and only one implementer edits the tree — limits defer work to later rounds, they never shrink scope. Workers write fragment files only; `audit.py merge` folds them into a single ledger, and `audit.py check` refuses COMPLETE until every rule is mapped, every unit closed, every reviewer independent and the final snapshot hash still matches the evidence.

### `website-creator` — global

**The Problem.** "Build a landing page" ends in the same generated look on every project: Inter on a cream or violet gradient, three icon cards, gradient headline, bouncy animations, and German marketing filler ("nahtlos", two-beat slogans, CTAs that never say what the click does). The agent never looks at the competition, never checks the page at phone width, and declares it done.

**The Fix.** A user-invoked procedure (`/website-creator [page] [focus]`) for building or redesigning landing, marketing and product pages in the project's own stack. It researches the three largest competitors live (text and visuals), drafts the German copy against a bundled editorial taste guide (`TASTE.md`; a project's own takes precedence) and stops for the user's choice of a copy skeleton. `concept.py` lets an image model (Codex CLI on the subscription, never an API key; else a local model, an HTML mockup or a recorded gap) draft its own picture of the page from the reference board as a second opinion. `seed.py` then rolls three distinct visual directions from a seed (layout archetype, font pairing, color posture from restrained to drenched with exactly one radical direction, OKLCH palette from the binding brand color with checked contrast, motion tier: restrained, signature or video, and a disclosed weighting of competitors, galleries, concept image and craft rules) and stops again for the user's pick, which becomes a `DESIGN.md`. Liveliness comes first: a playable demo, 3D or a video loop beats scroll storytelling, with hard limits for performance, CSP and reduced motion in `references/media.md`. After the build, `slop_lint.py` flags generated-UI and copy tells, missing `data-testid`s and (as warnings) uniform section runs and text-heavy pages, and `render_check.py` renders the page at several widths for overflow, contrast, tap targets and console errors. A Stop hook (`run.py`) keeps the agent working until decisions, research, concept image, directions, lint, render and `DESIGN.md` all hold — at most three rounds, every exception logged with a reason.

### `youtube-transcript` — project-local

**The Problem.** YouTube's auto-generated caption files use "rolling captions" — every line of text appears twice in a row (once as a preview of the next block, once as the finalized block) wrapped in inline word-timing tags like `<00:00:00.320><c>word</c>`. An agent reading a `.vtt` file directly gets a transcript with every sentence duplicated or tripled, and has no standing guidance on the right `yt-dlp` flags for metadata, manual-vs-auto subtitle fallback, or comment extraction — so each session reinvents (and sometimes gets wrong) the same handful of commands.

**The Fix.** A thin, deterministic workflow: pull metadata first (`--dump-json`) to decide whether manual subtitles exist before falling back to auto-captions, fetch the transcript, then always pipe the resulting `.vtt` through a bundled stdlib-only script (`scripts/clean_vtt.py`) that strips the timing tags and drops lines already emitted by a recent cue (a small trailing window, not just "equals the previous line" — a cue can carry over more than one prior line unchanged) rather than ever reading the raw file — verified against a real video end-to-end via n-gram redundancy checks, plus its error paths (missing file, empty file). An optional `--timestamps` mode emits `[mm:ss] text` per line for tasks that need to locate a specific moment, not just read the gist. A short pitfalls section covers the harmless `impersonation` warning, `--skip-download` still fetching a tiny metadata format, and mapping common `yt-dlp` failures (private/deleted/region-locked video, no captions available) to a clear message instead of a raw traceback.

## License

[MIT](./LICENSE).
