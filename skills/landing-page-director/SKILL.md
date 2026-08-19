---
name: landing-page-director
description: Build a distinctive, non-generic marketing/landing page grounded in a product's real brand facts, verified in a real browser. Use for a "beautiful"/"next level" product website, 'Landingpage erstellen', 'Website-Redesign', a launch page.
disable-model-invocation: true
metadata:
  argument-hint: "<product, page, or design goal>"
---

# Landing Page Director

Build a landing page the way a paid studio would for a client who has already rejected
templated pitches: one committed visual direction, grounded in the product's real brand
facts, verified in a real browser before it's called done. This skill does not replace
`frontend-design` — it sequences it correctly, adds a brand-facts gathering step so the
build starts from real constraints instead of invented ones, and adds a concrete
checklist for the specific patterns that make AI-built landing pages read as generated
rather than designed.

If this skill was invoked with an argument, that argument is the product/page/goal.
Otherwise, ask the user what surface this page is for before continuing.

## 1. Load the real design skill first — don't reinvent it

Before writing any markup, load Anthropic's own `frontend-design` skill
(`Skill(skill: "frontend-design:frontend-design")` if installed as a plugin here, or the
equivalent `frontend-design` skill if only the unscoped name is listed). That skill is
the authoritative source for typography pairing, color-token discipline, motion
restraint, and the brainstorm → critique → build → critique-again loop. This skill does
not restate it — it adds what that skill doesn't cover: brand-fact grounding, brief
structure, and a landing-page-specific anti-slop checklist.

## 2. Model tier: Fable for the creative passes, current tier for mechanical edits

Fable is this skill's default UI model for the creative build. Dispatch the actual
structural and creative passes (token system, layout, copy direction) through the
`Agent` tool with `model: "fable"` set explicitly, rather than building the page inline
on the current tier. Write the prompt as a self-contained brief per §4 — the subagent
has not seen this conversation.

If the brief is large (a full multi-section site, not one hero), consider asking for
extended/max effort in that one dispatch rather than splitting it into many small
follow-ups — one pass that covers the whole scope tends to hang together better, because
the model keeps one coherent token system in view the whole time. That fits best when
the scope and source of truth are already well-defined (a known brief, a reference to
match). For genuinely exploratory work — where the creative direction itself is still
being decided — a build-then-critique loop across several smaller passes tends to
converge better, because it leaves room to react to what actually got built instead of
pre-committing to a plan.

Once the creative direction is locked, drop back to the current tier for small
mechanical edits — nudging a spacing value, deleting a stray divider, adjusting one font
size. Paying premium-tier cost for that kind of edit is waste. (This Fable default is
this skill's own choice, not a rule inherited from the `escalate` skill's general table
— that table routes to `opus` for stakes/difficulty and doesn't cover model choice for
creative-direction work like this. Don't expect it to make this decision for you.)

## 3. Ground it in the product's actual brand facts, every time

Don't let the subagent invent brand identity — gather these fact *types* first and feed
them in, asking the user rather than guessing where the repo doesn't already answer them:

- **Display name.** How the product/brand is actually capitalized and written where a
  human reads it — this is often not identical to a lowercase package/repo identifier.
- **Mark/logo.** The actual source file (SVG or otherwise) if one exists — read it,
  don't approximate a gradient or shape from memory. If no mark exists yet, say so
  rather than inventing one inline.
- **Color source of truth.** Find the project's actual design tokens (a `theme.css`,
  a Tailwind config, a CSS custom-property block) and read them directly rather than
  trusting a written brand doc — token files drift faster than docs, and a stale doc
  describing a superseded rule is a common trap. If both exist and disagree, the token
  file wins; note the discrepancy to the user rather than silently picking one.
- **The one real differentiator.** What this product actually does that's true and
  specific, not generic SaaS positioning — a real mechanism, workflow, or capability,
  ideally with a real screenshot or mockup if one exists. This is what the hero should
  show or simulate; don't let it default to a generic device mockup, abstract blob
  illustration, or stock photo standing in for something real.
