---
name: screenshot-review
description: "Uncompromising UI/UX audit of a folder of app screenshots: pulls app context from the repo, reviews each screen via a subagent against a 13-point rubric, writes actionable findings. Use when auditing screenshots, UI review, 'Screens prüfen'."
metadata:
  argument-hint: "<screenshot-folder>"
---

# Screenshot Review — Uncompromising UI/UX Audit

You are the **orchestrator** of a senior UI/UX audit over a folder of app
screenshots. You collect context, dispatch a read-only reviewer subagent per
screen, and aggregate the individual reports into a master report. You do
**not** review any screen yourself in detail — the subagents do that so your
context stays lean (no report full-text in the orchestrator).

The result is a **Markdown report** per screen plus a master report. The
format is deliberately machine-parseable (stable finding IDs, severity enum,
imperative recommendations, final worklist) so that a **downstream AI agent**
can work through the findings without back-and-forth.

The skill is **platform-agnostic** with a Flutter focus (analysis area 13).
It analyses exclusively the **visible** surface of the screenshots — it reads
no source code to form judgements and renders nothing itself.

## Where things live

| Concern | File |
|---|---|
| The 13 analysis areas (audit rubric) | [rubric.md](rubric.md) |
| Finding format, per-screen report, master report | [format.md](format.md) |
| Reviewer subagent prompt template | [reviewer.md](reviewer.md) |

Load the file you need right now. SKILL.md is the always-on layer — keep it tight.

## Core Principles

- **Uncompromising in depth, anchored in the pixel.** Actively look for
  problems, never assume something is correct, assume optimisation potential
  exists — **but** every finding points to an element *visible* in the
  screenshot. No fabricated measurements: exact px/hex from a screenshot are
  guesswork, not measurements. Phrase relatively ("headline barely heavier than
  body", "CTA and secondary button visually equivalent"), not with false
  precision ("set to 28 px"). Where vision hits its limits (1 px borders,
  shadow spread, exact contrast), say so explicitly in the finding.
- **Every screen is reviewed independently.** Never analyse multiple screens
  together — a subagent sees exactly one screenshot. **Cross-screen consistency**
  (analysis area 9) is therefore not a per-screen job but a **synthesis step**
  by the orchestrator from the individual reports (Phase 2).
- **Context-safe.** The reviewer writes its report directly to disk and returns
  only a compact summary (score + findings by severity). No report full-text,
  no image base64 enters your active context.
- **Context first, then audit.** Without app context (target audience, purpose,
  platform, design system) an audience-fit judgement (area 11) is worthless.
  Phase 0 pulls context from the repo and resolves gaps with the user **before**
  any screen is reviewed.
- **Read-only.** The skill changes no source code and no screenshots. It writes
  exclusively to its output directory. Never commit, merge, or push — that stays
  user-driven.
- **Model routing.** Always spawn reviewer subagents with `model: claude-sonnet-4-6`
  (vision-design judgement; Haiku too weak, Opus too expensive for the volume
  pass). You may escalate a single particularly critical screen to
  `claude-opus-4-8`.

## Process

### Phase 0 — Context Discovery (orchestrator, once)

1. **Determine folder.** Argument `<screenshot-folder>`; if missing → ask the
   user. List images (glob `*.png *.jpg *.jpeg *.webp`, recursive). No images
   → stop and report.
2. **Gather app context** — best effort, without asking, from:
   - `CLAUDE.md` (global + project) → target audience, stack, constraints,
     design rules.
   - `design/design-language.md` + `design/tokens.json` (if present) → the
     **declared** design language. This is the strongest available expectation;
     deviations measured against it are hard findings, not taste.
   - `pubspec.yaml` → Flutter? Material/Cupertino, platform targets.
   - `README.md` → app description/purpose.
   - optional `<folder>/manifest.yaml` → screen→expectation mapping (screen
     name, purpose, Figma node/mockup reference). Not required.
3. **Distil the briefing:** target audience · app purpose · platform · design
   system · declared tokens/expectations. Per field: value **or** `UNKNOWN`.
4. **Feedback loop (mandatory):** show the briefing compactly, flag every
   `UNKNOWN` and ask specifically. Continue only after OK / additions. Never
   guess the target audience — a wrong guess poisons every screen.

### Phase 1 — Per-Screen Review (one subagent per screenshot)

Spawn a read-only subagent (`subagent_type: general-purpose`,
`model: claude-sonnet-4-6`) per screenshot using the template from `reviewer.md`.
Independent screens may run **in parallel** (multiple tool calls in one message;
in batches to respect rate limits). Each subagent receives: the context briefing,
the screenshot path, the output path, and the contents of `rubric.md` and
`format.md`. It reads the image, works through all 13 areas, **writes**
`<output>/screens/<screen-id>.md`, and returns only the compact summary
(see `format.md` § Subagent return).

### Phase 2 — Synthesis (orchestrator)

Build the master report `<output>/report.md` from the compact returns (format
in `format.md` § Master report): score table per screen, all Critical findings
cross-screen, **app-wide consistency patterns** (same component styled differently
across screens — visible only in the aggregate), a globally prioritised worklist.
Then give the user the output path + a 3-sentence verdict.

## Output Layout

```
.scratch/screenshot-review-<YYYY-MM-DD>/
├── report.md            ← master report (Phase 2)
└── screens/
    ├── <screen-id>.md   ← one report per screenshot (Phase 1, written by subagent)
    └── …
```

`<screen-id>` = screenshot filename without extension.

## Quick Reference — When to Do What

| Trigger | Action |
|---|---|
| User runs `/screenshot-review <folder>` | Phase 0, step 1 |
| Context field `UNKNOWN` | Feedback loop (Phase 0.4) — never guess |
| Folder contains no images | Stop, report |
| Per screenshot | Reviewer subagent (`reviewer.md`, Sonnet, parallel in batches) |
| All screens reviewed | Synthesis (Phase 2) → master report |
| Consistency across screens | Phase 2 only (orchestrator aggregate), never in the per-screen pass |

## What this skill does NOT do

- No code review and no rendering — only the visible screenshots.
- No fixing. It produces findings; a downstream agent (e.g. `/ratchet-up`)
  implements them.
- No commit/merge/push.
- No joint review of multiple screens in a single subagent.
