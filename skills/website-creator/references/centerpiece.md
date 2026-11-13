# The centerpiece

Every page has one loud center that carries the impression — the thing a visitor remembers and describes afterwards. Boldness is spent there in full; the rest of the page supports it instead of competing. "Restrained everywhere" is not a direction, it is the absence of one.

## Choose the hero material

Pick the material from the product, not from habit. Each of the three directions should use a different one.

| Material | Fits when | Shape on the page |
|---|---|---|
| **Playable product demo** | The product has a core flow that fits in one screen | A rebuilt, interactive slice of the real UI (real tokens, real labels, a few states) the visitor can click through; replaces two or three explanatory sections |
| **Real-time 3D object** | Something can be turned, inspected, assembled, or has material (glass, metal, physics) | Three.js/WebGL stage, draggable or scroll-turned, poster image first |
| **Video** | A process, a transformation, or a feeling over time | Muted, looping or scrubbed film as the hero field (HyperFrames when rendered) |
| **Giant type** | The message itself is the strongest asset | Display type at poster scale, cropped, layered or set as the full first viewport |
| **Data as image** | The product's value is a number, a pattern, a before/after | The figure drawn large (bar as wall, line as horizon, numbers as surfaces) instead of a sentence about it |
| **Procedural field** | Atmosphere matters and no subject photographs well | Shader or canvas field (gradient mesh, caustics, fluted glass, grain, particles) that reacts to pointer or scroll |
| **Photograph or generated image** | People, places or physical goods sell it | One commanding image, full bleed or hard-cropped, not a stock vignette |

## Moments around it

Beyond the hero, every screen may carry one *event* of its own form instead of another heading-plus-text block: a slider that changes a result, a toggle between before and after, a diagram that builds, a counter that runs, a comparison you can drag. Sticky or pinned scroll stories are allowed at most once per page and need a storyboard (step by step: what the visitor sees, what changes) before they are built.

## Tests for every device

- **Remove it — is the message clearer?** If yes, the device is decoration; cut it.
- **Skeleton test.** Grey out all text: does the page still show a structure, a rhythm, a peak? If the skeleton is a column of equal blocks, the layout is not done.
- **Peaks.** Read the page as a scroll rhythm: there must be at least one peak (the centerpiece) and quieter valleys, not a flat line of same-weight sections.

## Guard rails

The radical direction may relax size budgets (larger video, heavier 3D) and says so in the report. Hard limits for every direction: WCAG AA for text and controls, a strict CSP (no inline script evaluation, assets from known origins), a meaningful poster or static fallback, pause offscreen, DPR capped at 2, and `prefers-reduced-motion` honored.
