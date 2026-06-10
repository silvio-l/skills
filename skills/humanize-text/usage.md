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
  --threshold N         override score threshold (default 37/50)
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
        --threshold 37
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

## Spot-check — HellerIO landing copy (2026-06-10, post-rework)

The HellerIO i18n dictionaries were the calibration target for the 2026
marketing-tell rework. Before the rework `de.ts` scored **50/50 PASS, 0
surfaced** despite obvious AI structure; this is the read-only record after.
No files were changed.

### DE: `website/src/i18n/de.ts`

```
Language:  de
Overall:   36.0/50  →  NEEDS-REVISION
Dimensions: directness 10.0 / rhythm 5.5 / trust 5.0 /
            authenticity 7.5 / density 8.0
Total findings: 26  |  Surfaced: 5
  line  47  [t2]  'Kein Tracking. Kein Stress'                 (struct_anaphora)
  line  60  [t2]  '— groß, klar, motivierend'                  (struct_adj_tricolon)
  line 115  [t2]  'Kein Beleg-Scannen. Kein Bank-Anbinden. …'  (struct_anaphora)
  line 121  [t2]  'Einfach, visuell, motivierend'              (struct_adj_tricolon)
  line 128  [t2]  'Komplex, feature-überladen, buchhalterisch' (struct_adj_tricolon)
```

The five surfaced findings are exactly the structural tells a reader spots
by eye. `rhythm` is held neutral (5.5) because a `.ts` dictionary is
fragments, not flowing prose. `density` (8.0) absorbs the 21 em-dash
occurrences via the density penalty without flagging any single dash. The
`en.ts` counterpart scores the same way (35.9, the English equivalents of
all five findings).

### Conclusion

The scanner now fires on modern landing-page copy that the old academic
lexicon missed entirely, while clean flowing prose (e.g. the `index.astro`
body) still passes. Proper nouns (`hellerio`) are untouched; no content is
fabricated in findings or suggestions.

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
