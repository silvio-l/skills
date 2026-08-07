# Finishing Pipeline (3D)

What turns a raw AI mesh into a shippable mobile asset. Every mesh from
[AI-MESH-SERVICES.md](AI-MESH-SERVICES.md) goes through this; so does any `blender-scripting` output
that has to hit a polycount budget.

## Why a bare Decimate fails

The obvious move — import the AI mesh, add a Decimate modifier, drop it to the target triangle count,
ship it — **corrupts the texture**, and does so worse the closer you get to real mobile polycounts.
Decimate collapses edges without regard for the UV layout: the seams move, shells distort, and the
texture that was mapped to the dense mesh smears across the simplified one. The geometry looks
acceptable in a wireframe view and the material looks broken in the render, which is exactly the
failure mode that gets shipped because nobody re-checked the textured view.

This was confirmed in real production testing, not derived from theory: naive Decimate at production
polycounts was the failure; the fix below was what actually worked.

## The fix: retopo → bake

Do not simplify the textured mesh. Build a **new** low-poly mesh, give it its own clean UVs, and
**bake** the high-poly detail onto it as image maps.

1. **Duplicate** the high-poly mesh. The original is the bake source and must stay untouched.
2. **Decimate the duplicate** (Collapse) down to the target triangle count. This is the low-poly cage
   — its own UVs are about to be thrown away, so the UV damage from this step does not matter.
3. **Smart UV Project** the low-poly copy. A fresh, non-overlapping, 0–1-space layout with real
   padding. This is the layout the baked textures will be authored into.
4. **Cycles bake, "Selected to Active"** — select the high-poly, make the low-poly the active object,
   and bake `NORMAL`, `AO`, and a color pass from the high-poly onto the low-poly's new UVs.
5. **Wire the baked images** into the low-poly's Principled BSDF (base color → Base Color, normal →
   Normal Map node → Normal, AO into the ORM pack or an AO multiply).

The high-frequency detail now lives in the normal map instead of the geometry, which is precisely the
trade a mobile GPU wants: cheap triangles, one texture fetch.

`scripts/retopo_bake.py` implements all five steps headlessly:

```bash
blender --background high_poly.blend \
  --python skills/game-asset-director/scripts/retopo_bake.py \
  -- --target-tris 6000 --texture-size 2048 --margin 0.02 --output finished.blend
```

Three parameters carry most of the quality: `--target-tris` (the budget below), `--texture-size` (the
budget below), and `--margin` (UV island padding — too small and adjacent islands bleed into each
other at lower mip levels, showing up as seams on-device but not in the editor).

### Bake gotchas that produce silently wrong output

- The bake target image node must be **selected and active** in the low-poly material's node tree.
  Cycles bakes into the active image node; get this wrong and the pass writes into the wrong image or
  nothing at all, with no error.
- The color pass is `type='DIFFUSE'` with `pass_filter={'COLOR'}` — without the filter, scene lighting
  is baked into the albedo. `'EMIT'` is the alternative for a pure unlit color transfer. There is no
  `type='COLOR'`.
- `render.engine` must be `'CYCLES'`; Eevee cannot bake selected-to-active.
- `cage_extrusion` must be large enough to enclose the high-poly surface, or rays miss and the bake
  comes back with holes. Small models need a small value; scale it with the mesh, do not hardcode it
  for every asset.
- `bpy.ops.uv.smart_project()` needs EDIT mode with faces selected. This is one of the operators
  `blender-scripting/SKILL.md`'s "`bpy.ops` works fine in background" note does *not* cover — wrap it:
  `mode_set(mode='EDIT')` → `mesh.select_all(action='SELECT')` → project → back to `'OBJECT'`.
- Decimate `COLLAPSE` takes a `ratio` in 0–1, **not** a triangle count. Compute the current triangle
  count as `sum(len(p.vertices) - 2 for p in mesh.polygons)`, then `ratio = target / current`.

## Mobile budgets

Triangle budgets, per asset class. These are the numbers `scripts/validate_asset.py` enforces — the
script is the source of truth, this table is the rationale.

