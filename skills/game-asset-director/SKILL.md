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
| **B. Hero / character / organic / building** | character, creature, boss, hero prop, unique named asset, a structure that genuinely needs free-camera rotation — **read the fixed-camera rule below before sending a building here** | `fal-ai/hyper3d/rodin` with **HighPack** (quad topology + PBR + 4K, ~$1.20). If a retry is needed on a different vendor, try `tripo3d/tripo/v2.5/image-to-3d` HD first — independently benchmarked stronger geometry/low-poly output than Meshy, see AI-MESH-SERVICES.md's "Choosing a tier". Meshy (`fal-ai/meshy/v6-preview/image-to-3d`) is a fallback only where its specific style fits better, not a default second try. → `scripts/retopo_bake.py` → LOD chain → validate **with `--class building` for a structure, not `--class character`** — see FINISHING-PIPELINE.md's budget table. **Budget manual Blender retouch as part of this route:** image-to-3D cannot guarantee occluded geometry (dormer interiors, balcony undersides, similar detail on ornate one-off architecture) comes back defect-free — see AI-MESH-SERVICES.md's "Known limitation". |
| **C. Complex background prop** | one-off statue, furniture, "barrel with graffiti" — visible but not hero-tier | `tripo3d/tripo/v2.5/image-to-3d` with HD textures. Drop to `fal-ai/hunyuan3d/v2/turbo` or `fal-ai/trellis` **only** for high-volume far-background filler where the user signals volume over per-asset fidelity. → finishing pipeline as B, except that a simple, non-ornate prop may take the cheaper naive-Decimate path with a visual spot-check instead of the full retopo/bake — see FINISHING-PIPELINE.md's "When a bare Decimate is enough (category C only)". |
| **D. Asset pack** | "enemy pack", "matching set", any request for visual consistency across several assets | Generate a consistent **reference-image set first** via `fal-ai/nano-banana/edit` (or `fal-ai/flux-pro/kontext`), then convert each image through B or C by its own hero-vs-background status. Not Meshy's web-only "3D agent" — see [AI-MESH-SERVICES.md](AI-MESH-SERVICES.md). |
| **E. PBR texture / material only** | "make this look like rusted iron", no new mesh | Procedural Principled-BSDF graph via `blender-scripting`. AI photo-to-PBR only when the user supplies an actual reference photo. |
| **F. App icon** | a platform app icon specifically | Delegate entirely to `app-icon-director`. Nothing from this skill applies. |
| **G. LOD-only on an existing mesh** | "add LODs to this" | Chained Decimate per [FINISHING-PIPELINE.md](FINISHING-PIPELINE.md), executed headlessly through `blender-scripting`'s conventions, then re-validate. |
| **H. 2D game asset** | sprite, item/UI icon, portrait, tile art — anything flat that is not an app icon | `fal-ai/nano-banana/edit` (or `fal-ai/flux-pro/kontext`) → `fal-ai/birefnet` where transparency is needed → `fal-ai/esrgan` to the target in-engine resolution → `scripts/validate_2d_asset.py`. See [SPRITE-PIPELINE.md](SPRITE-PIPELINE.md). |

### Before generating any reference image, check for a named style profile

Categories B, C, D and H all begin by generating or choosing a **reference image**, and that image sets
the quality ceiling for everything downstream — no retopo, bake, or validator pass recovers art
direction that was never in it. So, after the category is decided and before the first image is
generated:

1. Read the request for a **named or clearly implied art style** — a period, genre or named look, a
   style the project has already established, or reference images the user supplied.
2. If the user supplied reference images, use them. Otherwise check
   [REFERENCE-STYLES.md](REFERENCE-STYLES.md) for a matching profile and fold **four to eight concrete
   cues** from it (materials, roofline, ornament placement, palette, lighting) into the image prompt.
3. If neither exists, ask for a reference image rather than prompting from adjectives. "Historic",
   "charming", "European" are not art direction and produce generic geometry.

Name the profile in the announcement, next to the category and tool. A profile never changes *which*
category a request routes to — it changes only what the reference image looks like.

### Fixed-camera structures go to category H (2D), not category B (3D)

Before routing any building or structure to category B, establish what the camera actually does. If
the asset is only ever seen from a **fixed or stepped isometric camera** — the common case for
city-builder and strategy mobile games, which typically allow stepped rotation around a fixed
elevation but never a free orbit — **route it through category H by default.** Use category B only
when the asset genuinely needs free-camera rotation or in-engine 3D interaction: collision meshes,
physics, a rotatable inspect view.

This is a requirements question, not an ambiguity call — the ambiguity rule below does not override
it. Three reasons, in order of weight:

