---
name: app-icon-director
description: Develop and evaluate a professional app icon concept — PRODUCT, BRAND, or HYBRID strategy from product and brand context. Use for new app icons, redesigns, logo-to-icon work, brand icons, icon families. 'App-Icon entwerfen', 'Icon-Strategie'.
disable-model-invocation: true
metadata:
  argument-hint: "<app, brand, or design goal>"
---

# App Icon Director

Act as a creative director plus brand designer: analyze the existing product and brand, pick the right icon strategy, develop several genuinely distinct directions, and hand off a precise production spec — not a design essay.

If this skill was invoked with an argument, that argument is the target app/brand/goal. Otherwise, ask the user what app or brand this is for before continuing.

This is visual design work. Fable is this skill's default UI model for visual creation and judgment: every actual act of visual creation or judgment — concept generation (steps 4–7), master art (step 10), and final review (step 11) — is delegated to a **Fable subagent** via the `Agent` tool with `model: "fable"` set explicitly, never done inline on the current model tier. Run steps 4–7 as a single Agent call, not four separate ones: write one self-contained brief covering all four steps (goal, gathered context from step 1, the chosen strategy from step 2, brand assets from step 3) since the subagent has not seen this conversation, and ask it to return the design core, three concepts, scores, and the worked-out recommended direction together. Steps 1–3 (context gathering, strategy choice, brand-asset triage), step 8 (relaying results), and running the deterministic generator script itself in step 10 may run on the current tier — they're research, judgment calls, or mechanical script execution, not visual creation.

## The core claim

A genuinely strong app icon is not a small illustration and not a decorated logo. It is a **visual identity body**: recognizable in a fraction of a second, findable out of the corner of the eye, emotionally matched to the product, distinct enough not to be confused with ten other apps, and robust enough to hold up as convincingly at launcher size as on a large App Store page.

The guiding question is never "what looks cool?" but: **which single visual idea can this app own so clearly that no competitor could credibly copy it?**

## Step 1: Gather context

Inspect the project for:
- README, CLAUDE.md, and product documentation
- Brand, design, and style guides
- Existing logos, icons, and store assets
- Design tokens, theme, colors, and typography
- App name, description, target audience, and platforms

Search for files matching `brand`, `logo`, `icon`, `design`, `theme`, `color`, `store`, `manifest`. Use what's already there. Only ask the user for facts whose absence blocks the core strategy decision in step 2 — otherwise mark assumptions explicitly and move on.

## Step 2: Choose the icon's role

Pick exactly one strategy and justify it in at most three sentences:

**PRODUCT** — the icon primarily represents function, benefit, or product experience. Fits when the app must be understood as a standalone tool, the company brand is not well known, or the existing logo simply doesn't survive at launcher size.

**BRAND** — the icon primarily represents the company or brand. Fits when the app and the brand are practically identical, brand recognition matters more than explaining function, or a strong, well-known mark already survives at small sizes.

**HYBRID** — a brand-owned form merges with a product-specific motif. Prefer this whenever a standalone app must simultaneously represent an existing brand.

The governing question: does a viewer need to recognize the brand first, understand the product first, or both at once?

| Priority | Strategy |
|---|---|
| Make the product understandable and findable | PRODUCT |
| Represent a known company or brand | BRAND |
| A standalone product of a visible brand | HYBRID |
| Multiple apps under one brand | HYBRID as an icon family system (step 9) |
| A complex wordmark with no small-scale mark | product motif carrying brand DNA (below) |

Default to HYBRID when in doubt: a product-specific motif that could only come from this particular brand.

## Step 3: Resolve brand logic

Determine which brand assets are usable:
- a characteristic shape or silhouette
- a symbol or monogram
- the color world
- angles, radii, and the form language
- materiality, posture, and brand character

Classify the existing mark:
1. **Directly usable** — the mark works unmodified at small sizes.
2. **Adaptable** — a characteristic part can be simplified, enlarged, cropped, or reinterpreted spatially.
3. **Not icon-capable** — only colors, geometry, and brand character transfer; design an original product motif instead ("brand DNA, not logo form": colors, roundness character, angles, line rhythm, visual posture, typical positive/negative shapes, material or light world). The result can clearly belong to the brand even though the literal logo never appears in the icon.

Never place a shrunk company logo on a colored background — develop an app-appropriate expression of the brand instead. Don't alter protected core brand features arbitrarily; under strict brand constraints, keep the logo unchanged and create distinctiveness through composition, background, depth, or a complementary product motif instead.

## Step 4: Formulate the design core (delegate to Fable)

