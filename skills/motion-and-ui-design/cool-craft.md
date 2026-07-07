# Cool Craft: The Anti-Generic Execution Loop

Knowing that "design system first" matters is not the same as being able to produce something that doesn't look like every other AI-generated site or app. This doc is the operational layer: the specific tells that give away generic AI output, a mandatory direction-first gate, a library of named aesthetic directions with concrete recipes, a checklist to critique against, and — the actual differentiator — a visual self-verify loop. Without that loop, an agent building a UI is working blind: it never sees what it produced, so it can't catch that the output is the same purple-gradient, four-card-grid median everyone else gets.

This doc is deliberately self-contained — usable without any other skill installed — but composes with `impeccable` and `frontend-design` for deeper taste work, and aligns with (does not duplicate) the phase-0 gate in `flutter-design-language`, which owns the equivalent discipline for the Flutter/Figma pipeline specifically.

## The generic tells (what gives away AI-built design)

Every one of these is a *default*, not a *choice* — the model reaching for the median of its training data because nothing forced it to commit to something specific.

| Tell | Do instead |
|---|---|
| Purple/indigo gradient hero | Pick a palette that comes from the subject, not from "what AI defaults to." See the direction library below. |
| Inter, Roboto, Poppins, Open Sans, Lato, or system-default sans everywhere | Pair a characterful **Display** face with a calm **Body** face — see `flutter-design-language`'s font allow-list for concrete names. Never let any single face become *your* new unreflective default either — rotate through the allow-list by direction. |
| Four identical cards in a grid | An asymmetric bento arrangement with one dominant cell — see the Bento pattern in [patterns.md](patterns.md). |
| Faint or missing hover/focus states | Full state coverage — hover, focus, active, disabled, loading, empty — each with a real, felt transition, not a 5% opacity nudge. |
| Hard-coded hex values scattered through markup | A token layer first — see the Token Starter in [patterns.md](patterns.md). |
| Carousels with no narrative reason to exist | Cut it, or replace with a sequence that has an actual order (a process, a timeline, a story). |
| App UI built entirely from stacked cards | Vary the structure — lists, a hero stat, a timeline, a map, a single focal chart — instead of defaulting to "everything is a card." |
| Ad hoc, per-component spacing decisions | Spacing pulled from one declared scale, every time. |

## Gate 0: commit to a direction before writing a line of code

This is the single largest lever against slop, and it costs one sentence. Before building anything — a landing page, a prototype, a motion graphic — name **one** aesthetic direction and **why** it fits the subject. Not "clean and modern" (that's not a direction, that's the absence of one). Pick from the library below or name your own, but name it explicitly and state the reason before generating anything.

## Direction library

Each direction is a starting recipe, not a cage — adapt it to the actual subject. The point of naming one is to stop the model from defaulting.

| Direction | Typography character | Color strategy | Layout signature | Motion signature | Use when |
|---|---|---|---|---|---|
| **Editorial** | Large serif or high-contrast display face for headlines, restrained sans body | Near-monochrome with one accent used sparingly | Generous whitespace, asymmetric text columns, pull quotes as graphic elements | Slow fades, text reveals tied to scroll position | Content-heavy sites, publications, thought-leadership brands |
| **Brutalist** | Raw, unstyled system-adjacent type used *deliberately* — the rawness is the point | High-contrast black/white plus one jarring accent | Visible grid lines, deliberately "unfinished" alignment, oversized borders | Abrupt state changes, no easing — motion that feels mechanical on purpose | Tech-forward, developer tools, brands that want to signal "we don't do corporate polish" |
| **Retro-futuristic** | Geometric/technical display face, monospace accents for data | Saturated duotones (e.g. deep purple + neon cyan), gradient meshes | Angled sections, glow/scanline motifs, chrome or glass surfaces | Glitch transitions, scanline sweeps, pulsing glows | Gaming, crypto/web3, music, anything explicitly nostalgic-future |
| **Maximalist** | Multiple display faces mixed deliberately, oversized headline scale | Saturated, high-count palette used with intent (not randomly) | Dense layouts, overlapping elements, layered z-index | Staggered, playful, slightly chaotic reveal timing | Fashion, entertainment, youth brands, portfolios |
| **Refined-minimal (Swiss)** | One neutral grotesque or humanist sans, tight type scale, heavy reliance on weight contrast | Near-monochrome, one restrained accent, lots of negative space | Strict grid, generous margins, alignment as the main visual device | Minimal, purposeful — motion only on state change, never decorative | B2B SaaS, professional tools, anything where credibility > excitement |
| **Organic-warm** | Rounded, humanist type; hand-drawn or soft accents | Warm neutrals plus one saturated accent, natural gradients | Soft shapes, rounded containers, asymmetric but friendly | Gentle spring easing, bounce on interaction | Consumer wellness, community products, anything wanting to feel approachable |
| **Technical/data** | Monospace or grotesque for data, clean sans for narrative text | Cool neutrals, semantic color reserved strictly for status (never decoration) | Dense information hierarchy, dashboards, tabular structure | Fast, purposeful, tied to real state changes (loading, updated, error) | Analytics products, dev tools, anything data-forward |

