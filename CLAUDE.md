# CLAUDE.md — Maintenance Guide for AI Agents

This repo is the source of truth for my personal Claude Code skills. It is maintained by AI agents (mostly Claude Code itself) — that is who this guide is for.

## Workflow

```
edit here → git commit → git push → npx skills@latest update -g -y
```

1. Edit skill files in this working copy (`~/Documents/Projekte/skills/`).
2. Commit with [Conventional Commits](https://www.conventionalcommits.org/) — `feat(skill-name): …`, `fix(skill-name): …`, `docs: …`, `chore: …`.
3. Push to `origin/main`.
4. Refresh the global installation with **`update`**, not `add`:
   - `npx skills@latest update -g -y` — refresh all global skills (auto-detects the source repo per skill, pulls only what changed).
   - `npx skills@latest update <skill-name> -g -y` — refresh a single skill, e.g. `update humanize-text -g -y`.

   **Do not use `add … -g` to refresh.** On the current `skills` CLI (≥1.5.x) global `add` fails with `PromptScript: PromptScript does not support global skill installation` for any skill that ships scripts (all of mine). `add` is for a *first-time* install only — and even then use it without `-g` (`npx skills@latest add silvio-l/skills`, which prompts for scope/skill/agent and installs project- or user-level). Once a skill is installed, `update` is the only working refresh path.

**Never edit `~/.claude/skills/<skill-name>/` directly.** Those paths are CLI-managed symlinks into `~/.agents/skills/<skill-name>/`. Any edit there is overwritten on the next install.

## Repo layout

```
.
├── README.md              ← public-facing overview; lists every skill
├── LICENSE                ← MIT
├── CLAUDE.md              ← this file
├── CONTEXT.md             ← vocabulary for skill authoring
├── .gitignore
├── skills/                ← bundled as-is by the skills CLI
│   ├── apple-notes/
│   │   ├── SKILL.md
│   │   ├── REFERENCE.md
│   │   └── scripts/
│   │       ├── apple-notes        ← dispatcher (AppleScript wrapper)
│   │       └── _helper.py         ← HTML→text + base64 extraction
│   ├── context-optimization-audit/
│   │   ├── SKILL.md
│   │   └── REFERENCE.md
│   ├── domain-glossary/
│   │   └── SKILL.md
│   ├── full-quality-scan/
│   │   ├── SKILL.md
│   │   └── scripts/scan-all.sh
│   └── ratchet-up/
│       ├── SKILL.md
│       ├── algorithm.md
│       ├── formats.md
│       ├── gates.md
│       ├── planner.md
│       ├── reviewer.md
│       ├── worker.md
│       └── scripts/check-evidence.sh
└── tests/                 ← NOT shipped by the skills CLI
    └── apple-notes/test_helper.py
```

`tests/` lives outside `skills/` on purpose. The `skills` CLI bundles a skill directory wholesale, so anything beside `SKILL.md` (and friends) ends up on every installer's disk. Tests stay in the repo for AI-agent maintenance but never travel with the install.

## Adding a new skill

1. `mkdir skills/<new-name>`.
2. Create `skills/<new-name>/SKILL.md` with YAML frontmatter:

   ```yaml
   ---
   name: <new-name>           # lowercase, hyphens; MUST match the directory name
   description: <English prose, ≤ 250 chars HARD CAP; end with trigger phrases (may be German) — see "Authoring language" and CONTEXT.md "Trigger pattern">
   ---

   # <Human Title>

   …
   ```

3. Add supporting files as needed (`REFERENCE.md`, `scripts/`, additional phase `.md` files). Everything in the skill's directory is bundled as-is by the `skills` CLI.
4. **Update `README.md`** — add a `### <skill-name>` block in the "The skills" section using the same *Problem/Fix* shape as the existing entries. If the new skill depends on something from `mattpocock/skills`, also add it to the prerequisites table. The README is the public surface; a skill that is not in it is invisible to anyone browsing the repo.
5. Commit, push, roundtrip.

For guidance on what makes a good skill (description shape, trigger phrases, supporting-file structure), invoke Matt Pocock's `/write-a-skill` rather than reinventing the convention.

## Frontmatter rules (enforced by the `skills` CLI)

- `name` — required. Lowercase, hyphens only. MUST match the directory name.
- `description` — required. One paragraph, **≤ 250 characters. This is a hard cap — never exceed it.** The description *is* the auto-invoke router: it must carry the core trigger phrases ("Use when …") and nothing more. Push every detail (modes, flags, tool lists, examples) into the body. Don't overcorrect into terseness either — too short and the model can't tell when to load the skill; aim for ~200–250 chars with the essential triggers intact. Count characters before committing (`python3 -c 'print(len(open("…").read()))'` on the extracted value, or just eyeball against an existing in-cap skill).
- `metadata.*` — optional. Used for extra hints (e.g. `metadata.argument-hint` in `ratchet-up`).
- `disable-model-invocation: true` — optional. Makes the skill **user-invoked only** (a procedure) and removes its `description` from the model's auto-invoke context entirely, so it costs zero ambient tokens. Set it on skills you always trigger deliberately by slash command and would never want the model to auto-load — e.g. heavyweight, stateful, or argument-driven controllers (`ratchet-up`, `ship-to-appstore`, `ship-to-playstore`). **Do NOT set it** on skills whose value is auto-discovery via natural-language triggers (`humanize-text`, `figma-to-flutter`, `openai-image`, `full-quality-scan`, `seo-audit`, `to-roadmap`) — disabling those defeats carve-out #1 in "Authoring language". The test: *would the model ever usefully load this without the user typing the slash command?* If no → disable.

Frontmatter is currently checked by hand. If the skill count grows, add a small lint script and a CI job.

## Harness hygiene (context discipline)

Every model-invoked skill pre-loads its `description` into the system prompt at startup ([Anthropic — Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)); a large always-on skill set is real context cost and degrades routing ("context rot"). Two ongoing practices keep the harness lean:

1. **Invocation-type discipline** — classify every new skill as a *procedure* (user-invoked; prefer `disable-model-invocation: true`) or an *ability* (model-invoked; description stays in context). Default to procedure unless auto-discovery is the point. See the `disable-model-invocation` rule above.
2. **Periodic blank-slate audit** — run `context-optimization-audit` **in a fresh session** (not at the tail of a long one — a polluted context mismeasures the baseline) to catch description leak, redundant globally-installed skill clusters, and stale instructions. Prefer project-scoped installs over global (`-g`) for skills only relevant to one project type.

## Authoring language (HARD RULE)

**Skill documentation is written in English.** This is non-negotiable and applies to every new skill and every edit: `SKILL.md` (including the `description` prose), every supporting/phase/reference `.md` file, code comments inside scripts, and the skill's `README.md` block. The repo's baseline is English (this file, `README.md`, `ratchet-up`, `formats.md`); a German skill body is a defect to fix, not a style choice. Rationale: a skill must be readable by any agent or maintainer that picks it up, and mixed-language bodies fracture that.

The user prompts in German and the *running* agent still talks to the user in German (per the global `~/.claude/CLAUDE.md` language rule) — that is conversation, not skill source, and is unaffected by this rule.

Three deliberate carve-outs stay non-English (everything else is English):

1. **Trigger phrases in the `description`.** German trigger phrases may — and should — be kept alongside the English ones, because the `description` is the auto-invoke router and the user phrases requests in German (e.g. `'Screens prüfen'`, `'Figma in Flutter umsetzen'`, `'sieht generisch / nach KI aus'`). The descriptive prose around them is still English.
2. **Functional language data.** Content that *is* the skill's payload rather than its documentation stays in its native language — e.g. `humanize-text`'s German slop lexica, `seo-audit`'s German brand anti-vocabulary. These are data, not prose.
3. **Deliberate German artifact/output mandates.** Where German is the skill's stated intent for what it *produces*, the mandate stays (phrased in English). Example: `domain-glossary` mandates that the `CONTEXT.md` artifact is authored in German because the project domain is German — the instruction is English, the mandated artifact language is German on purpose.

When in doubt, ask: is this string *documentation* (→ English) or *payload/trigger/output* (→ may stay German)?

## Tooling and testing

There is no CI and no global test runner. Verification is still the roundtrip: push, install, confirm the skill is discoverable in a fresh agent session.

**Tests are welcome where a script can fail silently** — i.e. where a bug produces plausible-but-wrong output that the roundtrip cannot see. Today this applies to:

- `skills/apple-notes/scripts/_helper.py` — regex-driven HTML stripping and base64 extraction. A missed edge case produces text the agent will happily use without noticing the loss. Tests live at `tests/apple-notes/test_helper.py`.

Tests are deliberately **not** added for:

- `skills/ratchet-up/scripts/check-evidence.sh` — a bug surfaces as a wrong exit code, which the orchestrator routes on immediately. Loud failure.
- `skills/full-quality-scan/scripts/scan-all.sh` — wraps external tools (flutter, cppcheck, eslint, semgrep, osv-scanner). Tests would freeze their output formats and rot with every upstream update. The output is also loudly wrong if the parser breaks.

### Conventions

- Tests live in `tests/<skill-name>/` at the repo root — **outside** `skills/`. The `skills` CLI bundles a skill directory wholesale; shipping tests to every installer would just bloat the bundle.
- Plain `unittest` (stdlib). No framework, no requirements file, no fixtures dir. A test file should be runnable with `python3 tests/<skill-name>/test_*.py` from the repo root.
- Tests set `sys.dont_write_bytecode = True` and pass `PYTHONDONTWRITEBYTECODE=1` to any subprocesses, so they leave no `__pycache__` inside `skills/`. `.gitignore` covers it as a second line of defense.
- Run them locally before pushing if you touched the underlying script. There is no CI to catch a red test.

## Vocabulary

See [`CONTEXT.md`](./CONTEXT.md). Read it before introducing new terms.

## Agent skills

Per-repo configuration for the engineering skills from `mattpocock/skills`. Generated by `/setup-matt-pocock-skills`; edit the underlying docs directly to change behaviour.

### Issue tracker

Local markdown under `.scratch/<feature>/`. `.scratch/` is currently gitignored, so issues are private working notes rather than shared tracking. See [`docs/agents/issue-tracker.md`](./docs/agents/issue-tracker.md).

### Triage labels

Five canonical status strings (`needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`) written into each issue file's `Status:` line. See [`docs/agents/triage-labels.md`](./docs/agents/triage-labels.md).

### Domain docs

Single-context. `CONTEXT.md` at the root documents the *skill-authoring* vocabulary (not an application domain). `docs/adr/` does not yet exist; created lazily by `/grill-with-docs`. See [`docs/agents/domain.md`](./docs/agents/domain.md).