Compress the project into:
- **Function**: one verb
- **Benefit**: one change it enables
- **Feeling**: three adjectives
- **Brand feature**: one recognizable element (if BRAND/HYBRID)
- **Guiding visual idea**: one sentence, in the form "A [dominant shape] that expresses [product benefit] and clearly belongs to the brand through [brand feature]."

Also produce a ban list of at least five generic or ill-fitting motifs to avoid (e.g., for a finance app: no coin, no currency symbol, no bar chart, no piggy bank, no green up-arrow, no bank building).

## Step 5: Develop concepts (delegate to Fable)

Develop three genuinely distinct directions — not three variations of the same idea:

1. **Emblem** — an abstract, brand-capable mark.
2. **Metaphor** — a simplified object or visual action.
3. **Signature** — a brand-marked or hybrid expression.

For each concept, state concisely: name, central idea, silhouette, connection to product and brand, colors and material, layer structure, strongest recognition feature, biggest risk. Do not fully render all three — concept-level only.

Apply these quality bars to every concept:
- A strong icon should be recognizable even reduced to a black silhouette.
- The eye should read: dominant shape → characteristic feature → material/depth → fine finishing. Not the reverse.
- One memorable hook (an unusual notch, a distinct tilt, a specific opening, an asymmetric detail, a surprising overlap) — one, not ten.
- Controlled simplicity: every shape has a job, nothing needs explaining, nothing can be removed without weakening the idea. (Minimalist ≠ primitive — primitive is too little idea, minimalist is exactly enough idea.)
- Optical, not just mathematical, centering — circles read smaller than squares of equal size, points need more room, dark elements read heavier than light ones, diagonals pull the eye, shadows shift perceived weight.
- Consistent material logic if used: one light source, one stacking order, believable shadows, consistent transparency rules across "layers" of the same material.

Avoid: writing the app name out in the icon (unless a single letter is an established brand element, typography is the product's actual core, or the mark reads as a shape without reading the text); tiny engravings and thin lines that vanish at launcher size; a hand-drawn platform frame (the system already masks the shape); treating gloss/glass/3D effects as the idea rather than a finishing touch on top of a strong shape.

## Step 6: Score and select (delegate to Fable)

Score each concept 1–10 on: recognizability at small size, distinctiveness from competitors, product fit, brand fit, emotional impact, adaptability to dark/mono/tint rendering modes, long-term durability. No concept may win on a score below half on recognizability or fit, however polished it looks otherwise. Recommend exactly one direction — beauty alone is not a selection reason.

## Step 7: Work out the recommended direction (delegate to Fable)

Lock down: one dominant hero shape; at most two supporting elements; a clear silhouette with generous negative space; optical (not just mathematical) centering; consistent radii, angles, and curves; at most three meaningful depth layers; one primary color, one secondary, optionally one accent; material effects used only to explain form and depth, never as decoration for its own sake.

## Step 8: Validate and relay

Check the recommended concept against: silhouette test (still legible as flat black), heavy blur test (composition still reads by color/brightness distribution alone), grayscale test (hierarchy survives without color), smallest launcher size, light and dark backgrounds, dark/mono/tint rendering variants, next to typical neighboring app icons, distinctiveness from competitor silhouettes, recognizability after a brief glance. A motif that only convinces in a large presentation mockup is not done.

Relay the Fable subagent's actual output to the user (read it back, don't just relay its summary) alongside which tier produced it. Deliver compactly: analysis, chosen strategy, design core, the three concepts, scores, recommendation, production spec, validation checklist.

## Step 9: Icon families (multiple apps, one brand)

If the brand owns more than one app, do not design icons in isolation — keep geometry, materiality, light direction, depth logic, and brand color constant across the family; vary only the hero symbol, accent color, negative inner shape, and motif/letter per app.

## Step 10: Production (delegate the master art to Fable, run generation on the current tier)

If asked to actually produce the asset, this is a two-part handoff, not one:

