# Domain Docs

How the engineering skills should consume this repo's domain documentation when exploring the codebase.

## What "domain" means here

This is unusual for a Matt-Pocock-style setup. The "domain" of this repo is not an application domain (Orders, Users, Payments) — it is **skill authoring itself**. `CONTEXT.md` at the repo root documents the vocabulary of writing and shipping skills: `Skill`, `SKILL.md`, `Frontmatter`, `Trigger pattern`, `Discovery`, `Roundtrip`, `Source of truth`.

When a skill like `improve-codebase-architecture` or `diagnose` is invoked here, "domain concept" means a term from that skill-authoring vocabulary, not a business noun. A refactor proposal in this repo should talk about "the trigger phrase of the skill," not "the order intake module."

## Before exploring, read these

- **`CONTEXT.md`** at the repo root — the skill-authoring vocabulary.
- **`docs/adr/`** — read ADRs that touch the area you're about to work in.

If `docs/adr/` does not exist, **proceed silently**. Don't flag its absence; don't suggest creating it upfront. The producer skill (`/grill-with-docs`) creates ADRs lazily when decisions actually get resolved.

## File structure

Single-context repo. `CONTEXT.md` at the root, optional `docs/adr/`:

```
/
├── CONTEXT.md
├── docs/
│   ├── adr/                              ← created lazily by /grill-with-docs
│   └── agents/                           ← the file you are reading
└── skills/
```

No `CONTEXT-MAP.md`; no per-context `CONTEXT.md` files under `skills/<name>/`. Each skill has its own internal vocabulary (in its SKILL.md and supporting files), but the project-level shared language lives at the root.

## Use the glossary's vocabulary

When your output names a concept (in an issue title, a refactor proposal, a hypothesis, a test name), use the term as defined in `CONTEXT.md`. Don't drift to synonyms the glossary's "Anti-vocabulary" section explicitly avoids — e.g. write "skill," not "prompt" or "plugin."

If the concept you need isn't in the glossary yet, that's a signal — either you're inventing language the project doesn't use (reconsider) or there's a real gap (note it for `/grill-with-docs`).

## Flag ADR conflicts

If your output contradicts an existing ADR, surface it explicitly rather than silently overriding:

> _Contradicts ADR-0007 — but worth reopening because…_

There are no ADRs yet, so this is only relevant once one is recorded.
