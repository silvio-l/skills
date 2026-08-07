# Finishing Pipeline (3D)

What turns a raw AI mesh into a shippable mobile asset. Every **category B (hero-tier)** mesh from
[AI-MESH-SERVICES.md](AI-MESH-SERVICES.md) goes through this in full, as does any `blender-scripting`
output that has to hit a polycount budget. A simple, non-ornate **category C** prop may take the
shorter route in "When a bare Decimate is enough (category C only)" instead.

## Why a bare Decimate fails on a hero asset

The obvious move — import the AI mesh, add a Decimate modifier, drop it to the target triangle count,
ship it — **corrupts the texture** on a hero asset, and does so worse the closer you get to real
mobile polycounts. Decimate collapses edges without regard for the UV layout: the seams move, shells
distort, and the texture that was mapped to the dense mesh smears across the simplified one. The
geometry looks acceptable in a wireframe view and the material looks broken in the render, which is
exactly the failure mode that gets shipped because nobody re-checked the textured view.

This was confirmed in real production testing, not derived from theory: naive Decimate at production
polycounts was the failure; the fix below was what actually worked.

This is a scoped claim, not an absolute one. It holds where texture fidelity after simplification
carries the asset — hero assets, and anything with complex or organic topology where naive Decimate
visibly breaks the UVs. It does **not** hold for every asset class: see "When a bare Decimate is
enough (category C only)" below, where a bare Decimate pass is a sanctioned, faster path.

## The fix: retopo → bake

Do not simplify the textured mesh. Build a **new** low-poly mesh, give it its own clean UVs, and
**bake** the high-poly detail onto it as image maps.

1. **Duplicate** the high-poly mesh. The original is the bake source and must stay untouched.
2. **Weld + close small gaps** on the duplicate (merge-by-distance, then Fill Holes on the resulting
   boundary loops). Raw AI-mesh output is routinely exported as disconnected per-chunk triangle soup —
   surfaces that touch geometrically but were never vertex-welded — and this is *before* decimation
   makes it worse. Confirmed by direct measurement on a real Rodin HighPack asset: 383 disconnected
   mesh components and 8,473 open boundary edges (14.5% of all edges) already present at the raw
   36,201-tri source. Skipping this step is what turns into a >1,000-island UV explosion two steps
   later (see "Why UV shell count explodes" below) — it is not a margin problem or a Smart UV Project
   angle-limit problem, both of which were checked and ruled out on the same asset.
3. **Decimate the (cleaned) duplicate** (Collapse) down to the target triangle count. This is the
   low-poly cage — its own UVs are about to be thrown away, so the UV damage from this step does not
   matter.
4. **Smart UV Project** the low-poly copy. A fresh, non-overlapping, 0–1-space layout with real
   padding. This is the layout the baked textures will be authored into.
5. **Cycles bake, "Selected to Active"** — select the high-poly, make the low-poly the active object,
   and bake `NORMAL`, `AO`, and a color pass from the high-poly onto the low-poly's new UVs.
6. **Wire the baked images** into the low-poly's Principled BSDF (base color → Base Color, normal →
   Normal Map node → Normal, AO into the ORM pack or an AO multiply).

The high-frequency detail now lives in the normal map instead of the geometry, which is precisely the
trade a mobile GPU wants: cheap triangles, one texture fetch.

`scripts/retopo_bake.py` implements all six steps headlessly:

```bash
blender --background high_poly.blend \
  --python skills/game-asset-director/scripts/retopo_bake.py \
  -- --target-tris 6000 --texture-size 2048 --margin 0.004 --output finished.blend
```

`--margin 0.004` (~8 texels at 2048px) is the default; pass `--skip-cleanup` to disable step 2 for a
source already known to be a single clean manifold mesh. Four parameters carry most of the quality:
`--target-tris` (the budget below), `--texture-size` (the budget below), `--margin` (UV island padding
— too small and adjacent islands bleed into each other at lower mip levels, showing up as seams
on-device but not in the editor), and the cleanup pass (`--weld-distance`, `--hole-fill-sides`).

### Manual escalation when the automated retopo is not good enough

`retopo_bake.py`'s duplicate → Decimate → Smart UV Project → bake technique is automated and headless,
which is what makes it the default — not a claim that it produces the best possible topology. On a
hero asset carrying a lot of fine ornamental geometry it can come back with topology that is simply
unsatisfactory, and the automated knobs above will not rescue it. The escalation path is manual, GUI,
and real-world proven; name it rather than treating the automated route as the only option:

