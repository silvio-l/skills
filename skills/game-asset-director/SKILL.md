---
name: game-asset-director
description: "Directs mobile-game asset generation: 3D (fal.ai Rodin/Tripo/Meshy/Trellis + Blender retopo/bake) and 2D sprites/icons, routes hard-surface to blender-scripting, validates AAA quality. Use for 'Game-Asset erstellen', 'Spielgrafik generieren'."
metadata:
  argument-hint: "<asset description or reference image>"
---

# Game Asset Director

Classify a mobile-game asset request, route it to the tool that reliably clears an AAA quality bar
for that asset class, finish it to mobile budgets, and gate the result behind a validator script.
Quality is the default axis, not cost — see "Routing" below. This skill owns the decision; it does
not own every step of the execution.

`blender-scripting` is a subordinate tool here, not a competing front door. It is excellent at
procedural hard-surface geometry and version-safe export, and has no PBR baking, no retopology, no
mobile budget model, no AI-mesh access, and no 2D branch at all. This skill fills exactly those gaps.

## Announce before executing

State the chosen category, the concrete tool/tier, and a one-line reason **before** running anything
that costs money or takes minutes. One or two lines, not an essay:

> Category B (hero/organic) → `fal-ai/hyper3d/rodin` + HighPack, because a named boss character needs
> quad topology and 4K PBR that procedural `bpy` will not produce.

**If `FAL_KEY` is missing, stop and say so.** Do not generate a placeholder mesh, a grey-box stand-in,
or a "representative" procedural substitute and present it as the asset. A missing key is a blocked
run to report, never a thing to work around silently. Key location and calling pattern:
[AI-MESH-SERVICES.md](AI-MESH-SERVICES.md).

## Routing

Decide from the request itself — never ask the user to pick a category. Quality tier is the default
axis, not cost: the spread between the cheapest and the flagship tier is ~$0.02 vs. ~$1.20 per asset,
which is noise against what a visibly bad hero asset costs. Every AI tier below runs through the
**same** `FAL_KEY` — there is no per-tier credential switch and no separate Meshy/Tripo/Rodin account.

| Category | Signal | Route |
|---|---|---|
| **A. Procedural hard-surface** | rock, terrain, modular building/kit, generic prop, GN tree, "N variants of X" | Hand off entirely to `blender-scripting`, then run `scripts/validate_asset.py` — it does not self-validate against mobile budgets. |
| **B. Hero / character / organic** | character, creature, boss, hero prop, unique named asset | `fal-ai/hyper3d/rodin` with **HighPack** (quad topology + PBR + 4K, ~$1.20). Alternate: `fal-ai/meshy/v6-preview/image-to-3d` where its style fits better. → `scripts/retopo_bake.py` → LOD chain → validate. |
| **C. Complex background prop** | one-off statue, furniture, "barrel with graffiti" — visible but not hero-tier | `tripo3d/tripo/v2.5/image-to-3d` with HD textures. Drop to `fal-ai/hunyuan3d/v2/turbo` or `fal-ai/trellis` **only** for high-volume far-background filler where the user signals volume over per-asset fidelity. → same finishing pipeline as B. |
| **D. Asset pack** | "enemy pack", "matching set", any request for visual consistency across several assets | Generate a consistent **reference-image set first** via `fal-ai/nano-banana/edit` (or `fal-ai/flux-pro/kontext`), then convert each image through B or C by its own hero-vs-background status. Not Meshy's web-only "3D agent" — see [AI-MESH-SERVICES.md](AI-MESH-SERVICES.md). |
| **E. PBR texture / material only** | "make this look like rusted iron", no new mesh | Procedural Principled-BSDF graph via `blender-scripting`. AI photo-to-PBR only when the user supplies an actual reference photo. |
| **F. App icon** | a platform app icon specifically | Delegate entirely to `app-icon-director`. Nothing from this skill applies. |
| **G. LOD-only on an existing mesh** | "add LODs to this" | Chained Decimate per [FINISHING-PIPELINE.md](FINISHING-PIPELINE.md), executed headlessly through `blender-scripting`'s conventions, then re-validate. |
| **H. 2D game asset** | sprite, item/UI icon, portrait, tile art — anything flat that is not an app icon | `fal-ai/nano-banana/edit` (or `fal-ai/flux-pro/kontext`) → `fal-ai/birefnet` where transparency is needed → `fal-ai/esrgan` to the target in-engine resolution → `scripts/validate_2d_asset.py`. See [SPRITE-PIPELINE.md](SPRITE-PIPELINE.md). |

