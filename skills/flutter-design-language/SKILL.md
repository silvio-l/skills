---
name: flutter-design-language
description: Phase-0 gate against AI design slop before the Figma→Flutter pipeline — enforces a deliberate design plan instead of a generic default. Use when starting a Flutter design, defining a theme from scratch, or a design 'sieht generisch / nach KI aus'.
---

# Flutter Design Language (Anti-Slop Phase 0)

Before a single variable is created in Figma or a `ThemeData` written in Flutter, this
**design language is decided deliberately**. Without this gate the pipeline produces
neatly packaged slop: `#4F46E5`-indigo, default Roboto/Inter, a uniform 16px radius,
centred Hero+CTA, timid palette.

> Attitude (from Anthropic's `frontend-design`): Work like the design lead of a small
> studio that gives every client an *unmistakable* identity. Templated work has already
> been rejected. Make deliberate, opinionated decisions — and take **one** genuine,
> justifiable aesthetic risk.

## Steps (mandatory, in this order)

### 1. Anchor in the subject
Name **one** concrete subject, its target audience, and **the single job** of the main
screen. Distinctive decisions come from the subject's world (materials, artefacts,
vocabulary) — not from design defaults. Use known user preferences.
Fail to pin this and you are designing the average.

### 2. Design plan = compact token system (worked out mentally)
- **Color:** 4–6 **named** hex values with justification. No default brand colour.
  Describe *why* this palette belongs to the subject.
- **Type:** 2+ roles — one characterful **Display** font (used sparingly),
  a complementary **Body** font, optionally a **Utility/Mono** for data/captions.
  Concrete font names. See the block/allow list in `REFERENCE.md`.
- **Layout:** concept in one sentence + ASCII wireframe. No reflexive centred
  Hero+CTA, no three-icon grid "because that's what you do".
- **Signature:** the **one** element people remember, embodying the subject.
  Structural devices (numbering, eyebrows, dividers) must encode something
  *true* — not decorate.

### 3. Critique against the generic default (the actual gate)
For **every** part of the plan ask: "Would I land here given a similar brief?"
If yes → it's a default, not a choice → **revise it and name what you changed and why.**
Check the plan against the slop checklist in `REFERENCE.md`. Only once the plan
passes this review do you proceed.

### 4. Commit
- `design/design-language.md` — subject, palette (with justification), typography,
  layout, signature, the chosen risk, rejected defaults.
- `design/tokens.json` — three-tier & **role-named** (see `REFERENCE.md`):
  *primitive* (raw values) → *semantic/`sys.*`* (role) → *component*. Light **and** Dark.

Then → `figma-to-flutter`: tokens feed Figma Variables **and** the Flutter theme.

## Hard rules

- **Spend boldness in one place.** The signature element is the one memorable thing;
  everything around it calm and disciplined. "Take one accessory off before you leave."
- **Justification required.** Every colour/font/radius decision derives from
  `design-language.md` — no values "from the gut".
- **Defaults are forbidden, not merely ugly.** The slop checklist is a gate, not a
  suggestion. Where the brief *prescribes* a direction (even a "generic" one), the
  brief wins — but never fill free axes with defaults.
- **Quality floor without announcement:** responsive down to mobile, visible focus,
  `reduced-motion`/accessibility respected, contrast checked.
- **Motion sparingly.** One orchestrated moment beats scattered effects; too much
  animation *is* a slop signal.

## What this skill does NOT do
- No frame→widget translation (that is `figma-to-flutter`).
- No blind generation — the plan + critique happen **before** the first pixel.
