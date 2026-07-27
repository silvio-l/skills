# CONTEXT.md — Vocabulary for Skill Authoring

Canonical terms used in this repo. Use them consistently; do not invent synonyms.

- **Skill** — A capability available to an AI coding agent (Claude Code, Codex, Cursor, …), expressed as a directory with a `SKILL.md` entry file. Invoked by trigger phrases in user prompts, or by slash command (`/skill-name`) where the agent supports it.
- **`SKILL.md`** — The entry file of a skill. YAML frontmatter (`name`, `description`) followed by Markdown instructions for the agent.
- **Frontmatter** — The YAML block at the top of `SKILL.md`. Required fields: `name`, `description`. Optional: `metadata.*`.
- **Trigger pattern** — The phrases inside `description` that cause an agent to invoke the skill.
- **Discovery** — The `skills` CLI writes to `~/.agents/skills/<name>/` and symlinks into agent-specific paths like `~/.claude/skills/<name>/`. Agents scan those paths at session start.
- **Roundtrip** — The full edit-to-availability loop: edit in this repo → push → `npx skills@latest update -g -y` → skill is reachable in a fresh agent session. See `CLAUDE.md` → Workflow.
- **Source of truth** — This repo. `~/.claude/skills/owasp-bsi-audit/` is downstream — do not edit it.

## Anti-vocabulary

- ~~"Prompt"~~ — a prompt is one-off and unstructured; a skill is a discoverable, named, reusable capability.
- ~~"Command"~~ — slash commands are one way to *invoke* a skill, not what the skill *is*.
- ~~"Plugin"~~ — plugins are a Claude Code marketplace mechanism. A skill can be packaged inside a plugin, but a skill is not a plugin.

## Relationship to Matt Pocock's `CONTEXT.md`

Matt's `CONTEXT.md` documents the vocabulary of skill *design philosophy*. This one documents the
vocabulary of skill *authoring mechanics* — file layout, frontmatter, discovery, roundtrip. The
two are complementary, not overlapping.
