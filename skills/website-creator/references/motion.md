# Motion tiers

The user picks one tier with the direction. The tier sets the size of the **centerpiece** (`references/centerpiece.md`); the tactile baseline from `references/liveliness.md` (press, hover, orchestrated load, living objects) ships with every tier. Motion explains something or gives the page character and weight; it never delays reading or the main action. All tiers honor `prefers-reduced-motion: reduce` (the linter errors when a project animates without it).

## Restrained

For pages in Operate or Read mode (`references/looks.md`), or when the user asks for calm.

- Liveliness baseline plus CSS transitions on hover/focus (120–200 ms) and entrance (300–600 ms), strong ease-out such as `cubic-bezier(0.22, 1, 0.36, 1)`.
- Scroll-driven reveal with `animation-timeline: view()` and `animation-range: entry 10% cover 30%`, guarded by `@supports (animation-timeline: view())`. Content is visible without it: animate from a small offset and partial opacity, never from `opacity: 0` with JS reveal (the render check reports content hidden at rest).

## Signature moment (default for landing and marketing pages)

One loud center carries the page; the rest supports it. Pick from the top of this list down: what the visitor can **touch or watch** beats what unfolds while they scroll. Limits for video, 3D and demos: `references/media.md`.

1. **Playable demo**: a rebuilt slice of the product UI with real states, View Transitions between them, a looping self-demo when idle. A strong variant is the *live re-skin*: one control swaps theme, density or content, and the same UI re-renders in place, so the visitor feels the product's range instead of reading about it.
2. **Three.js / real-time 3D**: whenever something can be turned, inspected or assembled, or material matters (glass, metal, physics).
3. **Video loop as hero field**: a 6–20 s muted loop of the real thing or of a generated world.
4. **Shader / canvas**: a WebGL or 2D canvas field (gradient mesh, caustics, grain, particles) that reacts to pointer or scroll; cap DPR at 2, pause offscreen (`IntersectionObserver`), static fallback image.
5. **Living objects at hero scale**: the product mockup works by itself (a task completes, numbers move, a status changes) — the baseline from `references/liveliness.md`, made big.

### Scroll storytelling (optional, sparingly)

Only when the product really has a sequence the reader must follow in order, and never as the only centerpiece. At most one pinned or scrubbed story per page, with a storyboard first (step by step: what the visitor sees, what changes). The page works when the reader skims past it.

- **GSAP + ScrollTrigger** (free incl. plugins since 2025): pinned section with scrubbed steps, product UI assembling. Load from the project's package manager; register plugins once; `matchMedia` for reduced motion and for mobile simplification; `ScrollTrigger.refresh()` after fonts load.
  - Groups of reveals: `ScrollTrigger.batch` instead of one trigger per element.
  - Horizontal run inside vertical scroll: pin the wrapper, tween the track with `ease: "none"`, and hang inner triggers on it via `containerAnimation`.
  - A trigger either scrubs or uses `toggleActions`, never both; put ScrollTrigger on the top-level tween or timeline, never on a child tween.
  - Pointer followers via `gsap.quickTo` (about 0.4 s, `power3`), not a new tween per mousemove.
  - Create everything inside `gsap.context()` or `gsap.matchMedia()` and revert it on cleanup, so route changes and hot reloads leave no orphaned triggers.
- **Scroll journey**: the camera travels through one world in four to six stages, driven by pinned, scrubbed video, an image sequence on canvas, or a Three.js scene. Every stage has a readable headline and a poster frame. Mobile gets its own portrait clips or framing, never a crop of the desktop footage. Scrub follows the reader's input and never snaps against it. Generated clips are generated imagery (`references/images.md`).

Budget: the moment must not delay LCP; measure with the render check at 375px. The radical direction may exceed size budgets and states it in the report; WCAG AA, the strict CSP and reduced motion stay hard limits (`references/media.md`).

## Video (HyperFrames)

A rendered product video carries the story (HyperFrames: HTML/CSS/GSAP compositions rendered to MP4, `npx hyperframes`; Puppeteer is allowed only there).

- 20–60 s, no voice required, captions burned in or as WebVTT, first frame meaningful as a poster.
- On the page: per `references/media.md` (poster, `preload="metadata"`, AV1/H.264, muted autoplay only in view, size budget, `media-src` in the CSP, poster plus play button under reduced motion).
- The video is the event; the liveliness baseline stays, other large motion steps back.

## Accessibility of motion

- Anything that moves on its own for more than five seconds (loops, carousels, background video, self-demos) gets a visible pause control (WCAG 2.2.2) or stops by itself.
- Nothing flashes more than three times per second.
- View Transitions do not respect reduced motion by themselves: add `@media (prefers-reduced-motion: reduce) { ::view-transition-group(*) { animation: none; } }` or skip `startViewTransition` there.
- Carousels: previous/next buttons, pause, keyboard access, and a static first slide under reduced motion.

## Never

- Bounce or elastic on large surfaces (springs with small overshoot on small controls are fine, see `references/liveliness.md`).
- Pulsing status dots without real status, typing-cursor heroes, logo marquees of unrelated companies.
- Parallax on body text, scroll hijacking (changing scroll speed or snapping the reader against their input).
- The same entrance animation on every section.
- A scroll story where a demo, a 3D object or a loop would show the same thing directly.
- Glow pulses on the CTA, neon edges, shimmer sweeps across buttons or text.
