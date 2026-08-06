# Skills

My personal Claude Code skills: a small, deliberately narrow set.

## Quickstart

```bash
npx skills@latest add silvio-l/skills
```

Pick the skills you want and the agents you want to install to. The installer is the generic [`skills` CLI by Vercel Labs](https://github.com/vercel-labs/skills).

## Updating

After new versions land upstream, refresh your local copy:

```bash
npx skills@latest update                    # interactive: picks scope, lists changes
npx skills@latest update -g                 # all global skills, no prompts
npx skills@latest update -g apple-notes     # one specific skill
```

The CLI tracks where each installed skill came from and pulls only what changed.

## The skills

### `brainstorming`

**The Problem.** Asking a model to "brainstorm" produces either a listicle of the ten answers anyone would give, or a wall of "wild" ideas that keep circling the same handful of tropes — fungal networks, ant colonies, swarms — because a model's idea of randomness is itself a learned pattern, not actual chance. Either way it's a monologue: the model talks, the human reads, nothing is actually explored together.

**The Fix.** A seven-step, three-gate divergent-ideation interview (`disable-model-invocation: true` — run it by name, it never fires itself) built around one deliberate design choice: every "random" element — twelve domain lenses, ten three-way collisions, an unstuck provocation card — comes from `scripts/draw`, which pulls from a 122-entry `deck.json` using real OS entropy (`--seed` makes any draw exactly reproducible), not the model improvising chaos. The ten obvious answers get gathered first but only as material to invert, collide, and mutate, never as output. A fixed catalog (`TECHNIQUES.md`) of inversion questions, contradiction pairs, radicality tiers, and SCAMPER/TRIZ-flavored mutation operators gets applied in full at each step, building toward at least 40 tagged raw concepts and 20 mutations. Human judgment enters only at two gates — framing the question, and picking which raw ideas survive to mutation and the final ranking — everything else is agent legwork. Every one of the final twelve concepts has to carry its full descent chain (which lenses, collisions, inversions, or operators produced it) and pass a checkable surprise test, so the session can't quietly drift back to generic suggestions.

### `deep-monograph`

**The Problem.** "Write me a deep article about X" either produces a shallow listicle dressed up in headers, or a wall of text that drowns the reader in disconnected facts — no coherent mental model, no traceable evidence, no idea which claims are verified fact versus manufacturer marketing versus the model's own guess, and no confirmation the assignment was even understood correctly before the agent started typing.

**The Fix.** A clarify → research → write → verify pipeline for book-chapter-depth explanatory work, aimed at private/home-user readers. A hard confirm-and-wait gate extracts everything determinable from context first and asks only genuinely outcome-critical questions before a word gets written. Research runs in cycles against a source hierarchy (laws/standards → primary sources → official docs → independent tests → practice reports → forums, last) with every material claim typed — verified finding, manufacturer claim, experience value, plausible inference, editorial recommendation, or open question — and cross-checked, never faked. Writing follows an explanatory contract (purpose → whole → components → interplay → mechanism → limits → practice, never detail-first) with mandatory per-chapter comprehension checks, then passes six separate quality gates (fact/source, technical, adversarial counter-check, didactic, practice, copy-edit) against explicit acceptance criteria instead of a vague self-score. Auto-selects single-response output (~4k–25k words across both modes, depending on requested depth) versus an agentic workspace mode with its own checkpoint/resumption files for longer multi-session runs, and is honest throughout about which capabilities (web research, video transcripts, file access) are actually available rather than pretending.

### `apple-notes`

**The Problem.** Non-technical collaborators write bug reports, ideas, and feedback wherever it is comfortable — for me, that is Apple Notes. The agent cannot reach into Notes; the human cannot reach into the issue tracker. The result is a swamp of half-captured intent that never makes it into a session.

**The Fix.** A single dispatcher (`scripts/apple-notes`) wraps AppleScript to read, search, write, and image-extract from Notes on macOS. Subfolders of one configured "company folder" map to projects (auto-resolved from the current git repo). Each project enforces a four-folder layout — `inbox` / `ready` / `done` / `docs` — with title prefixes (`BUG:` `FEAT:` `IDEA:` `FB:` `TECH:`) so the partner drops things in `inbox`, the agent triages from there, and nothing has to leave Notes until it is ready to become a real issue. Note titles are just the first body line, which Apple Notes truncates with an ellipsis — so when a collaborator dumps everything into the first line, the dispatcher still resolves the note from the truncated title, a prefix, or its stable `id` (exposed in `notes --json`).

### `owasp-bsi-audit`

**The Problem.** "Audit this against OWASP and BSI IT-Grundschutz" is a task with
no shape until someone decides which of the hundred-plus BSI Bausteine even apply,
what "Schutzbedarf normal" means in practice, and how a solo developer's app
compares to the enterprise-with-an-ops-department the standard assumes. Do it by
hand and you either drown the agent's context in every requirement at once, or
skip the parts of the methodology (Strukturanalyse, Schutzbedarfsfeststellung,
Modellierung) that make a Grundschutz-Check traceable instead of a vibe-check.

**The Fix.** An orchestrator that runs the actual BSI-Standard-200-2 process —
structure analysis, protection-need assessment, Baustein/standard modeling
confirmed with the user before dispatch, then the Grundschutz-Check itself — while
keeping the main context free: one Sonnet subagent per confirmed control group
(a BSI Baustein, an ASVS chapter, a MASVS category, ...) reads its own controls
and the code, judges like a human auditor (not keyword matching), and writes its
findings straight to disk with the mandatory BSI vocabulary (ja/teilweise/nein/
entbehrlich, justified) or the OWASP one (pass/fail/partial/n_a). The catalogs
themselves are machine-fetched from the official upstream sources (ASVS 5.0,
MASVS 2.1, the BSI Kompendium XML, curated NIST SSDF and SLSA subsets) rather than
hand-copied, and re-resolve to whatever the latest version is on each refresh. The
BSI Baustein selection is deliberately narrow — most of the Kompendium's ~111
Bausteine are organizational-governance or physical-infrastructure practices that
don't translate to "check this in the code" for an individual developer; only the
ones describing an actual software artifact survive. The rendered report makes
the methodology itself visible (which Bausteine were applied and what they cover,
what was explicitly out of scope, the full Soll-Ist comparison sorted Basis-before-
Standard in natural requirement order) and ships as a self-contained, badge-
colored HTML report with a one-click "copy an AI-agent fix prompt" button per
finding (or all of them at once) alongside the Markdown report and a prioritized
fix-plan.

### `escalate`

**The Problem.** Sonnet is the mandated default, but some tasks quietly need more — a stuck bug, a hard reasoning chain, a UI tweak, a security-sensitive change — and nothing forces the agent to notice and hand off instead of grinding on at the wrong tier. The two existing hard rules only cover design and planning/review; everything else is left to hope the agent remembers to ask for help.

**The Fix.** A model-invoked skill that routes a task through a fixed signal → tier table (UI/design → `fable`; architecture/roadmap synthesis, hard reasoning, stuck bugs, high-stakes/hard-to-reverse correctness → `opus`; everything else stays on Sonnet, explicitly, to avoid wasteful escalation — `/code-review` and security audits keep their own existing routing) and dispatches via the `Agent` tool with the model set explicitly. Splits mixed-signal tasks across tiers instead of forcing one subagent to cover both, has the subagent do the work rather than just advise, verifies its actual diff before reporting back, and always states which tier handled the task and why.

### `app-icon-director`

**The Problem.** Most app icon requests default to "generic symbol on a gradient" because nothing forces a deliberate choice between representing the *product* (function-first) versus the *brand* (company/logo-first) — and when it should be both, the usual result is a cluttered logo-plus-symbol collage instead of a genuinely owned visual idea.

**The Fix.** A manually-invoked creative-direction skill that gathers existing brand/product context from the repo, forces an explicit PRODUCT/BRAND/HYBRID strategy choice with stated reasoning, triages which brand assets are actually icon-capable, and develops three genuinely distinct concepts (not three variations) scored against recognizability, distinctiveness, and brand/product fit before recommending one. Concept and master-art generation are delegated to a Fable subagent per the operator's design-escalation rule — this skill plans and judges, it doesn't design inline. From the finished master SVG, a bundled script deterministically produces the actual platform asset sets — iOS (App Store Connect), macOS (`.icns` via `iconutil`), Windows (`.ico`, plus an opt-in full Microsoft Store MSIX asset set), and Android (launcher mipmaps, adaptive icon, Play Console listing icon) — each at the sizes and formats each store's own current docs specify (e.g. Play Console's listing icon needs alpha, Apple's must not), then self-validates that every required file actually exists at the correct pixel dimensions before anything is reported done. A second, fresh Fable subagent reviews rendered previews (smallest sizes especially) against the validation checklist as a final quality gate. For Expo/RN projects, hands the master SVG to the `app-icon` skill instead, which is already wired into Expo's asset pipeline.

### `fetch-shared-chat`

**The Problem.** Shared ChatGPT/Gemini/Claude.ai chat links are client-rendered SPAs — a plain `curl` or `WebFetch` returns an empty app shell, not the conversation, so the obvious approach silently fails. Worse, ChatGPT's DOM-rendered page client-side-redirects to its homepage both when a share is genuinely inaccessible *and* when nothing is actually wrong, making the two cases indistinguishable without digging further — and a naive fix risks fabricating a summary of content nobody ever actually read.

**The Fix.** A model-invoked skill that dispatches on the share URL's host. ChatGPT goes through its React Router single-fetch `.data` endpoint via plain HTTP — no browser at all — decoded by a from-scratch, cross-validated reimplementation of the `turbo-stream` wire format, which additionally surfaces the *exact* server-side reason a share failed (deleted vs. access-denied vs. workspace-scoped) instead of the ambiguous DOM redirect. Gemini falls back to headless-Chromium rendering, since no server-side data endpoint is known for it. Claude.ai is attempted the same way but currently hits a Cloudflare bot challenge, which the skill detects and reports explicitly rather than passing through as fake content. Every failure path returns a concrete, worded reason instead of an empty or fabricated result.

### `seo-aso-optimizer`

**The Problem.** "Optimize this site for SEO" is a task an agent will happily improvise its way through — re-deriving the same technical checklist from scratch every run (sometimes missing an item, sometimes inventing a composite "score" nobody asked for), guessing at target keywords instead of pulling the site's actual Search Console performance, and generating filler content that never gets checked against real striking-distance opportunities. An app with no marketing website at all falls through the cracks entirely, since App Store listings don't get crawled and ranked the way a website does.

**The Fix.** A single audit-fix-verify procedure grounded in a deterministic crawl script (`scripts/audit_site.py`, stdlib-only) that checks every page in the sitemap against a fixed rule set — titles, meta descriptions, H1s, canonical/lang/viewport tags, structured-data validity, alt text, thin content, orphan pages, broken internal links — and prints a findings-first report (violations grouped by rule) instead of a per-page wall of text, with the full per-page data pushed to a JSON sidecar read only on demand. Real Google Search Console data (via the `mcp__gsc__*` tools) drives keyword targeting: striking-distance queries — position 5–15, real impressions, under-earning CTR — get mapped to an owning page before any content gets written, distinguishing "ranks fine, converts badly, fix the title" from "doesn't rank, needs real depth or doesn't exist yet." Every technical fix is gated on human sign-off before publishing. A disclosed branch (`APP-TO-WEBSITE.md`) covers the case of an app with no website: pulling keywords from its store listing and building the hero/guides/FAQ page structure that gives it something to rank in the first place — explicitly scoped to the website, not native App Store/Play Store listing optimization.

### `marketing-video-automation`

**The Problem.** Recording a marketing/demo video for an app today means either an agent clicking live on screen during the recording — jittery, unrepeatable, mistakes baked straight into the footage — or manually driving the app by hand while a separate recorder runs. Mobile, web, Electron, and native macOS/Tauri apps each need a completely different automation and capture toolchain, so nothing carries over between projects, and the "make it look like Screen Studio" polish step usually gets skipped or redone by hand every single time.

**The Fix.** A model-invoked skill that separates driving the app from recording it, and routes to one of four platform branches based on how the app actually runs, each disclosed as its own reference file with that branch's install/explore/dry-run/capture commands: Maestro YAML flows for iOS/Android with built-in `maestro record`; Playwright CLI for web and Electron apps via `video-start`/`video-chapter`/`video-stop`; and for native macOS or Tauri desktop apps — WKWebView, not Chromium, so treated as native rather than web — AppleScript/JXA through `macos-automator-mcp` or Hammerspoon driving accessibility elements, paired with a capture tier from zero-install `screencapture -V` up through OBS + `obs-cmd` for scene composition. Every branch enforces the same discipline: write the storyboard, dry-run it clean twice, then replay it verbatim while a separate recorder captures the take — never improvise on camera. A fourth reference file covers post-production honestly: auto-zoom/cursor-highlight polish is a GUI step (OpenScreen, DaVinci Resolve) with an `ffmpeg` scriptable fallback for fixed push-ins and device-frame overlays, then exact export commands for MP4/GIF/animated WebP with the size/fps/width numbers that keep a GIF small, and a verification step via `ffprobe`/`gifsicle` so a deliverable counts as done only once it's confirmed to actually open at the target spec.

### `name-clearance-red-team`

**The Problem.** "Is this name okay to use?" invites an agent to confirm the name is safe — a quick search, a couple of clean-looking results, a reassuring answer — when what's actually needed is someone trying to prove the opposite: hunting for the conflicting trademark, the taken company name, the descriptive-term refusal, the domain that's not actually free. No trademark register offers reliable automated access either, so a naive implementation would deadlock — every deep run blocked on the same unautomatable lookups, tempting the next pass to fake completion just to produce a usable report.

**The Fix.** An adversarial clearance procedure that scores a candidate name across registered marks, company/business names, unregistered rights, absolute refusal grounds, and digital availability, then red-teams its own findings before rendering one of five deliberately conservative verdicts (`PRELIMINARILY CLEAR` … `DO NOT USE`) — never a legal guarantee. Intake is interview-style: it pulls what it can from the repo and conversation context first and only asks for what's genuinely missing, never a form to fill in up front. Every gate (13 of them) is derived from artifacts actually on disk — a search-log row, a finding, a red-team rebuttal — never a self-reported boolean, and a blocked/CAPTCHA'd/bot-blocked lookup can never be recorded as "no hits found." The deadlock is broken by design: a Checkpoint C hands unautomatable lookups (DPMA, TMview, WIPO — none offer a public API) to the user as an exact URL/query/filter list, and a user-verified row satisfies its gate exactly like an agent-completed one. An incomplete run still renders its full report — findings, coverage, red team, evidence — with only the verdict line replaced by `RESULT INCOMPLETE`, so there's never pressure to fake a gate just to get a usable artifact. Deterministic checks (RDAP domain lookups, GitHub/npm/PyPI existence) run via stdlib-only scripts alongside the research; the whole skill names no model and never downgrades reasoning tier for a lookup step, so it runs the same way in any agent CLI, not just this one.

### `godot-cli`

**The Problem.** Godot's command-line surface is one binary with roughly 90 flags spread across general, run, display, debug, and standalone-tool categories, several with sharp edges an agent won't know to expect: unknown flags fail silently instead of erroring, export output paths resolve against the project directory rather than the shell's CWD, a first export on an uncached project can freeze unless an import pass runs first, and the engine's own `--test` flag is a red herring for anyone trying to run a game project's actual test suite.

**The Fix.** A compact, model-invoked reference split for token efficiency: `SKILL.md` covers binary discovery (including the macOS `.app` bundle path), project-path resolution, headless mode, and five named workflows — import, export, running a one-off GDScript task, syntax-checking a script, and running GUT unit tests — plus the gotcha list above, stated explicitly enough that the agent reaches for GUT instead of `--test`. The full ~90-flag table (display, debug, profiling, doctool/API-dump, 3-to-4 conversion) lives in `REFERENCE.md`, loaded only on demand, with `godot --help` named as the authoritative fallback for anything version-specific this file doesn't cover.

## License

[MIT](./LICENSE).
