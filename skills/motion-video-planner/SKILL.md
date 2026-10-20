---
name: motion-video-planner
description: Plan a shareable motion-graphics video (social reel, explainer, promo, logo sting): three concepts and a self-contained HyperFrames production prompt, no rendering. Use for 'video concept', 'video idea', 'Videokonzept', 'Videoidee', 'Video planen'.
metadata:
  argument-hint: "[what the video is about, or a path to a briefing]"
---

# Motion Video Planner

Turn a product repository or a briefing into a short interview, three distinct concepts, and one
production prompt that a fresh coding-agent session can execute with HyperFrames, without this
conversation. **This skill plans; it does not produce.** Do not create compositions, generate media,
call paid services, or render. If the user wants the video built now, hand over the prompt and say
it runs best in a fresh session.

Talk to the user in their language. Every artifact of the plan is a file in the plan directory,
so a later session can resume.

## Workflow

Run the phases in order. Load each reference when its phase starts, not before. For
`occasions.md` and `style-kit.md`, read only what you need: list the headings
(`grep -n '^##' <file>`), then read the intro, "How to use a style" and the chosen styles, or
the one occasion section, by line range.

### A. Context: understand before asking
Load [references/context-discovery.md](references/context-discovery.md).
- In a repository: run `python3 "${CLAUDE_SKILL_DIR}/scripts/inventory_repo.py" <repo> --json <plan-dir>/inventory.json`,
  then read systematically and verify every candidate claim against the code.
- Without a repository: work from the briefing and supplied material.
- Separate verified facts, roadmap, and assumptions; record coverage and gaps honestly.
- Write `<plan-dir>/context.md` and tell the user the plan directory.

### B. Interview: at most 10 questions in total
Load [references/interview.md](references/interview.md).
- Summarize what you understood and the defaults you will use, then ask.
- One question per message, at most 4 options with the recommendation first, plus a free answer.
  Wait for each answer.
- One of the 10 is reserved for the concept selection. Never ask what the material answers.
- Delegation ("entscheide du") means you decide and say why.
- End with the confirmed / decided / blockers summary; log it in `<plan-dir>/decisions.md`.

### C. Concepts: three, substantially different
Load [references/creative-principles.md](references/creative-principles.md),
[references/concepts.md](references/concepts.md), the occasion's section of
[references/occasions.md](references/occasions.md), and
[references/style-kit.md](references/style-kit.md).
- Three concepts that differ in hook mechanism, protagonist, and dramaturgy, not only in style.
- Each with first seconds, story, open question, share and rewatch trigger, product and brand link,
  style, duration, effort, assets, and risks.
- Compare qualitatively (no scores), recommend one, ask the selection question, wait.
- Save to `<plan-dir>/concepts.md`.

### D. Production prompt: self-contained and checked
Load [references/production-prompt-template.md](references/production-prompt-template.md),
[references/hyperframes-facts.md](references/hyperframes-facts.md), and
[references/quality-checklist.md](references/quality-checklist.md). For a worked reference, see
[references/example-production-prompt.md](references/example-production-prompt.md) (read it only
when unsure about the level of detail; do not copy its content).
- Write `<plan-dir>/production-prompt.md` from the template: every section filled, no
  placeholders, no references to this chat, timings marked as planned.
- Run the hand-over gate (quality-checklist §1):
  `python3 "${CLAUDE_SKILL_DIR}/scripts/check_prompt.py" <plan-dir>/production-prompt.md --assets-root <base>`
  until it exits 0, then the arithmetic consistency pass, then a cold read by a subagent that sees
  only the prompt. A clean checker run is necessary, not sufficient: structure passes easily
  while times, layouts, and rules still contradict each other.
- Present the path, a short summary, the check results, the risks, and how to start production.

If `${CLAUDE_SKILL_DIR}` is not set, use the directory that contains this file.

## Hard rules

- **Evidence over plausibility.** No invented metrics, testimonials, ratings, vote results, or
  performance promises. Roadmap items are never current features. Every claim in the video has
  its evidence in the prompt's Appendix B.
- **No virality promises.** The creative principles are design hypotheses; compare concepts in
  words, never with scores or reach forecasts.
- **Goals:** reach first, brand recall second, conversion after that, unless the user states
  another goal. A stated goal wins.
- **A video takes no viewer input.** Quizzes, predictions, comparisons, and dilemmas are staged
  with a pause and a reveal (see occasions.md).
- **HyperFrames is the default executor.** Name an alternative only with a concrete reason.
  Deterministic animation only; all media available before render; never plan a custom render
  engine or `render --docker`.
- **Costs:** no paid generation unless the user approved a budget; never assume a provider or
  model is available. Prefer code-drawn assets, the user's files, and free sources.
- **Format honesty:** no blanket 60 fps or constant motion; decide holds per piece. Transparency
  only as MOV ProRes 4444 or WebM VP9.
- **Respect boundaries:** read the repository, never modify it (except the plan directory); do
  not commit plan files unless asked; install nothing during planning (`npx --no-install` for
  version checks).
- **No brand, no invention presented as brand:** if logo, colors, or fonts do not exist, propose
  a look marked `PROVISIONAL`; a missing logo file blocks the final render, not the plan.

## Files

| File | Load when |
|---|---|
| [references/context-discovery.md](references/context-discovery.md) | Phase A |
| [references/interview.md](references/interview.md) | Phase B |
| [references/creative-principles.md](references/creative-principles.md) | Phase C (and when judging a concept) |
| [references/occasions.md](references/occasions.md) | Phase C, the section for the occasion only |
| [references/style-kit.md](references/style-kit.md) | Phase C (choose looks), phase D (look rules) |
| [references/concepts.md](references/concepts.md) | Phase C |
| [references/production-prompt-template.md](references/production-prompt-template.md) | Phase D |
| [references/hyperframes-facts.md](references/hyperframes-facts.md) | Phase D, and in C when feasibility is unclear |
| [references/quality-checklist.md](references/quality-checklist.md) | Phase D, before hand-over |
| [references/example-production-prompt.md](references/example-production-prompt.md) | Phase D, only to calibrate detail |
| `scripts/inventory_repo.py` | Phase A, repository mode |
| `scripts/check_prompt.py` | Phase D, hand-over gate |

## Resuming

If `<plan-dir>` already holds `context.md`, `decisions.md`, or `concepts.md`, read them, tell the
user where the plan stands, and continue at the next phase. Questions already asked count
toward the budget of 10.
