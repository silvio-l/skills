# Sprite Pipeline (2D)

Routing category H: sprites, item and UI icons, portraits, environment tile art — every flat asset
that is not a platform app icon (that one goes to `app-icon-director`). Also the first half of
category D, where a 3D pack borrows this pipeline to produce its consistent reference images.

Same quality bar as the 3D branch. A sprite with a haloed alpha edge or a non-power-of-two canvas is a
defect, not a stylistic choice.

**Before writing the generate prompt, do the style-profile check** from SKILL.md's "Before generating
any reference image, check for a named style profile" — it applies to this branch exactly as it does to
the 3D ones. If the request names or implies a style and the user supplied no images of their own, fold
four to eight concrete cues from the matching [REFERENCE-STYLES.md](REFERENCE-STYLES.md) profile into
the prompt. Everything below assumes that step already happened; none of these three stages can add art
direction the prompt did not carry.

## Three stages

All three endpoints run on the one `FAL_KEY` in `~/.config/fal/.env` — auth and calling pattern in
[AI-MESH-SERVICES.md](AI-MESH-SERVICES.md), account setup in `~/.claude/infrastructure/fal-ai.md`.
Missing key → stop and report, never a hand-drawn placeholder.

**1. Generate.** `fal-ai/nano-banana/edit` (Google Gemini 2.5 Flash Image) is the default: it is the
identity- and style-consistent one, which is what makes a pack cohere. Input `image_urls: [dataUri]`
plus `prompt`. `fal-ai/flux-pro/kontext` is the alternate (~$0.04/image) — it stays more frontal and
distorts small details more readily. Both are documented in `~/.claude/infrastructure/fal-ai.md`; do
not re-derive their parameters here.

**2. Cut out.** `fal-ai/birefnet` for background removal, wherever the asset needs transparency
(anything composited over a game background — so: most things). Input `image_url`. Skip it only for
full-bleed tile art and backgrounds that genuinely fill their canvas.

**3. Upscale.** `fal-ai/esrgan` to the target in-engine resolution ($0.00111 per compute-second,
verified live). Upscale **after** cutting out, not before: BiRefNet's matting is cleaner on the
generation-native resolution, and ESRGAN sharpens the alpha edge along with the color instead of
magnifying a soft one.

Generate at or above the target size where possible and use ESRGAN to reach an exact power-of-two —
never to invent detail that was never generated. A 256px sprite upscaled to 1024 is a blurry 1024px
sprite.

## Canvas and sizing

- **Power of two** (256, 512, 1024, 2048) wherever the engine expects it — required for mipmapping and
  for most compressed texture formats. Square unless the subject genuinely is not.
- **Match the in-engine target exactly.** A sprite that gets resampled at import loses the edge quality
  this whole pipeline exists to protect.
- **Leave padding** inside the canvas. A subject touching the canvas edge clamps or wraps badly at
  mip levels and cannot be given a bleed margin later.
- **Format**: PNG for anything with alpha or hard pixel edges; WebP where the engine supports it and
  file size matters. Not JPEG — it has no alpha and its ringing artifacts land exactly on the sprite
  silhouette.

## Alpha edge quality bar

After background removal, the edge is what separates a shipped sprite from an obvious composite:

- **No halo.** A light or dark fringe means the matte kept background pixels. Re-run the cutout on the
  higher-resolution source rather than trying to erode the alpha afterwards.
- **No stair-stepping.** The alpha channel must be genuinely anti-aliased, not a 1-bit mask upscaled.
- **No semi-transparent interior.** Partial alpha belongs at the silhouette and in genuinely
  translucent material (glass, smoke), nowhere else.
- **Premultiplication** must match what the engine expects — mismatched premultiplied vs. straight
  alpha shows up as a dark fringe that looks exactly like a bad matte.

## Pack consistency (category D and multi-sprite sets)

The technique that actually works, and the one this skill uses: **generate the style reference once,
then condition every pack member on it.**

1. Generate a single reference/style image and get it right — silhouette weight, palette, lighting
   direction, line quality, level of detail.
2. Pass that image as the conditioning input (`image_urls`) to `fal-ai/nano-banana/edit` for **every**
   subsequent pack member, varying only the prompt.
3. Validate the finished set against each other, not just individually — `check_palette_consistency`
   in `scripts/validate_2d_asset.py` compares dominant colors across the pack.

For a 3D pack (category D), the same reference-image set is what feeds the image-to-3D endpoints —
consistency comes from the shared conditioning image, not from the mesh service. This is deliberate:
Meshy's conversational "3D agent" achieves pack consistency in its **web UI**, and that feature is not
confirmed present in the `fal-ai/meshy/*` API. Do not build against it.

## Validation

`scripts/validate_2d_asset.py` is the gate — the script's exit code, not a look at the image.

```bash
python3 skills/game-asset-director/scripts/validate_2d_asset.py \
  --image sprite.png --target 512x512 --require-pot --require-alpha

# pack consistency: two or more finished sprites
python3 skills/game-asset-director/scripts/validate_2d_asset.py \
  --image enemy_a.png --target 512x512 --compare-to enemy_b.png
```

Checks: canvas dimensions against the requested target, power-of-two (only where the engine expects
it — `--require-pot`), file format against an allow-list (PNG/WebP), alpha-edge quality after
background removal, and dominant-color consistency across a pack.

**Dependency: Pillow.** The image-reading shell (`read_image_size`, `read_alpha_edge_stats`,
`read_dominant_colors`) needs `pillow` (`pip install pillow`) — it is not stdlib. If it is missing the
script says so and exits non-zero rather than skipping the check. The pure predicate functions
(`check_canvas_size`, `check_power_of_two`, `check_format`, `check_alpha_edge_quality`,
`check_palette_consistency`) take plain numbers and tuples and import nothing, which is what makes them
testable without Pillow installed.

**On failure:** a canvas or format problem is a free fix — resize, re-export, re-run. A composition or
style problem needs a new paid generation, which stops and asks first. Same rule as the 3D branch.
