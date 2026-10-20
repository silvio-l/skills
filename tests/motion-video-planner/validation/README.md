# Validation runs (2026-10-20)

End-to-end runs of `motion-video-planner` by subagents that followed `SKILL.md` from the repo
path. **All user answers in these runs are SIMULATED** and marked as such in each
`decisions.md`. No video was rendered, nothing was installed, and no paid service was called.

| Run | Occasion | Mode | Questions used | Checker | Cold read |
|---|---|---|---|---|---|
| `1-repo-whispaste/` | Social clip for an existing product | Repository (whispaste, read-only) | 5 / 10 (selection: non-recommended concept) | exit 0 | not executable as-is |
| `2-briefing-quiz/` | Knowledge quiz Reel | Briefing only | 5 / 10 | exit 0 | v1: not executable; v2: close, 5 blocking decisions |
| `3-delegated-logo/` | Logo sting, everything delegated | Incomplete briefing | 2 / 10 (selection asked, answer delegated) | exit 0 | not executable as-is |

Each directory holds `context.md`, `decisions.md`, `concepts.md`, `production-prompt.md`, and the
runner's own `validation-notes.md` (references loaded, checker output, and the skill defects it
found). `2-briefing-quiz/production-prompt.v2.md` is the revision made with the stricter gate.
It became the basis for `skills/motion-video-planner/references/example-production-prompt.md`.

## What the runs changed in the skill

- Asset status `user` (supplied by the user, not present yet). The checker warns until the file
  exists.
- Hand-over gate: an arithmetic consistency pass (times that appear twice, text widths, element
  extents, rules against scenes, mechanical counting, copy strength against the source), plus a
  **mandatory** subagent cold read. All three prompts passed the checker and still failed a strict
  cold read, so a clean checker run is necessary, not sufficient.
- Template: one explicit question policy (no interview, draft renders pre-approved, one render
  gate), executor latitude for details the viewer does not notice, registry blocks only as
  optional candidates, fonts as local files, `hyperframes transcribe` for word timings, an honest
  agent-side "review with sound", and the end-of-run rule for a missing user asset.
- Interview: total delegation still asks the concept selection, unless the concept choice was
  delegated too; questions in the conversation language.
- Context: `npx --no-install` for version probes, "located only" and "unreleased" evidence
  levels, and an unrelated repository as working directory means briefing mode.
- Occasions: quiz sound-off and answer-position rules; a missing logo blocks the final render,
  not the plan; a pure sting may honestly have no share trigger.
- Checker: "as above" is no longer a planning-chat reference (false positive).

## Trigger test (real `claude -p` sessions)

A temporary project with the skill symlinked under `.claude/skills/`; `--max-turns 3`, write tools
disabled; the result is the skill the model loaded. Three description versions were measured. v1
missed "idea" prompts. v2 (adding 'video idea', 'Videoidee') then missed "Videokonzept" in 2 of 5
runs. v3 (the shipped one, naming the occasions) got every run right.

| Prompt | Expected | v1 | v2 | v3 (shipped) |
|---|---|---|---|---|
| "Ich möchte ein Erklärvideo für meine App planen. Wo fangen wir an?" | planner | 1/1 | 3/3 | 1/1 |
| "Entwickle mir ein Videokonzept für ein Instagram-Reel über unseren neuen Shop." | planner | 1/1 | 2/4 | 4/4 |
| "Ich brauche eine Idee für ein Social-Video, das Leute teilen." | planner | 0/1 | 4/4 | 2/2 |
| "Plan a 20-second launch video for our CLI tool and write the production prompt." | planner | 1/1 | — | 1/1 |
| "Rendere das HyperFrames-Projekt in ./video als MP4." | not planner | `hyperframes-cli` | — | — |
| "Mach mir ein cooles Promo-Video für meine App." (production) | `/hyperframes` | 1/1 | 1/1 | 1/1 |
| "Was ist der Unterschied zwischen GSAP und CSS-Keyframes?" | nothing | none | none | none |

Triggering stays probabilistic; small samples. The slash command `/motion-video-planner` invokes
the skill regardless.
