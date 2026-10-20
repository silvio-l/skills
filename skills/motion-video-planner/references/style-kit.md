# Style kit

Load this in phase C (choosing a look per concept) and in phase D (writing section 4, Look, and
the motion and transition columns). A style name alone never goes into a prompt. Translate the
chosen style into the concrete rules below, then adapt them to the brand.

## How to use a style

1. **The brand constrains the style.** Brand colors, fonts, logo, and do's and don'ts stay exact.
   The style contributes texture, shape language, layout grammar, motion character, transitions,
   and sound design. If a style's signature palette conflicts with the brand (Neon Glow for a
   pastel brand), keep the style's *behaviour* (glow on accents) and map it onto brand colors,
   or pick another style.
2. **One dominant style, at most one accent style.** Combine only when there is a
   storytelling logic, and say what it is:
   - **Era coherence**: Retro VHS + Pixel Art, or Neon Glow + Retro VHS (an 80s/90s world).
   - **Transformation as story**: Blueprint → Isometric or Clay 3D ("plan becomes real");
     Neo-Brutalism → Swiss ("chaos becomes order", for before/after product pieces).
   - **Layer separation**: Kinetic Typography over any graphic style, if the type follows the
     brand fonts and the dominant style's motion character.
   - **Material accent**: Swiss/Editorial + one Liquid Morph or Particles moment for the climax.

   Avoid combinations without a logic: Glassmorphism + Comic Book, Art Deco + Pixel Art, three or
   more styles, or a different style per scene.
3. **The recurring element lives in the style.** It is rendered in the dominant style every time
   it appears.
4. **Write the style into the prompt as rules**: palette roles with hex values, type families
   with weights and sizes, line weights, texture parameters, ease names and durations, transition
   names, and the audio palette.

Effort scale (HyperFrames, one 30 s piece): **S** = GSAP/CSS/SVG only; **M** = custom SVG or canvas
work, registry blocks, or media effects; **L** = Three.js, shader work, generated art, or many
bespoke assets.

Implementation hints name candidate techniques. The executing agent verifies block and effect
names with `npx hyperframes catalog --query …` and `npx hyperframes media-treatment --capabilities --json`.

---

## Swiss / Editorial

- **Fits**: B2B, finance, productivity, data-heavy explainers, premium brands. **Avoid** for kids
  or party energy.
- **Imagery**: a strict grid (for example 12 columns, 64 px gutters at 1080p); asymmetric
  composition; generous negative space; flat color fields; one accent color; rules and hairlines
  (1–2 px) as structure; real photography or UI in clean rectangular crops.
- **Typography**: a neo-grotesque or the brand sans; strong size contrast (display at about 1/10
  of frame width vs. labels at about 2.5 %); tight leading on display (0.9–1.0); flush-left,
  ragged-right; numbers as hero elements.
- **Motion**: precise and confident; `power3.out` / `power4.out` entrances at 0.35–0.5 s; elements
  slide along grid lines; masks wipe text in; no bounce; overlap offsets of about 0.06–0.1 s.
- **Transitions**: grid-based pushes and wipes (`transitions-push`, `transitions-grid`); match cuts
  on shared rules or lines.
- **Audio**: a minimal electronic bed; dry clicks and ticks on reveals; a confident voiceover.
- **Effort**: S.
- **HyperFrames**: GSAP, clip-path masks, SVG lines; `data-chart` for honest charts.
- **Typical failures**: centered everything; too many accent colors; decorative grid backgrounds
  with no structural role; timid type sizes.

## Kinetic Typography

- **Fits**: hooks, quotes, claims, social clips, sound-off viewing, explainers without footage.
  **Avoid** when the message needs product visuals to be believed.
- **Imagery**: type *is* the image; 1–2 type families; words as objects with mass; color blocks
  behind key words; occasional icon substitution for nouns.
- **Typography**: heavy display weights (700–900) or condensed caps for impact; sizes vary by
  meaning (the stressed word is 2–4× bigger); line breaks set exactly (`/` in copy).
