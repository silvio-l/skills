# Video, 3D and product demo

The three expressive centerpieces from `references/centerpiece.md`, with the technical limits they ship under. They are the preferred way to make a page lively: one of them replaces several explanatory sections. Each limit marked **hard** holds for every direction, the radical one included; the size budgets may be loosened by the radical direction if the report says so and by how much.

## Product demo

Chosen per project:

1. **Default: a rebuilt interactive slice** of the real UI in the page's own code: real tokens, real labels, three to six real states, View Transitions between them. It loops as a self-demo when idle and hands control to the visitor on the first click or hover.
2. **Embedded live demo** only when the product has a public demo instance meant for strangers (no login, no personal data, resettable). Embed it in an `<iframe>` with `sandbox` (only the flags it needs), `loading="lazy"` and a poster screenshot until the visitor activates it; never embed a production account.
3. Neither fits (hardware, B2B back office): a scrubbed or looping video of the real flow (see Video).

Rules:

- The demo shows only what the product really does; states and numbers come from the implementation, demo data is clean and plausible.
- Every control inside it is a real button or input with a `data-testid` and keyboard access; the self-demo stops for good on the first interaction and has a visible pause control (WCAG 2.2.2).
- Copy around the demo labels what it shows instead of explaining it again (`TASTE.md`).
- Budget: the rebuilt slice adds at most about 60 KB of compressed JS; the embed loads only after activation.
- **Hard:** CSP `frame-src` lists exactly the demo origin; no `allow-same-origin` together with `allow-scripts` for third-party content you do not control.

## Video

- **Format.** 6–20 s loops for a hero field, 20–60 s for a story film (HyperFrames, `references/motion.md`). AV1 (or VP9) plus H.264 fallback, 1080p max for full-bleed desktop, a separate portrait encode for mobile, no audio track on autoplay clips.
- **Loading.** `<video muted playsinline loop preload="metadata" poster=…>` with explicit `width`/`height`; start playing only when in view (`IntersectionObserver`), pause when out of view. The poster is the LCP candidate and is meaningful on its own.
- **Budget.** Hero loop under about 2.5 MB on mobile and 6 MB on desktop; story film streamed, never inlined. The radical direction may go further and states the size in the report.
- **Accessibility.** Captions as WebVTT or burned in when there is speech or on-screen text that matters; a visible pause control for anything that runs longer than five seconds.
- **Reduced motion (hard).** Show the poster plus a play button, no autoplay.
- **CSP (hard).** Videos are self-hosted or from one named media origin in `media-src`; no third-party player scripts for a decorative loop (YouTube/Vimeo embeds only for a real story film, behind a click-to-load poster for privacy).

## 3D

- **When.** Something can be turned, inspected, assembled, or its material matters. A floating abstract blob is not a reason.
- **Asset.** glTF/GLB with Draco or Meshopt compression and KTX2 textures; one model, under about 1.5 MB compressed (radical direction: say how much more).
- **Code.** Three.js (or the project's existing engine) loaded as a module only when the stage nears the viewport; scene JS under about 500 KB compressed. Poster image first, swapped for the canvas when the first frame is drawn.
- **Runtime.** DPR capped at 2, render on demand or pause offscreen and in background tabs, no shadows or post-processing on low-power devices (`navigator.hardwareConcurrency`, `matchMedia("(pointer: coarse)")`), a fixed frame budget (drop effects before frames).
- **Interaction.** Drag or scroll to turn, with a reset; the page must stay scrollable on touch (no full-viewport canvas that captures vertical swipes).
- **Fallback (hard).** No WebGL, a failed load or reduced motion shows the poster or a short video, never an empty box.
- **CSP (hard).** No `unsafe-eval`; decoders that need WebAssembly get `'wasm-unsafe-eval'` only, workers from `'self'` or `blob:` only when the decoder needs it, models and textures from `'self'`.

## Every centerpiece

- It must not delay LCP or reading: the first viewport is readable before any of it has loaded. Measure with the render check at 375 px.
- No layout shift when the poster is replaced (fixed aspect ratio).
- One heavy centerpiece per page; further moments are light (sliders, toggles, counters, small loops).
- Measured numbers (file sizes, JS weight) go into the report; a loosened budget is named there with the reason.