1. **No reconstruction step means no unseen-geometry defect.** Category B reconstructs a 3D shape from
   images and therefore has to invent everything the camera never saw; category H never leaves 2D, so
   the defect class documented in AI-MESH-SERVICES.md's "Known limitation" cannot occur at all.
2. **Cheaper.** A single `fal-ai/flux-pro/v1.1-ultra` reference at ~$0.06 versus ~$1.20 for a Rodin
   HighPack generation, before any Blender time.
3. **Faster.** No retopo, no bake, no LOD chain, no two-angle render check.

Measured on the ornate hero town hall (dormers, wrought-iron balconies, clock tower, corner turret)
this rule came out of: the isometric reference image alone already cleared the AAA bar — clean
dormers, correct wrought-iron balcony detail, sharp facade trim — while three separate 3D
reconstructions of that same subject, across two vendors, all came back with a hollow roof cavity and
warped balconies.

**Qualification: those defects were judged in a studio close-up, and that is the wrong bar.** The
renders behind the paragraph above were isolated single-subject close-ups at roughly 2.2× the asset's
bounding radius on a neutral backdrop. The same finished, baked building was afterwards re-rendered the
way a city-builder actually shows it — three instances on a ground plane at ~5.5–8× the bounding radius,
warm low-angle golden-hour key plus a cool dusk fill — and at that distance neither the warped balconies
nor the roof cavity read as broken; the asset looks coherent and detailed. Reasons 2 (cheaper) and 3
(faster) are unaffected and keep H the default. Reason 1 also stays structurally true — 2D has no
reconstruction step, so it cannot have that defect class at all — but *how much that is worth* depends
on whether the defect is visible at the camera distance the game actually uses, and on this asset it was
not. Concretely:

- **A defect that survives a scene-context render is real** and does block: keep the asset in H, or fix
  it manually before shipping it as B.
- **A defect that disappears at the real viewing distance is not a defect for that use case.** It is not
  grounds for rerouting a 3D asset to 2D on its own, and it is not something to report to the user as a
  broken pipeline.

Either way the decision comes from the distance-and-lighting test described in "Validation is necessary,
not sufficient" below — never from a close-up alone.

### Ambiguity rule

When a request sits between two categories, pick the higher-quality tier and say so in the
announcement. An over-specified background prop is a small cost; an under-specified hero asset is a
visible defect. This resolves *which tier*; it never overrides the fixed-camera rule above, which
resolves *which dimension* — a hero building on a fixed camera is a 2D asset at the highest quality
tier, not a 3D one.

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

## Validation is necessary, not sufficient

The last step of every 3D branch is `scripts/validate_asset.py`; of every 2D branch,
`scripts/validate_2d_asset.py`. **These scripts are the floor, not the ceiling.** `ALL CHECKS PASSED`
and exit zero is a hard requirement — never report an asset done without it, never report a validator
result you did not actually run, and never paraphrase a `FAIL` into a qualified pass. But it is not by
itself proof the asset is good.

This was found, not assumed: a real showcase asset (a hero building through Category B end-to-end)
printed `ALL CHECKS PASSED` — tri-budget, topology, UV shells, UV padding, textures — while the
rendered result had an open, hollow roof cavity and a bake wasted on ~1,300 confetti-sized UV islands,
both directly visible in a render and in the raw baked textures. The individual checks were each
narrowly correct; the combination still missed a defect any human would catch by looking at the
result. `manifold` and `uv-shell-density` were added to `validate_asset.py` specifically to close that
gap, but the lesson generalizes: **a validator pass on a visibly broken asset is a validator bug to
fix, not a judgment call to make in its place.**

So: render the finished asset from at least two angles and actually look at it before reporting a 3D
asset done — alongside the validator, not instead of it. If the render looks wrong and the validator
passed, the validator is missing a check; add one (following the pure-predicate pattern already in
`scripts/validate_asset.py`) rather than either shipping the visible defect or overriding the
validator's PASS with your own read of the mesh. The validator's word is still final on anything it
does check — this does not reopen "trust your own judgment over the script" for topology, budgets, or
UV correctness; it only means the checked set can be incomplete, and a render is how that gets found.

### Render at the distance and lighting the asset actually ships at

An isolated studio close-up is a *diagnostic* view, not the pass/fail bar. No shipping game shows a
building the way that render does, so judging pass/fail from it alone rejects assets that are fine and
sends work to a manual retouch nobody needed. Before calling a hero 3D asset failed — and **before
deciding to reroute it to category H** — render a **scene-context test** alongside the two diagnostic
angles:

- **multiple instances** of the asset, not one, on a **ground plane**, at the camera distance the game
  actually uses (for a city-builder/strategy view that is roughly 5–8× the asset's bounding radius; a
  single-subject diagnostic close-up sits near 2×),