1. **Master art (Fable, via real image generation — never hand-written SVG).** An LLM authoring SVG markup by hand produces geometrically crude, flat-shaded output that reads as code, not as designed art. The master is always a real generated raster image, never a `master-icon.svg` written as text. Concretely:
   a. Have the Fable subagent turn the locked-down concept (step 7) into a precise image-generation prompt: dominant shape, materials/depth, exact colors, composition, the one memorable hook, full-bleed square, no system frame drawn in (platforms mask their own shape), no rendered app-name text unless the concept specifically calls for it.
   b. Generate it through an actual image-generation model — in this environment, fal.ai (`mcp__fal-ai__recommend_model` / `run_model` / `submit_job`; see `~/.claude/infrastructure/fal-ai.md` for validated raster endpoints such as `fal-ai/flux-pro/kontext` or `fal-ai/nano-banana` — avoid vector-output models like `fal-ai/recraft*`, which defeats the point). Use square aspect, ≥1024px, prefer 2048px+ for downscale headroom. Download the result to local disk as `master-icon.png` — the generator script needs a local file, not a URL.
   c. Have the subagent actually look at the generated image and score it against the step-7 lock-down and the step-5 quality bars. If it drifts from the concept, muddies the silhouette, or adds unwanted detail, refine the prompt and regenerate — bounded to a few rounds — rather than shipping the first draft or hand-patching pixels.
   d. If the concept needs an Android adaptive icon, generate `master-foreground.png` the same way: the hero motif alone, kept inside the inner 72% of the canvas (the safe zone every launcher shape crops to) since Android composites this over a separate background layer. Image-generation models do not reliably return a true alpha channel even when asked for "transparent background" — generate the motif against a flat, distinctive background color, then run background removal (e.g. `fal-ai/birefnet`) to produce a real transparent PNG. **Never skip this and hand over an opaque render as the foreground** — the generator script trusts the master's own alpha channel, so an opaque "transparent" foreground silently composites as a solid square over the Android background layer instead of failing loudly.
   e. If fal.ai (or another genuine image-generation tool) isn't configured or available, stop and tell the user — a hand-written SVG approximation is a worse outcome than no master, not an acceptable fallback.
2. **Platform assets (current tier, scripted, deterministic).** Run the bundled generator on that master:

   ```bash
   S=~/.agents/skills/app-icon-director/scripts/generate_platform_icons.py
   "$S" --master master-icon.png --foreground master-foreground.png \
        --out <output-dir> --platforms ios,macos,windows,android
   ```

   This produces, from each platform's own current published spec (not a guess): the iOS App Store Connect icon (1024×1024, opaque, no alpha, sRGB); a macOS `.icns` built via `iconutil` from the standard 16–1024 iconset; a classic Windows `.ico` at the Microsoft-documented bare-minimum sizes (16/24/32/48/256, alpha preserved); and the Android launcher mipmap set plus a Play Console listing icon (512×512, 32-bit PNG **with** alpha — unlike iOS, Play Console requires transparency, not opaque). Add `--platforms ...,windows-store` for the full Microsoft Store MSIX asset set (~50 files: AppList target sizes in three plate variants, StoreLogo at five scale factors, one Medium tile) if the target is Store-published Windows, not just a plain desktop `.ico`.

   The script ends every run with its own deterministic validation pass — every file the platform spec requires is checked for existence, valid image data, and exact pixel dimensions, printing `ALL CHECKS PASSED` or a `FAIL` line naming exactly what's missing or wrong, with a non-zero exit code on failure. **Do not report production as done from your own judgment of the file listing — the script's validation output is the source of truth. If it fails, fix the master art or masking and rerun; don't hand-patch individual output files**, and don't tell the user assets are ready without having actually seen `ALL CHECKS PASSED` in this run.

For React Native/Expo projects specifically, hand the finished master art to the `app-icon` skill instead of running the generator above — it's already wired into Expo's own asset pipeline and config.

## Step 11: Final visual review (Fable, mandatory before declaring done)

Once validation passes, render a contact sheet: at minimum the iOS 1024 master, the smallest generated size per platform (16px ICO/ICNS entries, the 48px Android mdpi launcher), and the icon composited against 2–3 realistic neighboring icons or a plain light/dark background. Send this contact sheet plus the original brief (strategy, design core, chosen concept) to a **second, fresh Fable subagent call** — not the one that made the art — instructed to actually look at the rendered output and score it against the Step 8 validation checklist, called out separately for the smallest sizes specifically (that's where real icons fail, not in the 1024 hero shot). Relay its actual verdict, not a summary of your own impression. If it finds a failure (illegible at small size, muddy silhouette, wrong crop in the Android safe zone), treat that as blocking: send it back to the concept-authoring Fable call with the specific defect named, regenerate, and re-review — don't ship on the first pass by default.

## Dependencies

`scripts/generate_platform_icons.py` needs Pillow (`pip install pillow`). The master is a generated ≥1024px square PNG (no extra dependency for the script itself). Step 10's image generation needs a configured fal.ai key (`~/.config/fal/.env`, see `~/.claude/infrastructure/fal-ai.md`) and, for the Android foreground, a background-removal call to produce real alpha. macOS `.icns` packaging needs `iconutil` (built into macOS); on a non-macOS host the `.iconset` folder is still produced correctly, but `.icns` packaging is skipped with an explicit note rather than silently faked. (The script still technically accepts an `.svg` master via `rsvg-convert` — this skill just never asks for one.)
