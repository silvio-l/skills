---
name: instructions-optimizer
description: Compresses AI instruction files (CLAUDE.md, .cursorrules, copilot-instructions.md) by cutting general knowledge, keeping project rules/commands. Trigger: 'CLAUDE.md komprimieren', 'Instruktionsdatei optimieren', 'aufgeblähte .cursorrules'.
disable-model-invocation: true
---

# Instructions Optimizer

## Purpose

Reduces token usage of AI instruction files via delta-refactoring: subtract general knowledge, keep the project-specific delta.

`Optimized file = Original − general knowledge + project delta`

The judgment call — what counts as general knowledge vs. a hard project-specific rule — is yours, made per file, not automated. `scripts/compress.py` only handles the mechanical parts (finding candidate files, counting tokens, rendering the report); it never writes to an instruction file itself.

## Workflow

### 1. Discover candidate files

```
python3 scripts/compress.py discover --path <project-root>
```

Prints a JSON array of `{path, tokens}` for every candidate found under the project root and the well-known global locations (`~/.claude`, `~/.github`). It matches by filename case-insensitively and dedupes by inode, so a case-insensitive filesystem never returns the same physical file twice.

Matched filenames: `CLAUDE.md`, `CONTEXT.md`, `.cursorrules`, `copilot-instructions.md`, and any `*.rules` / `*.instructions.md` file (searched recursively, but only under the project root — never recursively under the home directory). Automatically skips `.git/`, `node_modules/`, `dist/`, `build/`, `.next/`, `venv/`, and similar build/dependency directories.

**Never a target, even if the user names it:** `.claude.json`, `.claude.yaml`/`.claude.yml`, or any other Claude Code state/config file. Those hold live session state, not instruction prose — rewriting them can corrupt the user's setup. If the user explicitly asks to compress one of these, decline and explain why.

### 2. Critical analysis (the top directive)

**No deletion for deletion's sake.**
- If a file is already dense and token-optimal → leave it unchanged.
- Never destructive. Every cut must preserve value.
- When unsure whether something is general knowledge or project-specific, keep it.

### 3. Delta-refactoring (compression)

**Remove (general knowledge Claude already knows):**
- Generic best practices ("write clean code", "use meaningful names")
- Standard framework concepts (how React Router works, basic TypeScript types)
- Well-known programming patterns (Factory, Observer, MVC)
- Narrative prose, greetings, filler
- Repeated or redundant explanations

**Keep (project delta, unchanged and prioritized):**
- Hard, project-specific architecture decisions ("we use X instead of Y because Z")
- Exact CLI commands, paths, and build pipelines
- Directory structures and defined storage locations
- Error-driven rules (things agents in this codebase keep getting wrong)
- Specific project conventions and constraints
- Hard prohibitions (what must NOT be done)

Do this rewriting yourself, file by file, following the rules above — don't hand it to a regex. A script can't tell a load-bearing project rule from filler; only reading the file can.

### 4. Write outputs and count tokens

For each file you actually change:
1. Write the compressed content to `<file>.compressed` (e.g. `CLAUDE.md.compressed`) — never overwrite the original yet.
2. Run `python3 scripts/compress.py count <file>` and `count <file>.compressed` to get the before/after token estimate (or use the `tokens` value `discover` already gave you for the original).

For a file you leave unchanged, its optimized token count equals its original token count.

### 5. Render the report

Build a JSON manifest (`[{"path", "original_tokens", "optimized_tokens"}, ...]`) covering every discovered file, then:

```
python3 scripts/compress.py report <manifest.json> --out prompt-compression-report.md
```

Writes the report to the project root and prints its own summary — don't hand-format the table.

### 6. Stop and ask before touching the original

Report to the user which files got a `.compressed` candidate and the savings each achieved. **Do not overwrite any original file in-place until the user reviews the `.compressed` copy and explicitly approves.** This applies with extra weight to global files (`~/.claude/CLAUDE.md` and similar) — they affect every future session, not just this project, so treat approval there as non-optional even if the user approved a project-local file without hesitation.

Once approved for a given file: replace its content with the `.compressed` version, then delete the `.compressed` copy (git history is the real backup from that point on).

## Notes

- **Judgment, not pattern-matching.** The actual rewriting is done by you, reading the file — that's the whole point of this skill over a blind regex pass. The script's job ends at discovery, counting, and report formatting.
- **In-place changes need explicit approval, always** — see step 6. Never skip it because a file "looks obviously bloated."
- **Iterative.** Multiple passes are fine; compression can take more than one round, especially on files with real structural redundancy (e.g. many near-identical skill/entry descriptions that collapse better into a table than they compress line-by-line).
