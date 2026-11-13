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

`codex` with its image tool can generate illustrations when nothing real fits. Check availability first (`codex --version`, a tiny test prompt); if the quota is used up, skip to 4. Prompt with the DESIGN.md palette and style, generate a set together for consistency, and never generate fake product screenshots, people presented as customers, or logos.

## 4. SVG, CSS, canvas, shader

Typographic compositions, diagrams of how the product works, data drawn from real numbers, generative patterns seeded from the brand color. Avoid the "shape-assembled illustration" (a scene built from circles and rounded rects) — it reads as clip art.

## Always

- `alt` for every `<img>`: describe what matters, `alt=""` for decoration.
- Formats: AVIF/WebP + fallback via `<picture>`; `srcset`/`sizes` for widths 480–2560; explicit dimensions.
- No hotlinking; images live in the project.
- No `placeholder.com`, `picsum`, `via.placeholder`, empty `src` (the linter errors on these).
