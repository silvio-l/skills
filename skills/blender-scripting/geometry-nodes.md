# Geometry Nodes via Python

Use Geometry Nodes instead of `bmesh` when the result should stay editable/parametric in the UI afterward (a client-facing rig, a tool the user will tweak by hand). For one-shot generation with no further editing, `bmesh` is simpler and has no modifier-evaluation overhead — don't reach for node groups by default.

## Building a node group

Socket creation uses the 4.0+ `NodeTreeInterface` API (`node_tree.interface.new_socket(...)`) — the pre-4.0 direct `inputs.new(...)`/`outputs.new(...)` API was removed, not just deprecated. Check `hasattr(node_tree, "interface")` if targeting older Blender (see [SKILL.md](SKILL.md#version-robustness)).

Scattering ico-spheres across a plane's faces, live-verified end to end:

```python
import bpy

node_tree = bpy.data.node_groups.new("ScatterOnFaces", "GeometryNodeTree")

node_tree.interface.new_socket(name="Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
node_tree.interface.new_socket(name="Density", in_out="INPUT", socket_type="NodeSocketFloat")
node_tree.interface.new_socket(name="Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")

nodes = node_tree.nodes
group_in = nodes.new("NodeGroupInput")
group_out = nodes.new("NodeGroupOutput")
distribute = nodes.new("GeometryNodeDistributePointsOnFaces")
instance = nodes.new("GeometryNodeInstanceOnPoints")
ico = nodes.new("GeometryNodeMeshIcoSphere")
realize = nodes.new("GeometryNodeRealizeInstances")   # see gotcha below — required for real geometry out

links = node_tree.links
links.new(group_in.outputs["Geometry"], distribute.inputs["Mesh"])
links.new(group_in.outputs["Density"], distribute.inputs["Density"])
links.new(distribute.outputs["Points"], instance.inputs["Points"])
links.new(ico.outputs["Mesh"], instance.inputs["Instance"])
links.new(instance.outputs["Instances"], realize.inputs["Geometry"])
links.new(realize.outputs["Geometry"], group_out.inputs["Geometry"])

bpy.ops.mesh.primitive_plane_add(size=4)
plane = bpy.context.active_object
mod = plane.modifiers.new("Scatter", "NODES")
mod.node_group = node_tree
```

## Gotcha: setting modifier input values

There is no stable `mod["Input_N"] = value` dict-style API to rely on across versions — in 5.x that raises `TypeError: id properties not supported for this type`. The actual path is `mod.properties.inputs.<socket_identifier>.value`, and the identifier (`Socket_0`, `Socket_1`, ...) is assigned by **creation order**, not name — look it up from the interface instead of guessing the index:

```python
density_id = next(
    s.identifier for s in node_tree.interface.items_tree
    if s.name == "Density" and s.in_out == "INPUT"
)
getattr(mod.properties.inputs, density_id).value = 20.0
```

If this fails on an older Blender, check `hasattr(mod, "properties") and hasattr(mod.properties, "inputs")` first — pre-5.x used the `mod["Input_N"]` ID-property pattern instead; verify against the actual installed version rather than assuming either form.

## Gotcha: instances aren't real geometry until realized

`GeometryNodeInstanceOnPoints` output is instance references, not mesh data — reading `.data.vertices` on the evaluated object returns **0** until the geometry passes through `GeometryNodeRealizeInstances` (or the object is exported, which realizes implicitly for most formats — but don't rely on implicit realization if you need to inspect/modify the mesh in the same script). Confirmed empirically: identical node graph without `RealizeInstances` evaluates to 0 vertices; with it, the expected vertex count appears.

## Reading back evaluated geometry

Modifiers (including node groups) only apply on the evaluated (depsgraph) object, not the base one:

```python
bpy.context.view_layer.update()
deps = bpy.context.evaluated_depsgraph_get()
eval_obj = plane.evaluated_get(deps)
print(len(eval_obj.data.vertices))   # reflects the modifier stack; plane.data.vertices would not
```

To make the result permanent (e.g. before export or further `bmesh` editing), apply the modifier: `bpy.ops.object.modifier_apply(modifier="Scatter")` with the object active — same as any other modifier, no special-casing needed for `NODES` type.
