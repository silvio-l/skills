# CONTEXT.md — Vocabulary for Skill Authoring

Canonical terms used in this repo. Use them consistently; do not invent synonyms.

## Core terms

- **Skill** — A capability available to an AI coding agent (Claude Code, Codex, Cursor, …), expressed as a directory with a `SKILL.md` entry file. Invoked by trigger phrases in user prompts, or by slash command (`/skill-name`) where the agent supports it.
- **`SKILL.md`** — The entry file of a skill. YAML frontmatter (`name`, `description`) followed by Markdown instructions for the agent.
- **Frontmatter** — The YAML block at the top of `SKILL.md`. Required fields: `name`, `description`. Optional: `metadata.*`.
- **Trigger pattern** — The phrases inside `description` that cause an agent to invoke the skill ("Use when the user says X, Y, or Z"). Trigger phrases are the public API of the skill — change them, change the calling behaviour.
- **Discovery** — How an agent finds installed skills. The `skills` CLI writes to `~/.agents/skills/<name>/` and symlinks into agent-specific paths like `~/.claude/skills/<name>/`. Agents scan those paths at session start.
- **Roundtrip** — The full edit-to-availability loop: edit in this repo → push → `npx skills@latest update -g -y` → skill is now reachable in a fresh agent session. (Refresh uses `update`, not `add -g`; the latter fails for script-bearing skills on the current CLI. See `CLAUDE.md` → Workflow.)
- **Source of truth** — This repo. The home-dir `~/.claude/skills/` is downstream — do not edit it.

## Authoring terms

- **Deep skill** vs. **shallow skill** — A deep skill encapsulates a non-obvious procedure behind a stable trigger phrase and a stable behaviour contract. A shallow skill is a one-line shortcut for a thing the agent could already do. Prefer deep.
- **Supporting file** — Any file inside a skill directory other than `SKILL.md`. Common examples: `REFERENCE.md` (lookup data), `scripts/` (helper shell), additional `.md` per phase (e.g. `ratchet-up/algorithm.md`). Bundled as-is by the CLI.
- **Phase document** — A supporting `.md` that captures one phase of a multi-phase skill (e.g. `ratchet-up/planner.md`, `worker.md`, `reviewer.md`). Used when a skill orchestrates subagents that need their own self-contained instructions.

## Workflow terms

- **Edit-here-push-roundtrip** — The maintenance loop. See `CLAUDE.md` for the canonical sequence.
- **Prerequisite skill** — A skill from another repo (typically `mattpocock/skills`) whose output formats one of my skills consumes. Listed explicitly in `README.md` so external installers know to install the upstream first.

## Anti-vocabulary

Do not use these when you mean a skill:

- ~~"Prompt"~~ — a prompt is one-off and unstructured; a skill is a discoverable, named, reusable capability.
- ~~"Command"~~ — slash commands are one way to *invoke* a skill, not what the skill *is*. A skill exists even when no slash binding is configured.
- ~~"Agent"~~ — agents *use* skills. The skill is the contract; the agent is the consumer.
- ~~"Plugin"~~ — plugins are a Claude Code marketplace mechanism. A skill can be packaged inside a plugin, but a skill is not a plugin.

## Relationship to Matt Pocock's `CONTEXT.md`

Matt's `CONTEXT.md` documents the vocabulary of skill *design philosophy* — failure modes, fix patterns, "shared language" as a concept. This `CONTEXT.md` documents the vocabulary of skill *authoring mechanics* — file layout, frontmatter, discovery, roundtrip. The two are complementary, not overlapping.