- **Motion**: word-by-word or phrase-by-phrase timed to speech or beat; slams (`expo.out`, 0.2–0.3 s)
  for emphasis, glides (`power2.out`) for connective words; words push each other away
  (cause and effect); one oversized "landing" word per beat.
- **Transitions**: type-driven (the last word scales up to fill the frame and becomes the next
  background; letter-mask wipes); hard cuts on the beat.
- **Audio**: rhythm-driven music or voiceover; a hit on every stressed word, but not on every word.
- **Effort**: S–M.
- **HyperFrames**: GSAP with SplitText-style per-word spans; `hyperframes-animation` has named
  text-animation effects (check the catalog).
- **Typical failures**: every word animated the same way; reading time too short; text drifting
  into safe areas; more than 7 words on screen at once on mobile.

## Particles

- **Fits**: tech, AI, data, transformations ("chaos to order"), logo reveals. **Avoid** when
  overused as generic "tech" decoration.
- **Imagery**: thousands of small points or glyphs forming and dissolving shapes; dark ground
  with luminous particles, or the brand ground with ink particles; depth through size and blur.
- **Typography**: clean sans, minimal; text assembles from or dissolves into particles once, at
  the climax.
- **Motion**: flocking or flow-field drift → convergence on a target shape (`power2.inOut`,
  1–2 s) → a short burst on impact; **seeded** randomness only.
- **Transitions**: particles of scene A become scene B's shape; dissolve into a particle burst.
- **Audio**: granular shimmer, risers on convergence, a sub-bass hit on the formed shape.
- **Effort**: M–L.
- **HyperFrames**: canvas or WebGL with a seeded PRNG; `code-particle-assemble`; keep particles
  *behind* text (otherwise `check` flags `text_occluded`).
- **Typical failures**: unseeded randomness (renders differ); particles with no target meaning;
  performance-heavy counts; particles covering text.

## Liquid Morph

- **Fits**: consumer apps, wellness, creativity tools, fluid transformations, premium playful
  brands. **Avoid** for serious compliance content.
- **Imagery**: blobs and organic shapes in brand colors; one shape continuously becoming the next
  (a button becomes a drop becomes a logo); soft gradients inside shapes; gooey merging.
- **Typography**: rounded or humanist sans; text sits on or inside blobs; restrained sizes.
- **Motion**: continuous morphing with `sine.inOut` / `power2.inOut`; squash and stretch;
  overshoot on settle (`back.out(1.4)`); nothing teleports.
- **Transitions**: morph cuts (a shape grows to fill the frame, becoming the next ground);
  `cross-warp-morph`.
- **Audio**: soft bloops and drips, a warm pad, mallets.
- **Effort**: M.
- **HyperFrames**: SVG path morphs (the keyframes skill covers SVG morph), `vfx-liquid-background`,
  CSS gooey filters.
- **Typical failures**: morphs between shapes with different point counts that tear; purposeless
  lava-lamp backgrounds; low contrast text on blobs.

## Holographic

- **Fits**: futuristic tech, AR/VR, premium gadgets, sci-fi-flavored launches. **Avoid** for warm,
  human topics.
- **Imagery**: iridescent gradients (cyan–magenta–lime shifts) on surfaces; scanline shimmer;
  translucent projected UI panels; light-catch sweeps; dark ground.
- **Typography**: thin or medium geometric sans, wide tracking (+5–10 %), all caps for labels.
- **Motion**: panels materialize via scan reveal (a line sweeps, the content appears behind it);
  slow parallax; iridescence shifts with angle or time (slow, 3–6 s cycles).
- **Transitions**: light sweeps, `chromatic-radial-split` sparingly, scan wipes.
- **Audio**: airy synth pads, digital chirps, a soft sweep on each reveal.
- **Effort**: M–L.
- **HyperFrames**: CSS conic/linear gradients with animated hue rotation, blend modes, Three.js
  for a real 3D hologram.
- **Typical failures**: rainbow overload burying the brand colors; unreadable thin text on
  shimmering grounds; too many glitch accents.

