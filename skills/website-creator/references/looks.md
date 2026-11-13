# Looks, color posture and tone

Vocabulary for making three directions genuinely different. A look is a *material* (paper, ink, faces, rules, radius, texture, motion temperament, voice), not a layout; layout comes from the archetype and the centerpiece.

## Ambition by page mode

Decide first how loud the surface may be:

- **Persuade** (landing, launch, campaign): full commitment — strong color, a loud centerpiece, motion with character.
- **Experience** (portfolio, showcase, event): the surface itself is the content; the radical end is welcome.
- **Operate** (docs, dashboard, settings): calm surface, fast feedback, little decoration.
- **Read** (blog, long article): typography first, motion nearly absent.

A marketing page treated like Operate is the most common reason a result looks generic.

## Color posture

Name the posture of each direction; three directions should not share one.

- **Restrained** — near-neutral surfaces, one accent used sparingly. The safe end; never the only option offered.
- **Committed** — the brand color owns large fields (full sections, the hero ground), with ink and one signal on top.
- **Drenched** — one saturated color soaks the whole page (prussian blue sheet with white line ink, acid yellow with black); everything else is that color's light and dark.
- **Full palette** — two or more strong colors compete as whole fields, poster-style, with hard edges between them.

A posture beyond restrained means real chroma on large areas (well above near-grey), hard contrast blocks, and the accent allowed beyond CTAs. "Light, dark or warm" is not a color idea; pick a color family that is unusual for the category in at least one direction. Contrast for text stays WCAG AA at minimum on every surface.

## Named looks (starting points)

Quiet to loud. Use them as material sketches, adapt them to the product, and never ship one unchanged.

- **Specimen** — pale stock, near-black ink, a serif display with a sober grotesk, hairlines, one ink-blue signal. *Restrained.*
- **Console** — graphite ground, mono figures, keycap-like controls, one electric signal color. *Restrained to committed.*
- **Blueprint** — prussian-blue sheet, white line ink, dimension strings, photos printed as cyanotypes. *Drenched.*
- **Broadside** — grained buff paper, condensed wood-type capitals, heavy and thin rules, one vermilion. *Committed.*
- **Brutal** — poster-white, thick black rules, boxed cells and solid fills, uppercase heavy grotesk, zero radius, one acid fill. *Committed.*
- **Riso / overprint** — two or three spot colors printed over each other, misregistration, halftone photos. *Full palette.*
- **Sticker** — saturated ground, thick outlines, hard offset shadows, rotated labels and badges. *Full palette.*
- **Arcade** — dark CRT ground, chunky display capitals with RGB split, pixel figures, two signal colors. *Full palette.*
- **Atmosphere** — dark or deep-tinted ground, a living light field (shader, blooms, grain) behind sparse type. *Committed.*
- **Squeeze** — one candy color drenched over everything, soft blobby forms, rounded heavy type. *Drenched.*

## Texture as material

A texture can carry a look on its own when it comes from the product's domain:

- **Glyph field** — an image or video rendered as a grid of characters from the domain (code tokens for a dev tool, notes for a music app, digits for finance), cells 6–10 px, brightness mapped to glyph density.
- **Halftone / dither** — photos reduced once to dots or a dither pattern in the palette's two inks; process once at build time, not per frame.
- Animated variants step at 8–12 frames per second (deliberately coarse), cap DPR at 2, pause offscreen, and show a still under reduced motion.

## Tone dials

Set five dials per direction, each with a one-line reason from the product:

| Dial | From | To |
|---|---|---|
| Energy | quiet | loud |
| Finish | raw | polished |
| Density | airy | packed |
| Weight | light | heavy |
| Seriousness | playful | grave |

The three directions differ clearly on at least two dials. Then translate every vague adjective into observable decisions before building: "hochwertig" → which display size, which surface share, which contrast; "mutig" → which color field, which centerpiece, which overshoot. A direction planned as loud and raw that ships as beige cards on white is the failure to avoid — there is no hidden safe variant.
