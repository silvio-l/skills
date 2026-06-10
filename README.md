# Skills

My personal Claude Code skills. Engineering process, context hygiene, and AI-agent maintenance — distilled into composable skills, straight from my `.claude` directory.

## Quickstart

```bash
npx skills@latest add silvio-l/skills
```

Pick the skills you want and the agents you want to install to. The installer is the generic [`skills` CLI by Vercel Labs](https://github.com/vercel-labs/skills) — the same one Matt Pocock uses.

## Updating

After new versions land upstream, refresh your local copy:

```bash
npx skills@latest update                 # interactive: picks scope, lists changes
npx skills@latest update -g              # all global skills, no prompts
npx skills@latest update -g ratchet-up   # one specific skill
```

The CLI tracks where each installed skill came from and pulls only what changed — across this repo, Matt's, and any others you have installed.

## Prerequisites: install Matt Pocock's skills first

These skills are built on top of the conventions, vocabulary, and issue formats produced by [`mattpocock/skills`](https://github.com/mattpocock/skills). **Install Matt's skills first** — several of mine consume what his produce.

```bash
npx skills@latest add mattpocock/skills
# then, inside an agent session:
/setup-matt-pocock-skills
```

Which of mine depends on which of Matt's:

| My skill | Depends on Matt's |
|---|---|
| `ratchet-up` | `/to-issues`, `/triage`, and the issue-tracker config from `/setup-matt-pocock-skills` |
| `domain-glossary` | `/grill-me` (mandatory in the interview loop); extends the `CONTEXT.md` philosophy from `/grill-with-docs` |
| `full-quality-scan` | parallel-subagent dispatch pattern shared with Matt's process-oriented skills |
| `context-optimization-audit` | audits the loaded surface, including Matt's installed skills |

If you only want one of these, skip the dependencies you do not exercise.

## The skills

### `apple-notes`

**The Problem.** Non-technical collaborators write bug reports, ideas, and feedback wherever it is comfortable — for me, that is Apple Notes. The agent cannot reach into Notes; the human cannot reach into the issue tracker. The result is a swamp of half-captured intent that never makes it into a session.

**The Fix.** A single dispatcher (`scripts/apple-notes`) wraps AppleScript to read, search, write, and image-extract from Notes on macOS. Subfolders of one configured "company folder" map to projects (auto-resolved from the current git repo). Each project enforces a four-folder layout — `inbox` / `ready` / `done` / `docs` — with title prefixes (`BUG:` `FEAT:` `IDEA:` `FB:` `TECH:`) so the partner drops things in `inbox`, the agent triages from there, and nothing has to leave Notes until it is ready to become a real issue.

### `context-optimization-audit`

**The Problem.** Claude Code loads everything in sight — skills, MCP servers, plugins, project instructions. Over time the context turns into a buffet. You lose tokens, signal-to-noise drops, and the model gets distracted.

**The Fix.** Audit every loaded surface — skills, agents, slash commands, MCP/plugin config, project files — and propose what to cut, merge, condense, disable, or move. Nothing is changed without your approval; the skill produces a plan first.

### `domain-glossary`

**The Problem.** Devs and domain experts speak different languages. So do agents and the projects they wake up in. You burn tokens explaining the same nouns every session.

**The Fix.** Build a `CONTEXT.md` collaboratively. The glossary is the artifact; the real work is getting the language right. Lifts Matt's "shared language" idea from `/grill-with-docs` and turns it into an explicit, repeatable authoring loop.

### `full-quality-scan`

**The Problem.** "Run all the linters" is fine until a scanner returns 200 findings and the agent tries to fix them inside a single context. Halfway through, you run out of room and lose the rest.

**The Fix.** A threshold: ≤10 findings → fix directly. >10 → produce a plan first, then dispatch parallel subagents per finding cluster. Each subagent works in isolation; the orchestrator never holds the full pile in one head.

### `openai-image`

**The Problem.** Generating an image from a prompt always means re-deriving the same boilerplate: which OpenAI model supports transparency, how the key is loaded, how to retry a flaky 429, how to decode the base64 to a file. Every project reinvents it, and the API key ends up copy-pasted into yet another script that risks getting committed.

**The Fix.** One self-contained Node script. It picks the model automatically — `--transparent` ⇒ `gpt-image-1` (the only one with an alpha channel), everything else ⇒ the higher-quality `gpt-image-2` — resolves the API key from its own gitignored `.env` (or the shell env), retries transient 429/5xx/network errors with exponential backoff, and writes PNG(s) to disk. No project dependencies; usable from any directory. `--dry-run` validates the resolved config for free before spending a credit.

### `ratchet-up`

**The Problem.** An agentic loop that grinds through issues sounds great until you realize each iteration drags the whole feature's state back into the orchestrator's context. Six issues in, you are hallucinating dependencies that do not exist.

**The Fix.** A context-safe ratchet — discover ready issues, respect `blocked-by`, dispatch isolated workers and read-only reviewers, gate on format/analyze, persist rework feedback to disk. The orchestrator stays small; the work moves forward one click at a time, never backward.

### `humanize-text`

**The Problem.** AI-generated text in German and English bleeds through the same hollow openers, inflation particles, and filler verbs — „Zudem", „Darüber hinaus", „Es ist wichtig zu beachten", "delve", "leverage", "seamlessly" — regardless of topic. They signal machine origin, flatten the author's voice, and accumulate quietly across a codebase until the site reads like a press release.

**The Fix.** A bilingual (DE/EN), offline, deterministic slop pipeline with three modes. `--mode scan` matches every file against curated tier-1 DE/EN lexica (word-boundary, case-insensitive, with opt-in `inflect` stemming for German declension) plus language-neutral tier-2/tier-3 structure tells (em-dash, negative parallelism, tricolon), auto-detects language, handles `.md`, `.html`, `.astro`, and `.ts` filetypes with appropriate strip strategies, and returns sorted findings with replacement suggestions. `--mode score` runs the five-dimension scorer (directness, rhythm, trust, authenticity, density; 50 pts max) and exits 1 when below threshold — wiring it into `ratchet-up` gates is one-liner work. `--mode rewrite` is an agent-side protocol: the script findings drive a targeted LLM rewrite pass that protects proper nouns (loam, whispaste, hellerio) and technical terms, invents nothing, and waits for explicit user confirmation before changing any file.

### `seo-audit`

**The Problem.** SEO audits collapse into three failure modes: paid tools you do not want to depend on (Ahrefs, Semrush, Screaming Frog Pro), one-off shell hacks that nobody re-runs because they are not reproducible, and brand-voice drift that nobody catches until a redesign — by which time half the site contradicts the glossary in `CONTEXT.md`.

**The Fix.** A local-first, free-tier-only audit skill that runs the same pipeline every time: inventory the repo (framework, pages, SEO assets, app-store listings, domain doc) → match the anti-vocabulary table from `CONTEXT.md` against the built HTML in `dist/` (with per-file and per-section suppression markers for kontrastive content) → synthesize findings by `severity × user_impact / fix_effort` with a deterministic tiebreaker → write a single Markdown report under `.scratch/<feature>/seo-audit-<date>.md` with Executive Summary, Findings nach Kategorie, Diff zum letzten Lauf, Empfehlungen. v1 is strictly offline; external probes (Lighthouse, pa11y, GSC, W3C, Schema, Observatory) come in slice 02, push (IndexNow, Bing, `llms.txt` generation) in slice 03.

### `to-roadmap`

**The Problem.** A raw idea document or rough PRD is too big to feed straight into `/to-prd` — the agent either drowns in scope or quietly skips half the features. And once a roadmap exists, mid-flight changes (new sprint, split, drop, reorder) tend to fragment it instead of staying coherent. There is no upstream layer that owns the roadmap as a living artifact.

**The Fix.** Three operations on `.scratch/roadmap.md`: `create` decomposes the idea document into ~100k-token sprints with stable Sprint-IDs, dependencies, MVP cut, and later-release ordering; `update` patches the roadmap surgically from a free-text instruction with a diff-plan-then-confirm flow; `status` flips a sprint through `todo → in-progress → done`, called manually or automatically by `ratchet-up` at the start and end of a loop. One sprint at a time later becomes one PRD via `/to-prd`.

## Credit

These skills exist because [Matt Pocock](https://github.com/mattpocock) made his own [`mattpocock/skills`](https://github.com/mattpocock/skills) public and showed what a working skill ecosystem looks like. The structural choices here — directory layout, frontmatter conventions, the `npx skills@latest add` install path, the failure-mode/fix narrative pattern in this README — are his. If you find any of this useful, point upstream first.

## License

[MIT](./LICENSE).