- **[RetopoFlow](https://github.com/CGCookie/retopoflow)** — free Blender addon for hand-guided
  retopology. This is the route practitioners take for highly optimized or handcrafted topology,
  particularly on mobile targets, instead of relying purely on automated remesh.
- **"Game Ready Modeling Tools" (G-Ready)**, on Superhive / Blender Market — a paid bake addon:
  one-click cage bake, "Smart Matrix Bake", roughly 10–15× faster baking, and built-in LOD generation.

Both are outside this skill's headless path: they need a human in the Blender GUI. Escalate to them
deliberately and say so, rather than shipping topology the automated pass got wrong.

### Why UV shell count explodes — and why margin does not fix it

The intuitive read of a badly fragmented bake (huge amount of black dead space around thousands of
tiny UV islands) is "the margin is too large." That was tested directly on a real showcase asset and
falsified: re-running Smart UV Project on the same low-poly mesh at `margin=0.003` instead of `0.02`
produced the *exact same* shell count (1,349). Margin controls the padding *around* each island; it
has no effect on *how many* islands Smart UV Project creates in the first place. Shell count is fixed
by mesh connectivity — Smart UV Project cannot merge UV islands across disconnected mesh components —
and the loose-part count on that asset's raw high-poly source (383) was already in the same order of
magnitude as its final shell count, confirming the source mesh's fragmentation as the actual driver.
This is exactly why step 2 (weld + fill-holes) exists as a pipeline step rather than a `--margin` or
`--angle-limit` tuning knob: it treats the cause, not the symptom.

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
- `mesh.remove_doubles` / `mesh.fill_holes` are EDIT-mode operators too, same wrapping as
  `smart_project` above. `fill_holes(sides=0)` closes boundary loops of any size — including a
  legitimate open bottom on a prop that was modeled that way on purpose. Pass `--hole-fill-sides` with
  a finite limit, or `--skip-cleanup`, when that matters for a given asset.

## When a bare Decimate is enough (category C only)

For a **simple, non-ornate background prop** — a chair, a crate, a table — a Decimate modifier applied
directly to the already-textured AI mesh is a legitimate and much faster path. No retopology, no
re-UV, no rebake. This is documented practice, not a shortcut invented here: a real shipped game asset
(a Meshy-generated chair, taken into the Eon Editor with collision) was finished exactly this way, in
two Decimate passes — ratio 1 → 0.1, then a later pass → 0.5 — with the file going 64 MB → 11 MB →
~2 MB after a manual 2K → 512 texture resize → 1.1 MB final.

The gate is the same render-and-look-at-it discipline this skill requires everywhere else (SKILL.md,
"Validation is necessary, not sufficient"): **spot-check the textured render before applying each
Decimate pass.** If the material still looks right, apply and continue; the moment UVs visibly break,
stop and fall back to the retopo → bake technique above. The validator still runs afterwards, with the
correct `--class`, exactly as on any other route.

Do not extend this to:

- **Category B hero assets.** Texture fidelity after simplification is precisely what carries a hero
  asset — retopo → bake stays mandatory there.
- **Complex or organic topology**, at any category, where naive Decimate visibly breaks the UVs.

## Mobile budgets

Triangle budgets, per asset class. These are the numbers `scripts/validate_asset.py` enforces — the
script is the source of truth, this table is the rationale.

| Asset class | Triangle budget |
|---|---|
| Character / hero | 3,000 – 10,000 tris |
| Background / mid-ground prop | 100 – 2,000 tris |
| Building (hero architecture) | 8,000 – 20,000 tris |
| Per LOD level | **~75% triangle reduction** from the previous level |

`building` is its own class, not "character with a bigger number" — a hero building carries more
silhouette-defining detail than a character (gables, dormers, a tower, balconies, facade trim) and
typically reads at a larger screen size for longer. Forcing a building through the character budget
(3,000–10,000) is what produced the aggressive 36,201→8,000 decimation in the showcase asset that
first exposed this gap — with headroom to 20,000 tris, a hero building does not need to shed 78% of
its triangles to pass validation.

Texture budgets:

| Case | Size |
|---|---|
| Standard (hero, character, near-camera prop) | 2K (2048×2048) |
| Building (hero architecture) | 2K–4K (2048–4096) |
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
| `manifold` | Every edge shared by exactly 2 faces, within a small tolerance for a legitimate open bottom — fails on holes or self-intersecting geometry |
| `uv-shells` | Every island inside 0–1 space; no island stacked on another |
| `uv-shell-density` | Average faces per UV island above a floor — fails on confetti-fragmented unwraps even when every individual island is technically valid |
| `uv-padding` | Tightest inter-island gap, measured in **texels** at the map size (default minimum 2) — this is what verifies `--margin` survived |
| `texture:*` | Power-of-two, square, and inside the class's size range |

`manifold` and `uv-shell-density` exist because of a real gap found by running this pipeline
end-to-end on a showcase asset: `tri-budget`, `topology`, `uv-shells`, and `uv-padding` all passed on
an asset with an open, hollow roof cavity and a bake with ~1,300 confetti-sized UV islands — every
individual check was narrowly correct and the combination still printed `ALL CHECKS PASSED` on a
visibly broken asset. A **validator pass on a visibly broken asset is a validator bug to fix, not a
judgment call** — see SKILL.md's "Validation is necessary, not sufficient."

Known boundaries, so nobody mistakes a pass for more than it is: the stacking test compares island
*bounding boxes*, so it catches duplicated and buried islands but not exactly-coincident mirrored UVs
(those weld into a single island, and mirrored UVs are often intentional anyway). Padding is likewise
a bounding-box gap, deliberately set to a lax default so a tightly interlocked pack does not
false-fail. Neither test rasterizes texels. `uv-shell-density` is an average, so it can still miss a
mesh with a few huge islands and many small ones — it catches the systemic-fragmentation case it was
built for, not every possible bad packing. `--class` is yours to pass correctly — validating a
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
