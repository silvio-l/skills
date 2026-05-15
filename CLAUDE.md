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
├── README.md              ← public-facing overview
├── LICENSE                ← MIT
├── CLAUDE.md              ← this file
├── CONTEXT.md             ← vocabulary for skill authoring
├── .gitignore
└── skills/
    ├── context-optimization-audit/
    │   ├── SKILL.md
    │   └── REFERENCE.md
    ├── domain-glossary/
    │   └── SKILL.md
    ├── full-quality-scan/
    │   ├── SKILL.md
    │   └── scripts/
    └── ratchet-up/
        ├── SKILL.md
        ├── algorithm.md
        ├── formats.md
        ├── gates.md
        ├── planner.md
        ├── reviewer.md
        ├── worker.md
        └── scripts/
```

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
4. Commit, push, roundtrip.

For guidance on what makes a good skill (description shape, trigger phrases, supporting-file structure), invoke Matt Pocock's `/write-a-skill` rather than reinventing the convention.

## Frontmatter rules (enforced by the `skills` CLI)

- `name` — required. Lowercase, hyphens only. MUST match the directory name.
- `description` — required. One paragraph. End with explicit trigger phrases ("Use when …").
- `metadata.*` — optional. Used for extra hints (e.g. `metadata.argument-hint` in `ratchet-up`).

Frontmatter is currently checked by hand. If the skill count grows, add a small lint script and a CI job.

## Tooling and CI

There are intentionally no test suites, build steps, or CI in this repo. Verification is the roundtrip: push, install, confirm the skill is discoverable in a fresh agent session.

## Vocabulary

See [`CONTEXT.md`](./CONTEXT.md). Read it before introducing new terms.