## Neon Glow

- **Fits**: gaming, nightlife, events, music, retro-futurism, bold social clips. **Avoid** for
  daylight and calm brands.
- **Imagery**: dark ground (near-black, not pure #000, for example `#0b0b14`); 1–3 neon colors
  mapped to the brand; tube-like strokes with bloom; reflections on wet floors; signage.
- **Typography**: monoline script or outline fonts for signs; a bold sans for messages.
- **Motion**: flicker-on ignition (2–3 stutters, then a stable glow); buzzing idle (1–2 %
  intensity); pulse on beat.
- **Transitions**: power-off/power-on, `flash-through-white` on the drop, `light-leak`.
- **Audio**: synthwave or electronic; electric buzz and ignition SFX.
- **Effort**: S–M.
- **HyperFrames**: CSS `drop-shadow` / `text-shadow` stacks or the Bloom effect (expensive);
  seeded flicker.
- **Typical failures**: glow so heavy that text blooms out; too many colors; flicker that reads
  as a render bug; contrast check failures.

## Wireframe 3D

- **Fits**: engineering, hardware, architecture, technical products, "under the hood" explainers.
  **Avoid** for emotional consumer stories.
- **Imagery**: line-only 3D models (1–2 px edges), dark or paper ground, a single accent for
  highlighted parts, measurement lines, exploded views.
- **Typography**: monospace or technical sans for labels; callout lines to parts.
- **Motion**: slow camera orbits (`sine.inOut`, 4–8 s); parts explode and reassemble; edges draw on.
- **Transitions**: camera fly-throughs between objects; wireframe → solid shading as a reveal.
- **Audio**: precise mechanical clicks, a subtle drone, servo whirs.
- **Effort**: L.
- **HyperFrames**: Three.js via the adapter (`EdgesGeometry` / line materials); a 3D model file
  is needed, or simple geometry built in code.
- **Typical failures**: CSS-perspective fake 3D (reads flat); too many lines (moiré at 1080p);
  orbit speed causing judder.

## Glassmorphism

- **Fits**: modern apps and OS-like UI, fintech, product UI showcases. **Avoid** when the brand
  is flat and graphic (it clashes), or on busy grounds.
- **Imagery**: frosted translucent panels (background blur 20–40 px, white at 10–20 % opacity,
  a 1 px border at 25–40 % white); a colorful soft gradient or blurred shapes behind; soft
  shadows.
- **Typography**: clean sans (system-UI-like), medium weights, high contrast on panels.
- **Motion**: panels float in layers with parallax; gentle `power2.out` rises (0.5–0.7 s); specular
  highlight sweeps across glass.
- **Transitions**: panels slide past the camera; depth push-through (`transitions-blur`).
- **Audio**: soft UI ticks, airy pads.
- **Effort**: M.
- **HyperFrames**: CSS `backdrop-filter` (costly, so limit the number of panels); the liquid-glass
  VFX in the registry (check the catalog).
- **Typical failures**: low contrast text on glass; blur on everything (mud); render time spikes.

## Isometric

- **Fits**: processes, systems, workflows, SaaS architecture, "how it works" explainers, small
  worlds. **Avoid** when emotional closeness to people is the point.
- **Imagery**: a 30° isometric grid; flat-shaded blocks with three tones per color (top, left,
  right); tiny worlds on a plinth; a consistent light direction.
- **Typography**: geometric sans; labels on flat callout tags, not skewed text.
- **Motion**: blocks pop up from the grid (`back.out(1.6)`); objects travel along isometric
  paths; chain reactions from block to block.
- **Transitions**: zoom into one block, which becomes the next scene's world; camera pans along
  the grid.
- **Audio**: playful plinks, mechanical clacks, marimba.
- **Effort**: M.
- **HyperFrames**: SVG with isometric transforms built in code; Three.js with an orthographic
  camera for real depth.
- **Typical failures**: mixed angles; inconsistent light sides; overly detailed worlds that read
  as clutter at mobile size.

## Clay 3D

- **Fits**: friendly consumer apps, kids, food, playful explainers, mascots. **Avoid** for
  high-end luxury (unless deliberate) and for dense data.
- **Imagery**: soft rounded forms, matte material with subtle fingerprints or bumps, pastel or
  saturated brand colors, soft contact shadows, studio lighting.
- **Typography**: rounded bold sans; text as plump 3D letters only for the lockup.
- **Motion**: squash and stretch, bouncy settles (`back.out(2)`, `elastic.out(1, 0.5)` on
  landings); stop-motion feel optional (stepped poses on a two-frame hold, quantized on the frame
  index).
- **Transitions**: objects squish into the next shape; the camera pushes into a clay hole.
- **Audio**: squishes, pops, boings, light acoustic instruments.
- **Effort**: L (Three.js materials, or generated stills animated as layers).
- **HyperFrames**: Three.js via the adapter with soft materials; or generate clay stills via
  `/media-use` (costs; budget it) and animate them in layers.
- **Typical failures**: plastic-shiny materials instead of matte; uncanny mascots; generated
  assets that are inconsistent across shots.

## ASCII Art

- **Fits**: developer tools, CLI products, hacker culture, retro-computing, nerdy humor. **Avoid**
  for non-technical audiences without context.
- **Imagery**: monospace character grids form images; a terminal-green or brand-colored ink on
  a dark ground; density ramps (` .:-=+*#%@`); real terminal output.
- **Typography**: one monospace family throughout; a fixed cell grid.
- **Motion**: characters cascade and resolve into images; typing cursors; the grid updates in
  steps (no subpixel motion).
- **Transitions**: an image dissolves into characters and re-forms; a scroll-off like terminal
  output.
- **Audio**: keyboard clacks, beeps, chiptune or a lo-fi bed.
- **Effort**: S–M.
- **HyperFrames**: code-drawn character grids; the ASCII media effect on image or video layers;
  `code-typing` for terminals.
- **Typical failures**: characters too small to resolve at 1080p mobile; non-monospace fallback
  fonts breaking the grid; unreadable density.

## Gradient Mesh

- **Fits**: modern brands, SaaS hero moments, calm premium pieces, backgrounds for typography.
  **Avoid** as a lazy default ("AI purple-blue gradient").
- **Imagery**: smooth multi-point gradients from **brand colors only**; slow-moving color fields;
  subtle grain (1–3 %) against banding.
- **Typography**: bold or elegant type over a calm field; contrast is verified per frame.
- **Motion**: very slow mesh drift (10–20 s cycles); a color shift as the emotional beat;
  foreground elements carry the action.
- **Transitions**: color-field crossfades (`cross-warp-morph`); the gradient flows into the next
  palette.
- **Audio**: warm pads, soft piano or ambient.
- **Effort**: S–M.
- **HyperFrames**: CSS gradients or canvas animated by GSAP; `vfx-liquid-background`; add grain.
- **Typical failures**: generic purple-blue gradients unrelated to the brand; banding after
  compression; a pretty background with nothing happening in front of it.

## Comic Book

- **Fits**: humorous stories, "that's so us" situations, superhero metaphors, younger audiences.
  **Avoid** for sober B2B (unless the humor is the point and the brand allows it).
- **Imagery**: bold black outlines (3–6 px at 1080p), flat colors with halftone shading, panels
  and gutters, speech bubbles, action lines, onomatopoeia ("POW") as graphic elements.
- **Typography**: comic lettering fonts for bubbles (license check), a heavy condensed display for
  sound words.
- **Motion**: panel-to-panel camera moves; snappy poses (2–3 key poses per action), impact frames
  with zoom and shake; on-twos stepping for a hand-drawn feel.
- **Transitions**: panel wipes; a camera moving through gutters; page turns sparingly.
- **Audio**: cartoon SFX on impacts, a punchy score.
- **Effort**: M–L (characters may need generated art; budget it).
- **HyperFrames**: SVG panels plus the Halftone effect on image layers; generated character art
  animated in layers.
- **Typical failures**: inconsistent characters across panels; too much text in bubbles;
  unlicensed comic fonts.

## Split-Flap

- **Fits**: travel, logistics, announcements, "what's next" reveals, word swaps, stats. **Avoid**
  for long copy.
- **Imagery**: a mechanical departure-board grid; dark plates, light characters; visible hinges
  and housing; subtle shadows.
- **Typography**: condensed sans or the board's characteristic font; a fixed cell width.
- **Motion**: plates flip with overshoot and settle (`back.out` on the plate, the housing recoils a
  few px, the shadow lags one frame); cascading left-to-right timing; the final value never
  overshoots.
- **Transitions**: the whole board flips to the next message; the camera pulls out to reveal the
  board in a scene.
- **Audio**: a mechanical flutter that lands with each settle; a station chime as the motif.
- **Effort**: M.
- **HyperFrames**: per-cell CSS 3D flips with GSAP; the docs show split-flap motion as an example.
- **Typical failures**: flips that are too fast to read; an unsynced flutter sound; messages longer
  than the board.

## Retro VHS

- **Fits**: nostalgia, 80s/90s references, ironic humor, "remember when" problem setups (as the
  "before" world). **Avoid** for precision or trust messages.
- **Imagery**: tape noise, color bleed, tracking lines, a slightly washed palette, 4:3 safe framing
  inside 16:9 or 9:16 optional, timestamp and REC overlays.
- **Typography**: VCR OSD-style monospace, chunky 80s display fonts (license check).
- **Motion**: jittery tracking wobble (seeded), rewind and fast-forward speed ramps, pause-frame
  jitter.
- **Transitions**: tape rewind, a channel-switch glitch, static bursts.
- **Audio**: tape hiss, warble, a synth or library score, button clunks.
- **Effort**: M.
- **HyperFrames**: the Tape Damage, Scanlines, Channel Separation, and Chroma Softening effects on
  media layers; the `glitch` transition.
- **Typical failures**: degrading the product UI or logo until it is unreadable; constant glitching
  (fatiguing); effects applied to text layers (effects work on media layers).

## Halftone

- **Fits**: editorial, print heritage, posters, punk or zine energy, magazine-style explainers.
  **Avoid** when photographic detail matters.
- **Imagery**: dot screens (or line screens) on photos and shapes; a two-ink palette from brand
  colors; paper texture; registration offsets as a stylistic accent.
- **Typography**: a strong grotesque or slab; poster scale.
- **Motion**: dot size animates (images "develop" from the dots); a print-press slide-in; offset
  drift as an idle.
- **Transitions**: an ink-wipe; a dot-grow transition to solid color.
- **Audio**: a print-press thump, paper rustle, punchy drums.
- **Effort**: S–M.
- **HyperFrames**: the Halftone, Two-Ink Print, Ordered Dither, and Mono Screen effects (media
  layers); SVG dot patterns for vector shapes.
- **Typical failures**: moiré after compression (use a coarser screen than you think); muddy
  overprints; effects stacked on large layers (slow renders).

## Bauhaus

- **Fits**: design, architecture, education, cultural brands, playful-geometric explainers.
  **Avoid** if the brand palette cannot map to strong primaries.
- **Imagery**: circles, squares, and triangles; primary colors (mapped to brand colors); strong
  diagonals; asymmetric balance; flat fills, no gradients.
- **Typography**: geometric sans, lowercase or uppercase consistently; text as a compositional
  block.
- **Motion**: shapes roll, stack, and balance; physical logic (a circle rolls, a square slides,
  a triangle tips); precise `power2.inOut`.
- **Transitions**: shapes sweep across and become the next layout; a circle iris (`sdf-iris`).
- **Audio**: percussive, minimal; wooden blocks; a modernist piano.
- **Effort**: S.
- **HyperFrames**: SVG and GSAP only.
- **Typical failures**: shapes with no compositional tension (everything centered); too many colors.

## Pixel Art

- **Fits**: games, gaming-adjacent products, retro charm, playful dev tools, kids. **Avoid** for
  high-end luxury.
- **Imagery**: a low-res grid (for example a 320×180 logical canvas scaled ×6 for 1080p), a
  limited palette (8–16 colors including brand colors), dithering, sprites with outlines.
- **Typography**: pixel fonts at integer scales only; a crisp fallback for long text.
- **Motion**: stepped animation (sprite frames), integer pixel movement, on-twos timing; jump
  arcs; screen shake by whole pixels.
- **Transitions**: pixelate in and out (the Pixelate effect), a screen wipe, a "level complete"
  card.
- **Audio**: chiptune, 8-bit SFX (jump, coin, power-up) as the recurring sound motif.
- **Effort**: M (sprites code-drawn or hand-made).
- **HyperFrames**: canvas with `image-rendering: pixelated`; quantize motion on the frame index.
- **Typical failures**: mixed pixel scales; anti-aliased edges; subpixel motion that blurs sprites.

## Blueprint

- **Fits**: engineering, building, planning, "how it's made", architecture, B2B infrastructure.
  **Avoid** for emotional consumer messaging.
- **Imagery**: a blueprint-blue ground (or the brand dark color), white or cyan line drawings,
  grid paper, dimension lines and annotations, hand-lettered notes as an accent.
- **Typography**: technical monospace or condensed sans; handwritten annotations sparingly.
- **Motion**: lines draw on (SVG stroke animation), dimension arrows extend, parts assemble; the
  camera pans across a large sheet.
- **Transitions**: the sheet unrolls; a blueprint fills with color and becomes the real object.
- **Audio**: pencil and pen scratches, a ruler click, a gentle technical bed.
- **Effort**: S–M.
- **HyperFrames**: SVG draw-on (watch the lint rules: no CSS multi-value `stroke-dasharray` on
  animated paths; set `d` before measuring).
- **Typical failures**: lines too thin for mobile; annotations unreadable; everything drawing on
  at once.

## Art Deco

- **Fits**: luxury, hospitality, events, anniversaries, premium spirits or fashion. **Avoid** for
  casual tech.
- **Imagery**: symmetry, sunbursts, stepped and fan motifs, gold or metallic accents (mapped to
  the brand), deep greens, blacks, or navies, fine line ornaments.
- **Typography**: high-contrast deco display faces, wide tracking, all caps; elegant serif for body.
- **Motion**: symmetrical unfolding (fans open, lines radiate), slow and stately (`power2.inOut`,
  0.8–1.5 s), shimmering metallic sweeps.
- **Transitions**: radial wipes; a curtain or door reveal; ornament frames that close and open.
- **Audio**: jazz-age or orchestral swing, chimes, a champagne-pop accent.
- **Effort**: M.
- **HyperFrames**: SVG ornaments, gradients for metallic sheen, GSAP.
- **Typical failures**: kitsch from overdone ornament; illegible display fonts; gold that turns
  brownish after compression.

## Neo-Brutalism

- **Fits**: indie tools, startups, Gen Z social, anti-corporate brands, bold "no-nonsense"
  messages. **Avoid** for conservative or premium-calm brands.
- **Imagery**: thick black borders (4–6 px), hard offset shadows (no blur, 6–12 px), clashing flat
  colors (mapped to the brand), raw UI blocks, stickers, deliberate misalignment.
- **Typography**: chunky grotesques, very large, tight; mixed weights on purpose.
- **Motion**: snappy and blunt (`power4.out`, 0.15–0.25 s), slams, hard stops, shake on impact,
  elements shoving each other; humor through abruptness.
- **Transitions**: hard cuts; block wipes; elements knocking the previous scene out of frame.
- **Audio**: punchy percussion, clunks, a deadpan voiceover.
- **Effort**: S.
- **HyperFrames**: CSS and GSAP only.
- **Typical failures**: ugliness without intent; contrast failures from clashing colors; chaos that
  hides the message.
