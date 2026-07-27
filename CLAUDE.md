# CLAUDE.md — Maintenance Guide for AI Agents

This repo is the source of truth for my one remaining personal Claude Code skill,
`owasp-bsi-audit`. It is maintained by AI agents (mostly Claude Code itself) — that is who this
guide is for.

Everything else that used to live here (apple-notes, aso-research, context-optimization-audit,
domain-glossary, figma-to-flutter, flutter-design-language, full-quality-scan, humanize-text,
mail-deliverability-audit, motion-and-ui-design, openai-image, ratchet-up, screenshot-review,
seo-audit, ship-to-appstore, ship-to-playstore, to-roadmap) was retired in favour of
[`mattpocock/skills`](https://github.com/mattpocock/skills) and
[`Code-with-Beto/skills`](https://github.com/Code-with-Beto/skills). Do not resurrect them here —
install the upstream repos instead.

## Workflow

```
edit here → commit on dev → push dev → merge dev into main (ff-only) → push main → npx skills@latest update -g -y
```

**The skills CLI sources global skills from the `main` branch on GitHub (`origin/main`).** A skill edit is therefore not "live" globally until it is committed on `dev`, merged to `main`, and **both branches are pushed** — only then does `update -g` pick it up.

1. Edit skill files in this working copy.
2. **Work on `dev`, never commit directly on `main`** (solo-dev branch guard — see the global `~/.claude/CLAUDE.md`).
3. Commit with [Conventional Commits](https://www.conventionalcommits.org/). No `Co-Authored-By` trailer.
4. **Publish both branches, in this order:**
   - `git push origin dev`
   - `git switch main && git merge --ff-only dev && git push origin main && git switch dev`
5. **Then** refresh the global installation with `npx skills@latest update -g -y` (not `add … -g`, which fails for script-bearing skills on the current CLI).

**Never edit `~/.claude/skills/owasp-bsi-audit/` directly.** That path is a CLI-managed symlink into `~/.agents/skills/owasp-bsi-audit/`.

## Repo layout

```
.
├── README.md
├── LICENSE
├── CLAUDE.md
├── CONTEXT.md
├── skills/owasp-bsi-audit/   ← bundled as-is by the skills CLI
└── tests/owasp-bsi-audit/    ← NOT shipped by the skills CLI
```

## Frontmatter rules (enforced by the `skills` CLI)

- `name` — required, lowercase-hyphens, matches the directory name.
- `description` — required, ≤ 250 characters, carries the trigger phrases.
- `disable-model-invocation: true` — optional; makes a skill user-invoked only.

## Vocabulary

See [`CONTEXT.md`](./CONTEXT.md).
