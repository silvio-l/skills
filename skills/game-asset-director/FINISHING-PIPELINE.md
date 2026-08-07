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
3. **Decimate the (cleaned) duplicate** (Collapse) down to the target triangle count, then run the
   **post-decimation cleanup pass** below. This is the low-poly cage — its own UVs are about to be
   thrown away, so the UV damage from this step does not matter.
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

### Post-decimation cleanup (required, and not the same pass as step 2)

Step 2 cleans the mesh *before* decimation; Collapse Decimate then leaves its own debris behind — long
needle-thin triangles, degenerate faces, coplanar slivers. Those are what produce shading artifacts,
z-fighting sparkle at distance, and poor vertex-cache behaviour on device, and they survive every check
in `validate_asset.py`. Run a second, shorter pass **after** the decimate and **before** the Smart UV
Project, in this order:

1. **Merge by distance** (weld) at the same threshold step 2 used.
2. **Dissolve degenerate** faces and zero-area geometry.
3. **Limited dissolve at a small angle (~1°)** to collapse coplanar slivers into their neighbours.
4. **Re-triangulate** any n-gons steps 2–3 produced, so `topology` still passes.

It costs seconds and removes a few percent of the triangles the decimate produced. **Set
`--target-tris` above the class floor, not at it, and re-count after the cleanup rather than after the
decimate.** `validate_asset.py`'s `tri-budget` enforces a *range* (building 8,000–20,000, and so on),
so decimating to exactly 8,000 and then shaving 3–5% lands at ~7,600 and fails a check the asset would
otherwise have passed. `scripts/retopo_bake.py` currently runs `quads_convert_to_tris()` inside
`cleanup_mesh()`, i.e. **before** the decimate — that is not this pass. Until the script grows it, run
the four operators above on the low-poly cage explicitly.

### Known gap: this cleanup does not catch spiky non-manifold survivors fused into the main mesh

Confirmed on a hero building sourced from a raw AI mesh with 33.20% non-manifold verts and 573
disconnected islands pre-cleanup: after decimate + the four-step cleanup above + bake, a region of
thin, spiky, degenerate geometry near a shopfront awning survived and baked into a visible
wire/sail-shaped artifact. It was **not** a separable junk island (a `bmesh` connected-component
traversal from a raycast hit found it topologically fused to 90% of the mesh — 14,195 of 15,814
faces — so it can't be selected and deleted in isolation), and it was confirmed geometric, not a
texture problem, via a clay (untextured) render of the same framing. Two remediation attempts both
failed: masked texture-space inpainting was ruled out before touching pixels once a UV-coordinate
back-projection showed the auto-packed atlas has no spatial locality (a small screen region maps to
hundreds of scattered, unrelated islands elsewhere in the same texture); and localized Laplacian
smoothing of the affected verts made it *worse*, because moving vertices after the bake desyncs the
already-UV-mapped texture from the new geometry (visible as harsher, stretched distortion) without
a re-bake to match. **The weld + dissolve-degenerate + limited-dissolve + re-triangulate sequence in
this section is tuned for coplanar/needle-thin decimate debris, not for relaxing a spiky, fused,
non-manifold survivor region** — that needs either a targeted local remesh of just the affected
vertex group (bounded, not yet implemented) or catching it earlier, before decimation fuses it to
clean geometry. Re-bake is mandatory after any geometry edit made downstream of a bake — never move
verts against a texture that already has UVs baked onto the old positions.

### Considered and rejected: a voxel-remesh prepass before the decimate

A widely circulated AI-mesh pipeline puts a **voxel remesh** in front of the decimate — voxel size
`0.0015` of the object's largest dimension — to fuse a raw generator output described there as ~2
million triangles of messy, overlapping shells into one manifold surface before the triangle budget gets
spent. **Do not add it to this skill's default pipeline.** It fixes an input pathology the vendors routed
here do not have.

Measured directly on this skill's own raw Rodin source (`building.glb`: one mesh object, 36,201 tris,
dimensions 1.618 × 1.624 × 1.817), Voxel Remesh at that ratio and its neighbours:

| Voxel size (fraction of max dim) | Absolute voxel size | Result |
|---|---|---|
| — (untouched source) | — | 36,201 tris |
| 0.0030 | 0.00545 | 937,004 tris |
| **0.0015** (the published value) | 0.00273 | **3,769,340 tris** |
| 0.0005 | 0.00091 | 34,082,592 tris |

Nothing was fused and nothing was cleaned: the mesh was re-tessellated 26–940× denser and would have to
be decimated straight back down, spending minutes of compute for no gain. Rodin returns quad topology at
an already-reasonable density — 36K tris is close to a usable budget on its own — so there is no shell
soup to collapse. The fragmentation this skill's sources *do* have (383 loose parts, 8,473 boundary
edges) is a welding problem, which is exactly what step 2 treats.

