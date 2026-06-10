# Usage Reference

## CLI — entry script

All modes go through `scripts/humanize.py`. The script lives in the skill
directory and has no external dependencies (stdlib only, Python 3.9+).

```
python3 scripts/humanize.py <file_path> [options]

Options:
  --mode scan|score     scan: report only, always exits 0 (default: scan)
                        score: quality gate, exits 0=pass / 1=needs-revision
  --format json|text    output format (default: json)
  --lang de|en|auto     language (default: auto — heuristic detection)
  --lexicon-dir <dir>   override the lexicon directory
  --threshold N         override score threshold (default 35/50)
```

## Mode reference

### --mode scan

Reads the file, runs the lexicon + structure scanner, prints findings.

```bash
python3 "$S" --mode scan --format text apps/privat/src/data/projekte.ts
python3 "$S" --mode scan --format json apps/firma/src/pages/index.astro
python3 "$S" --mode scan --lang en --format text docs/en/faq.md
```

Exit code is always 0. Use for inspection before deciding whether to rewrite.

### --mode score

Runs scan, then applies the five-dimension scorer.

```bash
python3 "$S" --mode score --format text some-page.md
python3 "$S" --mode score --threshold 40 --format json some-page.md
```

Exit codes:
- `0` — pass (overall ≥ threshold)
- `1` — needs-revision (overall < threshold)
- `2` — error (file not found, bad arguments)

Output (`--format text`) includes:
- Overall score (e.g. `42.3/50 → PASS`)
- Five dimensions: directness, rhythm, trust, authenticity, density
- Surfaced findings (tier-1 always; tier-2 when clustered)
- Tier-3 density hint when applicable

### --mode rewrite (agent-side, not a CLI flag)

Rewrite is not a `--mode` flag in the CLI. It is an agent-side protocol:
the agent runs `--mode score`, reads the findings, proposes specific edits,
and waits for explicit user confirmation before writing anything. See
[rewrite.md](rewrite.md) for the full protocol.

**No file is ever changed by the scanner or scorer.** Only an agent running
the rewrite playbook, with user approval, modifies source files.

## ratchet-up gate integration

The scorer's exit code makes it a natural `ratchet-up` quality gate. Add
it to `.ratchet-up/config.yaml` (or the `verify:` section of `CLAUDE.md`)
alongside the existing build/lint gates:

```yaml
gates:
  - name: humanize-score
    command: >
      python3 ~/.claude/skills/humanize-text/scripts/humanize.py
        --mode score
        --threshold 35
        <file>
    on_fail: needs-revision
```

For scanning a directory of files, wrap in a small shell loop:

```bash
find apps/privat/src/pages -name "*.astro" | while read f; do
  python3 "$S" --mode score --format text "$f" || exit 1
done
```

The per-file exit code (`0`/`1`) gates the ratchet loop: one failing file
stops the loop so the agent addresses it before continuing.

## Spot-check — live site samples (2026-06-10)

Two real files from the live sites were scanned as part of the AC6
acceptance check for this skill slice. No changes were made to either
file — this is a read-only record.

### DE sample: `apps/privat/src/data/projekte.ts`

```
Language: de
Findings: 11 (all punct_em_dash, tier-1)
Overall:   34.1/50  →  NEEDS-REVISION
Dimensions: directness 1.0 / rhythm 10.0 / trust 10.0 /
            authenticity 4.5 / density 8.6
```

All 11 findings are em-dash (U+2014) occurrences inside JSDoc comment
strings (e.g. `"Ein schlankes Dart/Flutter-Paket — kein Boilerplate"`).
The em-dash scanner correctly flags them at tier-1. No word-slop matches
were found. Proper nouns `loam`, `whispaste`, `hellerio`, `skills` are
intact throughout — the scanner did not touch or suggest altering them.

The `needs-revision` verdict is technically correct (11 tier-1 em-dash
hits in a 94-line file) but low-priority for a TypeScript data file: the
em-dashes live in summary strings displayed as prose on the website.
A targeted rewrite would replace `—` with ` – ` (en-dash, less AI-like)
or rephrase the summaries to remove the dash entirely.
If the `.ts` file should be excluded from scoring, add
`<!-- humanize:ignore-file -->` in a leading comment block.

### EN sample: `apps/privat/src/pages/en/index.astro`

```
Language: en
Findings: 2 (both punct_em_dash, tier-1)
Overall:   46.1/50  →  PASS
Dimensions: directness 8.0 / rhythm 10.0 / trust 10.0 /
            authenticity 9.0 / density 9.1
```

Two em-dash findings in Astro frontmatter comment lines (lines 3 and 16).
No word-slop. Score is well above the 35/50 threshold. Proper nouns in
the file (`silvio-lindstedt.de`) intact. Scanner ran without errors.

### Conclusion

Scanner ran clean on both files (exit 0 for `--mode scan`, exit 0/1 for
`--mode score` per threshold). No proper-noun damage. No fabricated content
in findings or suggested replacements. The `--mode score` verdict for the
`.ts` file is a reminder to consider `humanize:ignore-file` for pure-code
data files where em-dashes in string literals are authorial style choices.

## Demarcation from seo-audit

These two skills solve adjacent but distinct problems. Do not conflate them.

| Dimension | `humanize-text` | `seo-audit` |
|---|---|---|
| **Scope** | Source files (`.ts`, `.astro`, `.md`) AND built HTML | Built HTML in `dist/` only |
| **What it scans for** | Generic AI slop tells — vocabulary and structure patterns that appear across any project | Project-specific brand anti-vocabulary from `CONTEXT.md` (terms the project explicitly forbids) |
| **Lexicon source** | Bundled `lexicon.de.json`, `lexicon.en.json`, `structure_patterns.json` | `CONTEXT.md` / `CLAUDE.md` / `README.md` glossary table (`Begriff | Stattdessen | Grund`) |
| **Suppression marker** | `<!-- humanize:ignore -->` / `humanize:ignore-file` | `<!-- seo-audit:contrastive -->` / frontmatter `contrastiveVocabulary: true` |
| **Output** | Findings JSON / text, score, rewrite playbook | Markdown report under `.scratch/` |
| **Writes files?** | Never (scan/score); only with explicit user OK (rewrite) | Never — report only |
| **Requires dist/?** | No | Yes (brand scan reads built HTML) |

Run both on a project to catch different things:
- `humanize-text --mode scan` catches AI vocabulary drift in source.
- `seo-audit --root .` catches brand-voice violations in the built site.

They do not duplicate effort: a word like "Zudem" in source that also
appears in `dist/` would be caught by `humanize-text` (as a DE tier-1
slop pattern) but not by `seo-audit` (unless your `CONTEXT.md` glossary
explicitly lists it as forbidden brand vocabulary).
