# CLAUDE.md — Maintenance Guide for AI Agents

This repo is the source of truth for my personal Claude Code skills. It is maintained by AI agents (mostly Claude Code itself) — that is who this guide is for.

## Workflow

```
edit here → git commit → git push → npx skills@latest add silvio-l/skills
```

1. Edit skill files in this working copy (`~/Documents/Projekte/skills/`).
2. Commit with [Conventional Commits](https://www.conventionalcommits.org/) — `feat(skill-name): …`, `fix(skill-name): …`, `docs: …`, `chore: …`.
3. Push to `origin/main`.
4. Refresh the local installation: `npx skills@latest add silvio-l/skills -g` (or omit `-g` for the full interactive flow with scope, skill, and agent prompts).

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
   description: <one paragraph; end with trigger phrases — see CONTEXT.md "Trigger pattern">
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
- `description` — required. One paragraph. End with explicit trigger phrases ("Use when …").
- `metadata.*` — optional. Used for extra hints (e.g. `metadata.argument-hint` in `ratchet-up`).

Frontmatter is currently checked by hand. If the skill count grows, add a small lint script and a CI job.

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