- **Tone.** How the brand actually talks — technical-confident, playful, enterprise,
  etc. — and any positioning constraints (e.g. tool-agnostic language that shouldn't
  imply an exclusive partnership that doesn't exist).

Mark anything genuinely unknown as unknown instead of letting the model invent stats,
testimonials, pricing, or metrics.

## 4. Brief structure that gets a non-generic result

Use this shape when writing the subagent prompt in §2:

1. **Goal** — exact page type and what it needs to accomplish (ship a first-look landing
   page for X, produce N genuinely different directions to choose between, etc).
2. **Context** — the brand facts from §3, audience, tone.
3. **Inputs** — real assets: the actual mark/logo file, actual copy fragments if any
   exist, actual screenshots of the product if any exist.
4. **Constraints** — brand rules that must hold (which colors are reserved for the mark
   vs. general UI, no invented metrics, self-contained file, no external requests beyond
   system fonts if the target is an Artifact).
5. **Process** — ask for the two-pass loop: brainstorm a compact token system (color,
   type, layout, one signature element) and self-critique it against generic-AI-design
   defaults (§5) before writing any code.
6. **Output format** — sections required (hero, feature highlights tied to real product
   truths, CTA, footer), and whether it's a standalone HTML file or an Artifact.
7. **Quality check** — see §5.
8. **Next action** — usually: produce 2–3 real directions, not variations on one theme,
   for the human to react to.

## 5. Quality check — concrete anti-slop list

Beyond what the loaded `frontend-design` skill already screens for (templated palettes,
generic type pairing, decorative-marker overuse, over-animation), check specifically for
patterns that read as generated rather than designed:

- **Decorative grid-line backgrounds** — a hairline hatch tiled by a fixed-pixel cell
  behind ordinary content is a recurring tell. Reserve it for content that's actually a
  blueprint/canvas/measurement surface; if the hero already carries a real grid motif
  (a dashboard, a table, a multi-pane layout), it doesn't need a decorative echo behind
  it too.
- **Purple gradient on a light/cream background** as the reflexive "modern SaaS" choice.
- **Numbered markers (01 / 02 / 03)** used as pure decoration where the content isn't
  actually an ordered sequence.
- **One accent color used everywhere** instead of a deliberate dominant + sharp-accent
  pairing.
- **Uniform, scattered micro-animation** on every element instead of one orchestrated
  moment (page load, or a scroll-driven sequence, chosen deliberately) plus restrained,
  purposeful micro-interactions elsewhere.
- **Decorative strokes/borders added by default** — an outline plus a fill on the same
  card, a divider rule between every section regardless of whether it's earning its
  keep. This is one of the most common things people end up asking the model to remove
  after a first draft — check for it as a matter of course rather than waiting to notice
  it.
- **Hierarchy drift** — a stat, badge, or secondary label sized or weighted so it
  competes with the actual headline or primary CTA for attention. Check explicitly:
  does anything on the page win the eye before the thing that's supposed to win it does?

If a background video or image reads as visibly pasted onto the page rather than part
of it, a CSS blend mode (`mix-blend-mode`, e.g. `exclude`/`multiply`/`screen` depending
on the asset) on top of the right base color is a concrete, cheap fix worth trying
before regenerating the asset itself.

## 6. Verify before calling it done

- Actually open the result in a browser (or render the Artifact) and look at it — don't
  approve from reading the markup. Scroll the whole page, trigger the hover/scroll
  states, check both light and dark if the surface supports it.
- Check `prefers-reduced-motion` is respected if the design leans on motion.
- Check responsive behavior down to a narrow viewport, not just desktop width.
- If publishing as a Claude Artifact, load `artifact-design` first as that tool
  requires, and give each variant a distinct favicon/title so they're easy to tell apart
  when the human compares them side by side.

## 7. Optional power-ups, once the basics are solid

These are worth reaching for when the brief calls for more than a well-designed static
page — none of them substitute for §1–§6, and a well-executed simple page beats a
power-up-laden generic one:

- **Reference imagery.** If the human has screenshots of sites or products they like the
  feel of, feeding those in as visual anchors narrows the direction far more reliably
  than describing taste in words. Treat gathering a handful of references (color,
  typography, one graphic motif — not necessarily all from the same source) as its own
  short, time-boxed step rather than skipping straight to prompting. Combining unrelated
  references into one new direction is the point — the goal is a synthesis, not a copy
  of any single source.
- **Matching a reference font by eye.** When a reference image implies a typeface but
  doesn't name one, a model reading the image alone often gets it wrong. Comparing the
  reference visually against a page of common free typefaces and picking the closest
  match by eye, then naming that font explicitly in the brief, is more reliable than
  asking the model to infer it from pixels.
- **Real product screenshots** in the hero instead of a stylized mockup, once the
  product has UI worth screenshotting.
- **AI-generated hero imagery** for illustration-heavy directions, when a literal
  product shot or mockup isn't the right hero device for that particular concept.
- **Existing component libraries** for polish details — check license and the project's
  `.ossallowlist` conventions before vendoring anything.
- **Competitor/reference-site research** to ground positioning claims in what's actually
  true relative to real alternatives, not assumed.

## Boundaries with other skills in this repo (don't duplicate these)

- **`frontend-design`** owns the actual design methodology (§1) — this skill sequences
  it and adds brand grounding, not a replacement.
- **`escalate`** owns general task-difficulty routing; this skill's §2 tiering is its
  own creative-direction call, not derived from `escalate`'s table.
- **`app-icon-director`** is for app icons specifically, not full pages.
- **`impeccable`** (if installed) is for app/product UI, not marketing/landing pages.
- **`dataviz`** / **`artifact-design`** / **`artifact-diagramming`** own chart, Artifact,
  and diagram fundamentals if the page (or a section of it) is published as an Artifact.
- **`motion-graphics-director`** is for standalone animated graphics from video content,
  not landing pages — a different output entirely, though it shares this skill's
  anti-slop instinct.
