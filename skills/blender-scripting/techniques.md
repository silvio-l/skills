# Generation Techniques

Read [design-sense.md](design-sense.md) first — the patterns below implement its principles; they're not a substitute for reading it.

## Hard-surface / architecture

Order of operations matters as much as the modifiers themselves: primary volumes first, secondary breakup (Boolean cutouts, Array repeats) second, tertiary polish (Bevel) last — applying Bevel before the Boolean bakes ugly geometry into the cut.

```python
import bpy

# primary form
bpy.ops.mesh.primitive_cube_add(size=2, location=(0, 0, 1))
wall = bpy.context.active_object
wall.scale = (5, 0.2, 3)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)

# secondary breakup: repeated window cutout via Array + Boolean
bpy.ops.mesh.primitive_cube_add(size=0.6, location=(-3, 0, 1.2))
window_cutter = bpy.context.active_object
window_cutter.scale = (1, 3, 1)

arr = window_cutter.modifiers.new("WindowRepeat", "ARRAY")
arr.count = 6
arr.relative_offset_displace = (2.0, 0, 0)   # note: attribute is *_displace, not *_display_size

bool_mod = wall.modifiers.new("Windows", "BOOLEAN")
bool_mod.object = window_cutter
bool_mod.operation = "DIFFERENCE"
bpy.context.view_layer.objects.active = wall
bpy.ops.object.modifier_apply(modifier="Windows")
window_cutter.hide_set(True)

# tertiary detail: bevel last
bevel = wall.modifiers.new("EdgeBevel", "BEVEL")
bevel.width = 0.02
bevel.segments = 2
bpy.ops.object.modifier_apply(modifier="EdgeBevel")
```

Other modifiers for the same primary→secondary→tertiary role: `SOLIDIFY` (give a flat plane real thickness — primary), `MIRROR` (symmetric primary forms, model one half), `SCREW` (spiral stairs, threads, primary form from a profile curve), `BEVEL`/`SUBSURF` (tertiary only — apply after breakup, never before).

Before placing walls/windows/floors, fix a proportion constant and derive positions from it rather than hardcoding coordinates — see design-sense.md's proportion-system principle:

```python
GOLDEN = 1.618
floor_height = 3.0
window_width = floor_height / GOLDEN   # ~1.85 — derived, not guessed
```

## Organic / natural forms

### Rock and terrain

Match the noise/Voronoi combination to the named rock type, and layer a second, lower-frequency, weaker pass for weathering — don't apply one generic displacement to every rock:

```python
import bpy, bmesh

mesh = bpy.data.meshes.new("Granite")
bm = bmesh.new()
bmesh.ops.create_icosphere(bm, subdivisions=4, radius=1.0)
bm.to_mesh(mesh)
bm.free()
obj = bpy.data.objects.new("Granite", mesh)
bpy.context.scene.collection.objects.link(obj)

# granite: sharp crystalline facets -> Voronoi at high scale, applied first
tex_voronoi = bpy.data.textures.new("GraniteFacets", type='VORONOI')
tex_voronoi.noise_scale = 1.2
tex_voronoi.distance_metric = 'DISTANCE'
disp1 = obj.modifiers.new("FacetDisplace", "DISPLACE")
disp1.texture = tex_voronoi
disp1.strength = 0.35

# weathering: second, lower-frequency, subtler pass
tex_noise = bpy.data.textures.new("Weathering", type='CLOUDS')
tex_noise.noise_scale = 0.5
disp2 = obj.modifiers.new("Weathering", "DISPLACE")
disp2.texture = tex_noise
disp2.strength = 0.08

bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier="FacetDisplace")
bpy.ops.object.modifier_apply(modifier="Weathering")
```

Rock-type vocabulary to pick displacement from: **granite/igneous** → sharp Voronoi facets, high strength, minimal smoothing. **Sedimentary** → flat CLOUDS/Musgrave layering along one dominant axis (scale non-uniformly instead of isotropic noise) plus chipped edges at low-poly boundaries. **Weathered/river rock** → strong Subsurf/smooth after a mild Voronoi pass, no sharp facets at all.

