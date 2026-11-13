# Liveliness: micro-interactions and craft

A page that only fades in feels dead. Every direction gets this baseline of tactile response, independent of its motion tier; the tier decides only how big the *centerpiece* is (`references/centerpiece.md`). All of it is wrapped in `prefers-reduced-motion` (reduced: state changes stay, travel and scale go).

## Baseline every page ships

- **Press.** Buttons and clickable cards compress on `:active` (scale about 0.96–0.98, 80–120 ms) and release on a slightly slower curve. A button that does not react to a press feels broken on touch.
- **Hover with direction.** Hover moves something toward the pointer's intent: an arrow slides 2–4 px forward, a card rises 2–4 px with a deeper shadow, a photo inside a frame scales to about 1.02–1.04 while the frame stays put, an underline draws from left to right. Never a bare color swap only.
- **Entry from somewhere.** Elements enter from a small offset and partial opacity, or from scale 0.92–0.96 — never from nothing (`scale(0)`, `opacity: 0` behind a JS gate). One entrance per container, not per child.
- **Orchestrated load.** The first viewport arrives as one sequence (headline, then proof, then action), not as a dozen independent fade-ups. Stagger unevenly: the most important item first, gaps of 30–80 ms that grow slightly, some items in parallel. A metronome stagger reads as generated.
- **Small numbers that read as care.** Hover responses 150–200 ms with travel under about 2 px for text-sized elements; reveal travel 8–16 px; press feedback lands within 50–100 ms. Stagger at most about eight children, then reveal the rest as one group.
- **Words as an entrance.** A tagline or key claim may reveal word by word, each word starting at 25–35 % opacity rather than invisible, so the line is readable at every moment.
- **Living objects.** Product mockups, counters, small diagrams loop quietly while in view (a cursor completes a task, a number ticks, a status changes; 2.5–4 s per loop, pause offscreen).
- **Motion claimed, motion shown.** If the copy says "in Echtzeit", "automatisch", "synchronisiert", the page shows it happening. A claim about movement next to a static screenshot is a broken promise.

## Curves and springs

- Default deceleration: a strong ease-out such as `cubic-bezier(0.22, 1, 0.36, 1)` for entrances, a shorter ease-in-out for things that move between two states on screen.
- Springs give weight. In CSS, express them as a `linear(...)` easing generated from a spring (stiffness/damping), or use the Motion library's spring when JS is already there. Name the character in DESIGN.md instead of raw numbers: *snap* (fast, no overshoot: toggles, tabs), *settle* (slight overshoot: cards, sheets), *float* (slow, soft: decorative drift), *pop* (quick overshoot: badges, confirmations).
- Overshoot scales inversely with area: small controls may overshoot noticeably (around 10–20 %), large surfaces barely (1–2 %). A full-width section never bounces.
- Durations: feedback 80–150 ms, small moves 150–250 ms, entrances 300–600 ms. Marketing moments may run longer than product UI because they happen once.
- Split the properties: opacity and color change on a curve, position and scale move on a spring. On small screens run everything 20–30 % shorter — the distances are shorter too.

## Modern platform tools (with fallbacks)

- **View Transitions** for state changes inside a demo (tab, filter, detail view) and between pages of a multi-page site.
- **Scroll-driven animations** (`animation-timeline: view()` / `scroll()`) for reveals and progress, guarded by `@supports`.
- **`@property`** to animate custom properties: gradient angles, color stops, counters.
- **Pointer coupling**: tilt, magnetic buttons or light that follows the cursor — on one element, damped by a spring, off on touch devices.

## Restraint that still applies

- Animate `transform`, `opacity`, `filter` and registered custom properties; never layout properties, never `transition: all`. Blur at most about 8 px and only as a one-off transition, never looping.
- No scroll listeners that write styles or `scrollTop` on every event; use scroll-driven animations or ScrollTrigger.
- Frequent product actions stay fast; delight belongs to rare and first-time moments.
- Nothing blocks reading or the main action; nothing loops in the reader's peripheral vision while they read body text.