## Litmus checks (run before calling anything done)

- **The "would I land here by default?" test.** For every non-obvious choice — palette, type pairing, layout — ask: would this be the output on *any* similar brief? If yes, it's a default, not a choice. Revise and name what changed.
- **One visual anchor per screen.** If nothing draws the eye first, nothing was actually designed — it was assembled.
- **Motion earns its place.** Every animation should be answerable with "this exists because ___." If the answer is "it looks nice," it's decoration, not design.
- **State completeness.** Hover, focus, active, disabled, loading, empty — accounted for, not just the happy path.
- **Real typographic contrast.** Display and body faces should read as a deliberate pairing, not "two fonts that happened to both be installed."
- **Spacing from a scale.** Every gap traces back to the declared spacing scale, not an eyeballed value.

## The visual self-verify loop (the actual capability)

This is what turns "described a design" into "built a good one." An agent that never looks at its own output is working blind — it cannot tell a purple-gradient default from a deliberate choice, because it never rendered either.

1. **Build** the artifact (landing page, prototype section, motion graphic) per the chosen direction and the token layer.
2. **Render and look at it** — for a code artifact built with the `Artifact` tool, view the rendered output; for anything driven through a browser, screenshot it (`mcp__claude-in-chrome__computer` with a `screenshot` action, or the equivalent capture step already used by `screenshot-review`/`ratchet-up`'s visual-QA tiers).
3. **Critique against the tells table and the litmus checks above** — explicitly, in writing, before touching the code again. Name what's generic, name what's missing a state, name what has no anchor.
4. **Iterate** — fix what the critique surfaced. One or two passes is normal; more than that usually means the direction wasn't committed to strongly enough in step 1, not that the execution needs more polish.
5. **Escalate for depth, not for a first pass.** Once the loop has produced something coherent, hand it to `impeccable` or `frontend-design` if the task warrants deeper taste work than this loop covers (complex information architecture, a full design system, an unusually demanding brief) — don't skip straight there before ever looking at what was built.

## Web vs. app craft split

The loop above is the same in both cases; what "cool" means differs:

- **Web** leans on art direction and storytelling — scroll-tied motion, large expressive typography, a landing page that reads as a sequence with a beginning and an end. Awwwards-caliber sites treat the whole page as one authored experience, not a stack of interchangeable sections.
- **App** leans on microinteraction polish — the gap between an "OK" app and an exceptional one is almost entirely in the small, felt details: a button that responds to touch, a toggle with real physicality, a loading state with personality instead of a generic spinner. One clear visual anchor per screen (not per page — screens are smaller and get one shot at it), and adherence to the platform's own material language (HIG/Liquid Glass, Material) rather than a ported web aesthetic. See the web→app adaptation table in [modern-design.md](modern-design.md) for the underlying interaction-model differences this is built on.

For concrete, copy-paste starting code for any of the patterns referenced above (tokens, bento grids, staggered reveals, microinteractions), see [patterns.md](patterns.md).