Ambiguity rule: when a request sits between two categories, pick the higher-quality tier and say so in
the announcement. An over-specified background prop is a small cost; an under-specified hero asset is
a visible defect.

## Delegation contract with `blender-scripting`

State this explicitly so a future maintainer does not "simplify" the split away.

**Handed off whole** — categories A and G. The request goes to `blender-scripting` as-is; this skill
only validates the result afterwards.

**Reused mid-pipeline** — a narrower pattern than `app-icon-director`'s all-or-nothing handoff:

- **Final export.** Use `blender-scripting`'s `hasattr`-guarded export functions from
  `blender-scripting/export-and-errors.md` (`export_gltf`, `export_fbx`, `export_obj`, `export_stl`,
  `export_ply`) plus its GLTF settings table and post-export `gltf-transform` order. Do not write a
  second export path.
- **Headless bpy conventions.** `blender-scripting/SKILL.md`'s "Version robustness" section
  (`hasattr` probing, never pin a version) and its collection-linking rule
  (`bpy.context.scene.collection`, not `bpy.context.collection`) apply to every script here, and
  `blender-scripting/techniques.md`'s modifier-order idiom (add modifier → set active object →
  `modifier_apply`) is the pattern the LOD chain follows.

**Kept here** — the actual gap: all fal.ai calls and tier selection, `scripts/retopo_bake.py`'s bake
technique, the mobile budget thresholds, the LOD-chain recipe and texture-packing decisions for
AI-sourced meshes, both validator scripts, and the entire 2D branch (category H — `blender-scripting`
has no involvement in 2D work whatsoever).

Note for maintainers: `blender-scripting` currently has **no** Decimate/LOD content of its own. The
chained-Decimate recipe lives in [FINISHING-PIPELINE.md](FINISHING-PIPELINE.md) and is this skill's
own material, executed through `blender-scripting`'s headless conventions.

## Validation is a script, not a judgment

The last step of every 3D branch is `scripts/validate_asset.py`; of every 2D branch,
`scripts/validate_2d_asset.py`. **These scripts are the source of truth.** A file that exists, a
render that looks fine, and the agent's own reading of a mesh are all irrelevant — an asset is done
when the validator prints `ALL CHECKS PASSED` and exits zero, and not before.

```bash
blender --background asset.blend --python skills/game-asset-director/scripts/validate_asset.py
python3 skills/game-asset-director/scripts/validate_2d_asset.py --image sprite.png --target 512x512
```

Never report a validator result you did not actually run, and never paraphrase a `FAIL` into a
qualified pass.

**On failure:**

- **Free retry** — adjust this skill's own script parameters (target tri count, bake margin, texture
  size, canvas size) for up to ~2 rounds, then stop and report specifics.
- **Paid retry** — a defect needing a *new generation* (wrong base topology, wrong composition) stops
  immediately and reports to the user before spending again. Same discipline as
  `~/.claude/infrastructure/fal-ai.md`'s "Exhausted balance" rule: stop and ask, never retry-loop
  against a paid endpoint.

## Files

| Read when | File |
|---|---|
| Picking or calling an AI-mesh endpoint (IDs, prices, tiers, auth) | [AI-MESH-SERVICES.md](AI-MESH-SERVICES.md) |
| Retopo/bake, mobile polycount and texture budgets, LOD chain, ORM packing | [FINISHING-PIPELINE.md](FINISHING-PIPELINE.md) |
| Any 2D asset (category H) or a pack's reference-image pass (category D) | [SPRITE-PIPELINE.md](SPRITE-PIPELINE.md) |
