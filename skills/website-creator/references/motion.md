# Motion tiers

The user picks one tier with the direction. Motion must explain something (state, order, cause), never just decorate. All tiers honor `prefers-reduced-motion: reduce` (the linter errors when a project animates without it).

## Restrained (default)

- CSS transitions on hover/focus (120–200ms) and entrance (300–500ms), `ease-out` or `cubic-bezier(0.2, 0.7, 0.2, 1)`.
- Scroll-driven reveal with `animation-timeline: view()` and `animation-range: entry 10% cover 30%`, guarded by `@supports (animation-timeline: view())`. Content is visible without it: animate from a small offset and partial opacity, never from `opacity: 0` with JS reveal (the render check reports content hidden at rest).
- Animate only `transform` and `opacity`. No `transition: all`.

## Signature moment

One place on the page carries a memorable piece of motion; everything else stays restrained.

- **GSAP + ScrollTrigger** (free incl. plugins since 2025): pinned section with scrubbed steps, product UI assembling, text scrub. Load from the project's package manager; register plugins once; `matchMedia` for reduced motion and for mobile simplification; `ScrollTrigger.refresh()` after fonts load.
- **Shader / canvas**: a single WebGL or 2D canvas background that reacts to scroll or pointer; cap DPR at 2, pause offscreen (`IntersectionObserver`), static fallback image.
- **Three.js**: only when the product has a real 3D subject. Lazy-load, poster image first, under 500 KB of JS for the scene.
- Budget: the moment must not delay LCP; measure with the render check at 375px.

## Video (HyperFrames)

A rendered product video carries the story (HyperFrames: HTML/CSS/GSAP compositions rendered to MP4, `npx hyperframes`; Puppeteer is allowed only there).

- 20–60s, no voice required, captions burned in or as WebVTT, first frame meaningful as a poster.
- On the page: `<video muted playsinline loop preload="metadata" poster=…>` with AV1/H.264 sources; autoplay only muted and only when in view; reduced motion shows the poster plus a play button.
- Page motion otherwise minimal so the video is the event.

## Never

Bounce/elastic easing, pulsing status dots without real status, typing-cursor heroes, marquees of logos, parallax on body text, scroll hijacking, animation on every section.