**When to test it again:** a newly routed generator whose *untouched* import comes back as overlapping
or interpenetrating shells. Two cheap checks on the raw import decide it — a large disconnected
loose-part count, and a raw triangle count far above the target budget (>500K on a hero asset is the
signal). Then size the voxel to *that* mesh's real dimensions and measure the result; do not copy
`0.0015` across, since it is tuned to a different generator's output at a different scale. Until such a
vendor is actually routed here and measured, this stays rejected — not pending, and not quietly adopted.

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
- `cage_extrusion` is a two-sided failure mode, not just "bigger is safer": too small and the cage
  doesn't enclose a bulging high-poly surface (cornices, overhangs), so rays miss outward; too large
  and the cast ray *overshoots* a concave recess (a window reveal, an oval wall opening) and misses
  the high-poly surface sitting *inside* it, baking a jagged black hole into the color/normal texture
  at exactly that recess instead. Confirmed by direct comparison on a hero building: the old 5%-of-
  extent default (`retopo_bake.py`, since fixed) produced black holes in both dormer window frames and
  an oval gable window; dropping to 1% of extent on the identical mesh fixed it with no new misses at
  the bulging details. `retopo_bake.py`'s current default is 1% of the object's largest dimension
  (min 0.005) — scale it with the mesh, do not hardcode a fixed value for every asset, and drop it
  further than the default on a mesh with deep/narrow recesses.
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

**Name and parent the chain so the engine builds the LOD group itself.** Produce `<name>_LOD0` …
`<name>_LODn` as sibling children of an empty named `<name>`, all sharing LOD0's single material and
baked texture set. Unity's model importer recognises that exact convention — a common root with
`_LOD0.._LODn` suffixed children — and **creates the LODGroup component automatically on import**, so
dropping the GLB into the project yields a distance-switching prefab with zero per-asset setup. Getting
the naming wrong costs nothing at export time and costs manual LODGroup wiring on every single asset
afterwards, which is why it is worth being pedantic about.

**Rename before you create the root empty — `retopo_bake.py`'s output name will collide otherwise.**
The script names its result `<high-poly name>_LOD0` and leaves the high-poly source in the scene under
its own name. So if the source is `TownHall_HighPoly`, LOD0 is `TownHall_HighPoly_LOD0` and the root
empty would have to be `TownHall_HighPoly` — a name already taken. Blender resolves that silently by
appending `.001`, which the GLTF name mapping below turns into `TownHall_HighPoly001`, and Unity's
root-plus-`_LODn` match then fails with no error anywhere. Fix it before building the chain: rename the
LOD objects to the **asset** name (`TownHall_LOD0` …) and either rename the high-poly source out of the
way or exclude it from the export scene. Then create the empty as `TownHall`.

Two boundaries on this:

- **The ~75% per level above is this skill's ratio; keep it.** A published reference pipeline for
  background village houses used 39k / 15k / 5k / 1.5k, i.e. ~60–70% per step off a LOD0 two to five
  times this skill's whole building budget (8,000–20,000). Those numbers are that pipeline's example at
  its own budget, not a replacement for the table above.
- **Not every asset class needs the chain.** It pays for hero and background assets seen at genuinely
  variable distance. A UI-adjacent prop, an asset only ever shown at one fixed distance, or anything
  already at the bottom of its budget does not need four levels — say so rather than generating them.
- **The flat ratio is a starting point, not a guarantee — verify every level by rendering it, the same
  rule that applies to LOD0.** Collapse Decimate can fail catastrophically well before the table's
  numbers on a mesh with many thin protruding features (a clock tower, dormers, chimneys — anything
  that reads as a spike rather than a blob): confirmed on a hero building where the ~75%-per-level
  chain (LOD0 15.8K → LOD1 ~3.9K → LOD2 ~1K) produced a *recognizable* LOD1 but a LOD2 that rendered as
  two or three giant inverted/degenerate triangles with the building's geometry gone — not simplified,
  destroyed. This was not a chaining artifact (decimating straight from LOD0 to the same ~1K target
  failed identically) and not fixed by the `delimit={'NORMAL'}` option. What worked: decimating LOD2
  **directly from LOD0** (never through LOD1, so error from one aggressive step never compounds into
  the next) at a target found by testing render output at a few candidate tri counts — 2,200 tris held
  up, 1,200 did not, on this asset. There is no formula to compute the safe floor in advance; render
  each LOD level before shipping it, exactly as FINISHING-PIPELINE.md and SKILL.md already require for
  LOD0, and raise the target-tris for that level until it stops breaking.

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

### What the caller still owes the exporter

Two things sit on this side of the delegation line — they are texture prep and scene state, not export
settings, so doing them here does not reopen the export path.

**1. Export copies of the textures, produced non-destructively.**

- **Base color → JPEG, quality ~92.** Albedo tolerates it and the size saving is the largest single win
  in the whole export step.
- **Normal map → PNG, always.** JPEG's block artifacts on a normal map turn into visible shading noise
  across the whole surface. There is no quality setting that makes this safe.
- **Downscale only where the bake was authored above the export target.** This skill bakes at
  `--texture-size` (default 2048) against a 2K standard / 2K–4K building budget, so at the default there
  is nothing to shrink; the win exists when a building was deliberately baked at 4K and ships at 2K. A
  reference pipeline baking at 8K and exporting at 4K, together with the JPEG/PNG split above, measured
  ~80% off its GLB sizes with no visible loss at gameplay distance — the same *ratio* does not transfer,
  the *technique* does.
- **The full-resolution bake stays in the working `.blend`.** Swap the material's image nodes to the
  export copies, export, swap back. Only the exported file is reduced, so a re-export at another size
  stays possible without re-baking.

**2. Select and unhide the whole hierarchy before calling the exporter.** glTF's "Selected Objects"
option does **not** pull in the children of a selected root, and hidden objects drop out silently. Either
mistake produces a ~180-byte GLB that reads as a mysterious exporter failure rather than a selection bug.
With the LOD chain above this is the default trap: selecting the `<name>` root empty alone exports
nothing. Select every `_LOD*` child explicitly and unhide them first.
