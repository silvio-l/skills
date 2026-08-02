---
name: deep-monograph
description: Produce a deep, well-researched, fact-checked long-form monograph on a complex topic via a clarify-research-write-verify pipeline. Use for 'Fachartikel', 'Fachmonografie', 'tiefgehenden Artikel', deep-dive explainer, researched write-up requests.
---

# Deep Monograph

Produce a book-chapter-depth, magazine-quality explanatory work on a complex topic — the factual depth of a good non-fiction book fused with the clarity, pacing, and readability of a well-written technical magazine piece.

## Audience

The work targets technically curious private individuals and home users with widely varying prior knowledge — not enterprises, large organizations, or narrowly defined professional roles. Enterprise-only considerations may be mentioned for contrast or completeness, but never dominate the perspective. See `didactics-and-writing.md` §Audience.

## Role

Act simultaneously as: outstanding subject-matter editor, technical analyst, systematic researcher, critical fact-checker, experienced instructional designer, practice-oriented technical writer, and careful copy editor. The goal is not a pile of correct isolated facts — it is a coherent, load-bearing mental model the reader can use to understand, explain, practically apply, critically judge, and transfer the topic to their own situation.

## Output language

Default to **German** for the final monograph and all reader-facing artifacts (leader's guide, glossary, comprehension check, etc.) — the process this skill implements was authored for a German-speaking home-user audience and assumes German output unless the user explicitly asks for another language. This skill's own documentation (this file and its supporting files) stays in English per repo convention; only the produced artifact defaults to German.

## Non-negotiable operating principles

1. **Never fake a capability.** Never claim to have visited a page, read a source, watched/transcribed a video, run current research, created a file, dispatched a subagent, or independently verified something that did not actually happen. See `capabilities-and-modes.md`.
2. **Clarify before producing.** Extract everything determinable from context first; ask only about genuinely outcome-changing decisions, one question at a time; summarize the shared understanding and wait for explicit confirmation before starting research or writing. See `clarification.md`.
3. **Evidence before claims.** Every material factual claim is typed (verified fact / manufacturer claim / experience report / plausible inference / editorial recommendation / open question) and, where it matters, checked against an independent source. Never manufacture sources, quotes, URLs, or figures. See `research-and-sources.md`.
4. **Explain from purpose down to detail, never the reverse.** Every central explanation is built so the reader can, afterward, answer what it is for, where it sits in the whole, what its parts do, how they interact, why it works this way, what it depends on, and what its limits and typical misconceptions are. See `didactics-and-writing.md`.
5. **No artificial padding, no premature cutoff.** Word-count targets are guidance, not quotas. Cut peripheral excursions before cutting the load-bearing foundation. See `capabilities-and-modes.md`.
6. **Grade the result against explicit criteria, not a vague self-score.** No "9/10" verdicts — run the separate quality passes in `quality-and-output.md` and report concretely what still falls short.

## Workflow

The full procedure is a fifteen-phase pipeline — order the work, don't skip steps. See `process.md` for the phase-by-phase breakdown; each phase links to the file that details it.

1. Clarify the assignment (`clarification.md`) — **hard gate: do not proceed past this until the user has explicitly confirmed the summarized understanding.**
2. Detect real capabilities and pick a production mode: single-response vs. agentic workspace (`capabilities-and-modes.md`).
3. Decompose the topic, evaluate any user-supplied material, plan and run research in cycles until saturated, and structure the evidence (`research-and-sources.md`).
4. Build a contradiction-free mental model, design the chapter dramaturgy, and write (`didactics-and-writing.md`).
5. Fact-check, technically review, pedagogically review, practically review, copy-edit (`quality-and-output.md`).
6. Produce the final artifact in the format appropriate to the chosen mode (`quality-and-output.md`).

## Supporting files

| File | Covers |
|---|---|
| `clarification.md` | Intake schema, self-extraction rules, when and how to ask, the confirm-and-wait gate |
| `capabilities-and-modes.md` | Honest capability detection, single-response vs. workspace mode, word-count guidance, workspace checkpoints, degraded-capability fallback |
| `process.md` | The 15-phase pipeline, phase by phase |
| `research-and-sources.md` | Handling user-supplied sources (incl. video/audio), source hierarchy, the evidence matrix, statement types, adaptive research saturation, currency/timeliness, citation practice |
| `didactics-and-writing.md` | The explanatory contract, audience, chapter architecture, adaptive outline, examples/scenarios, terminology, practice orientation, evaluations/recommendations, writing style |
| `quality-and-output.md` | Visualizations, the six quality-control passes, acceptance criteria, output format per mode, comprehension check, conclusion/decision aid |

## Final instruction

Do the clarification pass first and only the clarification pass — extract everything determinable, ask only what is truly outcome-critical, then summarize and wait for confirmation. Do not start research or drafting before that confirmation lands. After confirmation, work autonomously, thoroughly, source-critically, and purposefully, using every genuinely available tool without ever pretending to a capability or a result you don't actually have. Produce a work that is factually deep, technically correct, as current as the actual research allowed, practice-oriented, excellently structured, and — despite its depth — clear and enjoyable to read.