### Trees

**Default here, tested and working**: recursive branching with apical-dominance and phototropism weighting (a practical L-system, interpreted directly into `bmesh` edges rather than a separate turtle-graphics layer):

```python
import bpy, bmesh, math, random
from mathutils import Vector, Matrix

random.seed(1)

def grow_branch(bm, origin, direction, length, radius, depth, max_depth):
    if depth > max_depth or radius < 0.01:
        return
    end = origin + direction * length
    v1 = bm.verts.new(origin)
    v2 = bm.verts.new(end)
    bm.edges.new((v1, v2))

    # apical dominance: side branches weaken/thin closer to the tip (higher depth)
    n_branches = 2 if depth < max_depth - 1 else 1
    for i in range(n_branches):
        spread = math.radians(25 + 10 * depth)
        yaw = random.uniform(0, 2 * math.pi)
        tilt = Matrix.Rotation(spread, 4, Vector((math.cos(yaw), math.sin(yaw), 0)))
        new_dir = (tilt @ direction.to_4d()).to_3d().normalized()
        new_dir = (new_dir + Vector((0, 0, 0.3))).normalized()  # phototropism: bias upward
        grow_branch(bm, end, new_dir, length * 0.72, radius * 0.68, depth + 1, max_depth)

mesh = bpy.data.meshes.new("Tree")
bm = bmesh.new()
grow_branch(bm, Vector((0, 0, 0)), Vector((0, 0, 1)), 1.0, 0.15, 0, 5)
bm.to_mesh(mesh)
bm.free()

obj = bpy.data.objects.new("Tree", mesh)
bpy.context.scene.collection.objects.link(obj)

skin = obj.modifiers.new("Skin", "SKIN")   # turns the edge skeleton into a tapered mesh
bpy.context.view_layer.objects.active = obj
bpy.ops.object.modifier_apply(modifier="Skin")
```

Tune `length * 0.72` / `radius * 0.68` (branch shrink per generation) and the `spread` angle for species character — tighter spread + faster shrink reads as conifer, wider spread + slower shrink reads as oak/broadleaf.

**Higher-fidelity alternative, described but not shipped as tested code here**: the Space Colonization Algorithm (Runions, Lane, Prusinkiewicz 2007) grows branches toward a cloud of randomly-placed attractor points instead of a fixed recursive angle rule — closer to how real trees compete for light. It needs: an attractor-point cloud (scattered in the target canopy volume), a per-point **influence radius** (attractors pull the nearest branch tip toward them) and **kill radius** (attractors within this distance of a tip are consumed/removed), then iterative growth steps (each step: find each attractor's nearest tip, grow that tip a fixed distance toward the *average* direction of its attractors, remove consumed attractors, repeat until no attractors remain or a step limit). This is a real algorithm with real tuning cost — budget for it explicitly rather than improvising it as a one-off; the recursive approach above is the safe default when time is constrained.

### Scatter / distribution

Sample instance sizes from a power law, not `random.uniform` — few large, many small, matching how debris/rocks/leaves actually distribute in nature:

```python
import bpy, random

random.seed(2)

def power_law_size(min_size, max_size, exponent=2.0):
    u = random.random()
    size = min_size / (u ** (1.0 / exponent))
    return min(size, max_size)   # clamp — power law has an unbounded tail

for i in range(30):
    r = power_law_size(min_size=0.05, max_size=1.0, exponent=1.8)
    x, y = random.uniform(-5, 5), random.uniform(-5, 5)
    bpy.ops.mesh.primitive_ico_sphere_add(radius=r, location=(x, y, r), subdivisions=1)
```

Lower `exponent` (closer to 1) skews harder toward many-small/few-large; higher `exponent` (3+) approaches a more even spread. 1.5–2.5 reads as natural debris for most scenes.
