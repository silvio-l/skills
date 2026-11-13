# Images

Real images beat placeholders; honest images beat impressive ones. Work down this cascade and stop at the first source that fits.

## 1. Free photo pools, with license proof

Unsplash, Pexels, Pixabay, Wikimedia Commons (check each file's license; CC BY needs attribution), Openverse as a search across them.

- Download the original, record source URL, author, license and date in `.website-creator/images.md` (and in the report). CC BY/BY-SA: attribution visible on the page or in an image-credits section.
- Avoid the recognizable stock clichés (handshake, laptop-on-desk with coffee, diverse team laughing at a screen). Prefer detail, place and material over people pretending to work.
- Crop and color-grade toward the palette (CSS `filter` or one-time processing), consistently across all photos.

## 2. Project assets

Screenshots of the real product (taken via pwc from the running app, cleaned demo data, device frame only if it adds something), logo, existing illustrations, team photos. The product itself is usually the strongest image.

## 3. Codex CLI image generation, if quota remains

`codex` with its image tool generates what no pool has: the brand's own world (a place, a material, an object, an atmosphere in the page's palette), hero fields, scene stills, objects for overlays. A generated image that fits the direction beats a generic stock photo; it is a full option for atmosphere, not only a last resort. The product itself still comes from step 2. Check availability first (`python3 S/scripts/concept.py check`: only a ChatGPT subscription login counts, never an API key; call `codex exec` with the key variables unset, as `concept.py` does); if the quota is used up, skip to 4. Prompt with the DESIGN.md palette and style, generate a set together for consistency, and never generate fake product screenshots, people presented as customers, or logos.

Every generated image that ships gets a line in `.website-creator/images.md` (file, tool, prompt, date) and a quiet "KI-generiert" note in the image credits on the page.

- **Prompt order**: subject, setting, light and palette (hex values from DESIGN.md), style, composition (where the empty space for text sits), exclusions (no text, no logos, no UI), format at 2× the display size.
- **Grain and texture in code**, not in the prompt: a CSS or canvas noise layer stays consistent across images and can be tuned later.
- **Generated object, live interface**: generate the object (a device, a desk, a sign, a box) with an empty surface, cut it out, measure the surface rectangle in the final image, and position real HTML over it — the product UI, a counter, a form. The image gives material, the overlay stays sharp, current and accessible. All images of one page tell one consistent story (same world, light and lens).

## 4. SVG, CSS, canvas, shader

Typographic compositions, diagrams of how the product works, data drawn from real numbers, generative patterns seeded from the brand color. Avoid the "shape-assembled illustration" (a scene built from circles and rounded rects) — it reads as clip art.

## Always

- `alt` for every `<img>`: describe what matters, `alt=""` for decoration.
- Formats: AVIF/WebP + fallback via `<picture>`; `srcset`/`sizes` for widths 480–2560; explicit dimensions.
- No hotlinking; images live in the project.
- No `placeholder.com`, `picsum`, `via.placeholder`, empty `src` (the linter errors on these).