- **scene-appropriate lighting** — the game's own key/fill setup, e.g. a warm low-elevation sun plus a
  cool ambient fill for a golden-hour village, not a neutral studio grey.

Then judge from that image. This was found the same way everything else in this section was: an asset
whose balcony and dormer defects looked disqualifying in a 2.2×-radius studio close-up read as coherent
and detailed at village distance under warm directional light, and would have been thrown away on the
close-up alone. The reverse case is equally binding — a defect still visible in the scene-context render
is real, blocks, and does not get argued down.

The two-angle render is also how category B's unseen-geometry defects get caught (see
AI-MESH-SERVICES.md's "Known limitation"). When one shows up, repairing it is part of the route, not a
pipeline failure to report:

- **A sealed cavity no camera will ever reach in the finished game** — a roof interior, a closed
  underside — gets **capped/patched in Blender**. That is a correct fix, not a workaround, and it is
  not an end-run around the validator: capping closes real non-manifold geometry, so the `manifold`
  check passes afterwards because the mesh has actually become manifold.
- **A genuinely visible defect** — warped balconies, torn facade trim — needs manual retouch in
  Blender, or a fresh generation from adjusted reference imagery (a paid retry: stop and ask first,
  per "On failure" below). Treat this as expected category B effort, not as a broken pipeline.

```bash
blender --background asset.blend --python skills/game-asset-director/scripts/validate_asset.py
python3 skills/game-asset-director/scripts/validate_2d_asset.py --image sprite.png --target 512x512
```

**On failure:**

- **Free retry** — adjust this skill's own script parameters (target tri count, bake margin, texture
  size, canvas size) for up to ~2 rounds, then stop and report specifics. **A manual Blender touch-up
  counts as a free-round action**, not a paid one: capping a cavity, patching a hidden gap, nudging a
  warped region, cutting a hole the generator closed over. On ornate hero geometry that pass is expected
  production reality rather than a pipeline failure — a second, independent practitioner hit the same
  class of content defect (a chimney whose interior hole never reconstructed) and fixed it exactly this
  way, by cutting the hole and repainting that part in Blender. Two free rounds still cap it: if the
  touch-up does not get there, stop and report rather than rolling into a new paid generation.
- **Paid retry** — a defect needing a *new generation* (wrong base topology, wrong composition) stops
  immediately and reports to the user before spending again. Same discipline as
  `~/.claude/infrastructure/fal-ai.md`'s "Exhausted balance" rule: stop and ask, never retry-loop
  against a paid endpoint.

## Output location and cleanup

Every route produces two kinds of files, and they do not belong in the same place:

- **Deliverables** — the finished, validated asset (exported GLB/FBX/OBJ, baked textures, 2D
  sprites/icons) — go into the calling project's actual asset directory, never a scratch/temp path.
  If the project's asset-directory convention is not obvious from context (Unity's `Assets/`,
  Godot's project tree, a repo's own `art/`/`assets/` folder), ask once before the first export
  rather than guessing or leaving the result sitting in a scratchpad.
- **Working files** — raw AI-mesh downloads, the untouched high-poly `.blend`, unbaked duplicate
  meshes, reference-image experiments, diagnostic scripts and their intermediate renders — stay in
  a scratch location (the harness's scratchpad directory, or a repo-local gitignored `.tmp/`) for
  the duration of the pipeline and never get copied into the deliverable directory alongside the
  finished asset.

**Clean up working files once the finished asset is validated and copied to its destination.** This
pipeline is disk-heavy — a single hero-building run produces a 50+MB high-poly `.blend`, a 50+MB
baked `.blend`, a raw GLB of similar size, and several multi-megabyte PNG bake textures — and running
it more than once without cleanup silently fills a disk with hundreds of MB nobody will ever reopen.
Delete the working files after the deliverable is confirmed in place; do not keep them "just in
case." The only exception is an explicitly open diagnostic (e.g. comparing a raw render against the
finished one to investigate a defect) — say so out loud when that is why something is being kept.
Otherwise, cleanup is part of the task, not an optional finishing touch.

## Files

| Read when | File |
|---|---|
| Picking or calling an AI-mesh endpoint (IDs, prices, tiers, auth) | [AI-MESH-SERVICES.md](AI-MESH-SERVICES.md) |
| Retopo/bake, mobile polycount and texture budgets, LOD chain, ORM packing | [FINISHING-PIPELINE.md](FINISHING-PIPELINE.md) |
| Any 2D asset (category H) or a pack's reference-image pass (category D) | [SPRITE-PIPELINE.md](SPRITE-PIPELINE.md) |
| The request names or implies a specific art style, or ships its own reference images | [REFERENCE-STYLES.md](REFERENCE-STYLES.md) |