| Asset class | Triangle budget |
|---|---|
| Character / hero | 3,000 – 10,000 tris |
| Background / mid-ground prop | 100 – 2,000 tris |
| Per LOD level | **~75% triangle reduction** from the previous level |

Texture budgets:

| Case | Size |
|---|---|
| Standard (hero, character, near-camera prop) | 2K (2048×2048) |
| Small prop | 1K (1024) or 512 |
| Every case | **Power-of-two dimensions, required** |

**ORM channel packing** — pack ambient Occlusion into R, Roughness into G, Metallic into B of a single
texture. Three grayscale maps become one RGB fetch: fewer texture samplers, less GPU memory, one less
file per asset. This is the standard glTF metallic-roughness layout (roughness in G, metallic in B),
so the packed map maps directly onto the exported material without a shader hack.

## What `validate_asset.py` actually checks

Run it after every 3D branch; its exit code is the verdict.

```bash
blender --background finished.blend \
  --python skills/game-asset-director/scripts/validate_asset.py -- --class character
```

| Check | What it enforces |
|---|---|
| `tri-budget` | Triangle count inside the class range above |
| `topology` | Quads and tris only — n-gons and degenerate faces fail |
| `uv-shells` | Every island inside 0–1 space; no island stacked on another |
| `uv-padding` | Tightest inter-island gap, measured in **texels** at the map size (default minimum 2) — this is what verifies `--margin` survived |
| `texture:*` | Power-of-two, square, and inside the class's size range |

Known boundaries, so nobody mistakes a pass for more than it is: the stacking test compares island
*bounding boxes*, so it catches duplicated and buried islands but not exactly-coincident mirrored UVs
(those weld into a single island, and mirrored UVs are often intentional anyway). Padding is likewise
a bounding-box gap, deliberately set to a lax default so a tightly interlocked pack does not
false-fail. Neither test rasterizes texels. `--class` is yours to pass correctly — validating a
character as a prop is a green run that means nothing.

## LOD chain

Chained Decimate on the **finished, baked** LOD0 — never on the high-poly source, and never before the
bake, since every LOD level shares LOD0's baked texture set and therefore its UV layout. Collapse
Decimate preserves UVs well enough for a mip-distance mesh; that is the whole reason the bake happens
first.

Each level drops ~75% of the previous level's triangles (`ratio ≈ 0.25` per step, relative to the
level it is derived from):

| Level | Tris (from a 8,000-tri character LOD0) |
|---|---|
| LOD0 | 8,000 |
| LOD1 | ~2,000 |
| LOD2 | ~500 |
| LOD3 | ~125 (drop it and use a billboard instead below this) |

Follow `blender-scripting/techniques.md`'s modifier idiom for each step: add the modifier, set the
object active via `bpy.context.view_layer.objects.active`, then `bpy.ops.object.modifier_apply(...)`.
Link new objects with `bpy.context.scene.collection`, not `bpy.context.collection`, per
`blender-scripting/SKILL.md`'s collection-linking rule. Re-run `validate_asset.py` on the chain.

*Maintainer note:* `blender-scripting` has no Decimate/LOD content of its own — this recipe is this
skill's material, executed through `blender-scripting`'s headless conventions. If a Decimate/LOD
section is ever added there, this section should shrink to a pointer.

## Export is not reimplemented here

Final FBX/GLTF/OBJ/STL/PLY export goes through `blender-scripting/export-and-errors.md`'s
version-safe functions — `export_gltf`, `export_fbx`, `export_obj`, `export_stl`, `export_ply` — each
`hasattr`-guarded against the 4.0 `wm.*_export` / legacy `export_scene.*` split. That file also owns:

- the **GLTF settings table** (`export_format='GLB'`, `export_apply=False`, Draco off at export time),
- the **material export survival matrix** — which is the second reason the bake is mandatory:
  procedural Noise/Voronoi textures and Color Ramps do not survive GLTF export at all, baked image
  textures and baked normal maps do,
- the **name-mapping table** (spaces → underscores, `Sphere.003` → `Sphere003`) — check names in the
  exported file before referencing them downstream,
- the post-export `gltf-transform` order (`resize` → `webp` → `draco`, never `optimize`).

Do not write a second export path. Do not re-derive those settings.
