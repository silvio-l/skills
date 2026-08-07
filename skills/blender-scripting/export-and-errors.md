# Export and Error Reference

## Export: check what's available, don't assume a version

Blender 4.0+ introduced `wm.*_export`/`wm.*_import` operators; the legacy `export_scene.*`/`import_mesh.*`/`export_mesh.*` operators still coexist as of 5.2 but aren't guaranteed to stay. Check with `hasattr` and prefer the modern operator when both exist — live-verified pattern, all five formats confirmed working:

```python
import bpy, os

def export_gltf(filepath):
    if hasattr(bpy.ops.export_scene, "gltf"):
        bpy.ops.export_scene.gltf(
            filepath=filepath, export_format='GLB',
            export_apply=False,                              # don't bake modifiers — Array balloons file size
            export_draco_mesh_compression_enable=False,       # apply Draco later via gltf-transform, not here
        )
    else:
        bpy.ops.wm.gltf_export(filepath=filepath, export_format='GLB')

def export_fbx(filepath):
    if hasattr(bpy.ops.export_scene, "fbx"):
        bpy.ops.export_scene.fbx(filepath=filepath, use_selection=False)
    else:
        bpy.ops.wm.fbx_export(filepath=filepath)

def export_obj(filepath):
    if hasattr(bpy.ops.wm, "obj_export"):
        bpy.ops.wm.obj_export(filepath=filepath)
    else:
        bpy.ops.export_scene.obj(filepath=filepath)

def export_stl(filepath):
    if hasattr(bpy.ops.wm, "stl_export"):
        bpy.ops.wm.stl_export(filepath=filepath)
    else:
        bpy.ops.export_mesh.stl(filepath=filepath)

def export_ply(filepath):
    if hasattr(bpy.ops.wm, "ply_export"):
        bpy.ops.wm.ply_export(filepath=filepath)
    else:
        bpy.ops.export_mesh.ply(filepath=filepath)
```

Always `os.makedirs(os.path.dirname(filepath), exist_ok=True)` before exporting, and quote/escape paths that may contain spaces.

## GLTF export settings

| Setting | Value | Why |
|---|---|---|
| `export_format` | `'GLB'` | single binary file, no separate texture references to lose |
| `export_apply` | `False` | don't bake modifiers — an Array modifier can turn 1MB into 56MB |
| `export_draco_mesh_compression_enable` | `False` | apply Draco later via `gltf-transform`, re-encoding an already-Draco mesh corrupts it |

## Material export survival matrix

Procedural node setups mostly don't survive GLTF export — bake to an image texture first, or patch the material at runtime after load.

| Blender feature | Exports to GLTF? | Notes |
|---|---|---|
| Flat roughness/metallic values | Yes | direct mapping |
| Image textures (baseColor, normal) | Yes | packed or referenced |
| Image roughness texture | Partially | texture exports, any Color Ramp remapping is lost |
| Procedural Noise/Voronoi texture | No | must bake to image, or patch at runtime |
| Color Ramp value remapping | No | range compression lost |
| Bump from Noise node | No | bake to a normal map instead |
| Baked normal maps | Yes | standard GLTF feature |
| Emission | Yes | via `emissiveFactor`/`emissiveTexture` |

## GLTF name mapping

Blender object/mesh names get transformed on export — always check names in the exported file, not in Blender, before referencing them in downstream code:

| Blender name | GLTF name | Rule |
|---|---|---|
| `RINGS ball L` | `RINGS_ball_L` | spaces → underscores |
| `Sphere.003` | `Sphere003` | dot-number suffix collapses |
| `RINGS S ` (trailing space) | `RINGS_S_` | trailing space → trailing underscore |
| two objects both named `Cube` | `Cube`, `Cube_1` | GLTF appends an index — order isn't guaranteed |

## Known errors

| Error | Cause | Fix |
|---|---|---|
| `RuntimeError: Operator bpy.ops.export_scene.gltf.poll() failed` | no active scene, or an operator that needs a specific context | run in `--background` mode (has a valid scene by default) rather than a minimal custom context |
| `AttributeError: 'NoneType' object has no attribute 'nodes'` | material has `use_nodes = False` | check `mat.use_nodes` before accessing `mat.node_tree.nodes` |
| `KeyError: 'Principled BSDF'` | material uses a non-standard shader setup | iterate `node_tree.nodes` and filter by `node.type == 'BSDF_PRINCIPLED'` instead of indexing by name |
| `RecursionError` walking object hierarchy | deep parenting hits Python's recursion limit | use an iterative, stack-based traversal instead of recursive |
| `bpy.context.scene` is `None` | context not fully initialized (e.g. inside a driver callback) | use `bpy.data.scenes[0]` or `bpy.context.window.scene` as a fallback |
| `TypeError: id properties not supported for this type` setting a Geometry Nodes modifier input | Blender 5.x removed the `mod["Input_N"]` ID-property pattern | use `mod.properties.inputs.<Socket_id>.value` — see [geometry-nodes.md](geometry-nodes.md#gotcha-setting-modifier-input-values) |
| Geometry Nodes modifier evaluates to 0 vertices | instances from `InstanceOnPoints` were never realized | add a `GeometryNodeRealizeInstances` node before the group output — see [geometry-nodes.md](geometry-nodes.md#gotcha-instances-arent-real-geometry-until-realized) |

## Post-export optimization (GLTF/GLB)

For web delivery, run [`gltf-transform`](https://gltf-transform.dev) *after* the Blender export, in this order — never use its `optimize` command, it bundles `simplify` and will destroy mesh geometry:

```bash
npx @gltf-transform/cli inspect input.glb                                    # baseline: GPU est., texture count/size
npx @gltf-transform/cli resize input.glb resized.glb --width 1024 --height 1024   # biggest GPU-memory win
npx @gltf-transform/cli webp resized.glb webp.glb --quality 85               # file-size win, no GPU-memory effect
npx @gltf-transform/cli draco webp.glb final.glb                             # mesh compression, irreversible — do this last
npx @gltf-transform/cli inspect final.glb                                    # confirm size/texture/anim counts
```

Typical reduction: ~22MB raw → ~3.7MB after resize+WebP → ~1MB after Draco. Keep the pre-Draco intermediate file — Draco is not reversible.
