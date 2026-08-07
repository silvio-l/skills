---
name: blender-scripting
description: "Generate Blender 3D geometry headlessly via Python (bpy/bmesh/Geometry Nodes) — procedural buildings, props, trees, rocks, FBX/GLTF export, bpy debugging. Finished mobile-game assets: use game-asset-director. Use for 'Blender-Modell erstellen'."
---

# Blender Scripting

Drive Blender entirely from Python, no UI, no MCP server, no live session — a script you write is the whole interface. Blender is one binary that doubles as editor and runtime:

```bash
blender --version                                    # check first, API drifts between majors
blender --background --python generate_model.py      # run a script file
blender --background --python-expr "import bpy; ..."  # one-liner
```

`--background` (`-b`) needs no display and no running Blender instance. Iterate by re-running the script — there is no persistent session to keep in sync.

When the request is for a *finished, production-ready mobile-game asset* rather than raw procedural geometry for its own sake, defer to `game-asset-director` — it owns AI-mesh routing, retopo/bake, mobile polycount and texture budgets, and asset validation, and calls back into this skill for the geometry and export steps.

## Object creation: bpy.ops vs bpy.data/bmesh

`bpy.ops.mesh.primitive_cube_add()`, `modifier_apply()`, and other object/mesh operators **work fine in `--background` mode without any context override** — despite scattered forum reports of "context is incorrect" errors. Those reports concern UI-/viewport-bound operators (selection painting, sculpt-mode tools), not general object/mesh creation. Don't avoid `bpy.ops` reflexively.

Reach for `bmesh`/`bpy.data` instead when:
- building many objects or dense meshes (`bpy.ops` re-evaluates the depsgraph and redraws per call — real cost at volume)
- the logic must not depend on selection state or the active object (`bpy.ops` implicitly reads both; `bmesh` takes explicit references)

```python
import bmesh, bpy

mesh = bpy.data.meshes.new("Rock")
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=2, radius=1.0)
bm.to_mesh(mesh)
bm.free()  # bmesh is Python-owned — always free, it won't be garbage collected for you

obj = bpy.data.objects.new("Rock", mesh)
bpy.context.scene.collection.objects.link(obj)
```

**Collection-linking gotcha:** use `bpy.context.scene.collection` (the root collection — always resolvable). `bpy.context.collection` depends on an active view layer that isn't reliably set up in every background scenario.

## Design sense

Procedural does not mean random. Silhouette, growth logic, and material history carry more visual weight than surface detail. Before generating new geometry whose *appearance* matters (a building, a tree, a rock, a prop) — not for export/inspection/debug tasks — read **[design-sense.md](design-sense.md)**: shape language, primary/secondary/tertiary form order, biologically/geologically grounded growth, power-law scatter, anti-repetition, proportion systems, environmental storytelling.

## Routing

| You want to... | Read |
|---|---|
| Model a building, prop, or organic form (rocks, trees, terrain) | [techniques.md](techniques.md) — reads [design-sense.md](design-sense.md) first |
| Build a reusable, node-based generator (parametric, editable in the UI afterward) | [geometry-nodes.md](geometry-nodes.md) |
| Export to FBX/GLTF/OBJ/STL/PLY, or debug a `bpy` error | [export-and-errors.md](export-and-errors.md) |

## Version robustness

Don't pin to a Blender version. Check what's actually there:

```python
import bpy
has_new_export = hasattr(bpy.ops.wm, "gltf_export")   # 4.x+ wm.* operators
has_legacy = hasattr(bpy.ops.export_scene, "gltf")      # coexists in 5.x, may vanish later

# check on an actual instance, not the class — bpy properties often don't
# introspect on the class itself
ng = bpy.data.node_groups.new("_probe", "GeometryNodeTree")
has_new_sockets = hasattr(ng, "interface") and hasattr(ng.interface, "new_socket")  # 4.0+ NodeTreeInterface
bpy.data.node_groups.remove(ng)
```

Known migration points: 2.8 moved active-object access to `bpy.context.view_layer.objects.active` only (no more `scene.objects.active`); 3.2+ deprecated dict-based operator context override in favor of `context.temp_override(...)`; 4.0 introduced `wm.*_export`/`wm.*_import` operators alongside the legacy `export_scene.*`/`import_mesh.*` ones and replaced direct node-socket creation with the `NodeTreeInterface` API. All of this is detailed with working code in the linked files.
