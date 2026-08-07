#!/usr/bin/env python3
"""Retopo + bake: turn a dense high-poly mesh into a mobile-ready low-poly one.

A bare Decimate pass on a textured mesh corrupts the texture (the UV layout moves
with the collapsed edges). The fix, per FINISHING-PIPELINE.md: duplicate the
high-poly, decimate the *duplicate* into a low-poly cage, give that cage fresh
Smart-UV-Project UVs, and bake normal/AO/color from the high-poly onto it.

Run headlessly:

    blender --background high_poly.blend \\
      --python retopo_bake.py \\
      -- --target-tris 6000 --texture-size 2048 --margin 0.02 --output finished.blend

Everything after the bare `--` is this script's own argv; Blender ignores it.

No Blender version is pinned. API surfaces that have drifted between majors are
probed with hasattr, per blender-scripting/SKILL.md's "Version robustness" rule.
"""

import argparse
import os
import sys

try:
    import bpy
except ImportError:  # importable for --help / arg-parsing tests without Blender
    bpy = None


# --------------------------------------------------------------------------
# CLI (pure, no bpy)
# --------------------------------------------------------------------------

def script_argv(argv=None):
    """Return the args after the bare '--' separator Blender uses."""
    argv = list(sys.argv if argv is None else argv)
    if "--" in argv:
        return argv[argv.index("--") + 1:]
    return []


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="retopo_bake.py",
        description="Duplicate high-poly -> decimate to low-poly cage -> Smart UV -> Cycles bake.",
    )
    p.add_argument("--target-tris", type=int, default=6000,
                   help="Triangle budget for the low-poly result (default: 6000).")
    p.add_argument("--texture-size", type=int, default=2048,
                   help="Square bake texture resolution, power of two (default: 2048).")
    p.add_argument("--margin", type=float, default=0.02,
                   help="Smart UV Project island margin in UV units (default: 0.02).")
    p.add_argument("--object", default=None,
                   help="Name of the high-poly source object (default: the active mesh object).")
    p.add_argument("--cage-extrusion", type=float, default=None,
                   help="Bake ray cage extrusion. Default: derived from the object's size.")
    p.add_argument("--bake-samples", type=int, default=16,
                   help="Cycles samples per bake pass (default: 16).")
    p.add_argument("--output", default=None,
                   help="Path to save the resulting .blend. Omit to leave the scene in memory.")
    p.add_argument("--texture-dir", default=None,
                   help="Directory for the baked PNGs (default: alongside --output, else CWD).")
    return p.parse_args(argv)


def decimate_ratio(current_tris, target_tris):
    """Collapse Decimate takes a 0-1 ratio, never a triangle count."""
    if current_tris <= 0:
        raise ValueError("current triangle count must be positive")
    if target_tris <= 0:
        raise ValueError("target triangle count must be positive")
    return min(1.0, float(target_tris) / float(current_tris))


def triangle_count(mesh):
    """Triangles a polygon mesh fans out to (a quad is 2 tris, an n-gon is n-2)."""
    return sum(len(p.vertices) - 2 for p in mesh.polygons)


# --------------------------------------------------------------------------
# Blender helpers
# --------------------------------------------------------------------------

def set_active(obj):
    bpy.context.view_layer.objects.active = obj


def select_only(objs):
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)


def find_source_object(name=None):
    if name:
        obj = bpy.data.objects.get(name)
        if obj is None:
            raise SystemExit("ERROR: no object named %r in the scene" % name)
        if obj.type != "MESH":
            raise SystemExit("ERROR: object %r is not a mesh" % name)
        return obj

    active = bpy.context.view_layer.objects.active
    if active is not None and active.type == "MESH":
        return active

    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("ERROR: scene contains no mesh object to retopo")
    if len(meshes) > 1:
        print("NOTE: %d meshes present, using %r (pass --object to choose)"
              % (len(meshes), meshes[0].name))
    return meshes[0]


def duplicate_object(src, new_name):
    """Copy object + mesh data. bpy.data, not bpy.ops — no selection dependency."""
    dup = src.copy()
    dup.data = src.data.copy()
    dup.name = new_name
    dup.data.name = new_name + "_mesh"
    # scene.collection is the root collection and is always resolvable in background
    # mode; bpy.context.collection depends on a view layer that may not be set up.
    bpy.context.scene.collection.objects.link(dup)
    return dup


def decimate_to(obj, target_tris):
    current = triangle_count(obj.data)
    ratio = decimate_ratio(current, target_tris)
    print("Decimate: %d tris -> target %d (ratio %.4f)" % (current, target_tris, ratio))
    if ratio >= 1.0:
        print("NOTE: source is already at or below the budget, skipping Decimate")
        return current
    mod = obj.modifiers.new("LowPolyCollapse", "DECIMATE")
    mod.decimate_type = "COLLAPSE"
    mod.ratio = ratio
    set_active(obj)
    bpy.ops.object.modifier_apply(modifier=mod.name)
    result = triangle_count(obj.data)
    print("Decimate: result %d tris" % result)
    return result


def smart_uv_project(obj, margin):
    """smart_project is an edit-mode operator - it needs faces selected."""
    set_active(obj)
    select_only([obj])
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    kwargs = {"island_margin": margin}
    # angle_limit became a radians-typed property in 2.9x; older builds took degrees.
    # Leaving it at the operator default avoids guessing the unit.
    bpy.ops.uv.smart_project(**kwargs)
    bpy.ops.object.mode_set(mode="OBJECT")
    layers = obj.data.uv_layers
    print("Smart UV Project: %d UV layer(s), margin %.3f" % (len(layers), margin))


def make_image(name, size, is_data, color):
    img = bpy.data.images.get(name)
    if img is not None:
        bpy.data.images.remove(img)
    img = bpy.data.images.new(name, width=size, height=size, alpha=False,
                              float_buffer=False)
    img.generated_color = color
    if is_data and hasattr(img, "colorspace_settings"):
        # normal/AO are data, not color - sRGB encoding them shifts the values
        img.colorspace_settings.name = "Non-Color"
    return img


def ensure_material(obj, name):
    mat = bpy.data.materials.get(name)
    if mat is None:
        mat = bpy.data.materials.new(name)
    # 5.2 deprecates use_nodes (slated for removal in 6.0) but still defaults new
    # materials to non-node in some paths - only touch it if there's no tree yet.
    if getattr(mat, "node_tree", None) is None and hasattr(mat, "use_nodes"):
        mat.use_nodes = True
    obj.data.materials.clear()
    obj.data.materials.append(mat)
    return mat


def principled_of(mat):
    """Find the Principled BSDF by type, not by name - the name is localized/renamed."""
    for node in mat.node_tree.nodes:
        if node.type == "BSDF_PRINCIPLED":
            return node
    return None


def add_image_node(mat, image, location):
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    node.location = location
    return node


def activate_bake_target(mat, node):
    """Cycles bakes into the *active* image node. Getting this wrong writes the
    pass into the wrong image with no error at all."""
    nodes = mat.node_tree.nodes
    for n in nodes:
        n.select = False
    node.select = True
    nodes.active = node


def object_extent(obj):
    dims = obj.dimensions
    return max(dims[0], dims[1], dims[2])


def configure_cycles(scene, samples):
    scene.render.engine = "CYCLES"
    if hasattr(scene, "cycles"):
        scene.cycles.samples = samples
        if hasattr(scene.cycles, "use_denoising"):
            scene.cycles.use_denoising = False
    # CPU keeps the run reproducible in headless/CI contexts
    if hasattr(scene.cycles, "device"):
        scene.cycles.device = "CPU"


def run_bake(bake_type, cage_extrusion, pass_filter=None):
    settings = bpy.context.scene.render.bake
    settings.use_selected_to_active = True
    settings.cage_extrusion = cage_extrusion
    if hasattr(settings, "use_cage"):
        settings.use_cage = False
    if hasattr(settings, "max_ray_distance"):
        settings.max_ray_distance = 0.0
    kwargs = {"type": bake_type, "use_clear": True}
    if pass_filter:
        kwargs["pass_filter"] = pass_filter
    bpy.ops.object.bake(**kwargs)


def save_image(img, directory, filename):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    print("  wrote %s" % path)
    return path


# --------------------------------------------------------------------------
# Pipeline
# --------------------------------------------------------------------------

def main():
    if bpy is None:
        raise SystemExit("ERROR: this script must run inside Blender "
                         "(blender --background file.blend --python retopo_bake.py -- ...)")

    args = parse_args(script_argv())

    scene = bpy.context.scene
    if bpy.context.object is not None and bpy.context.object.mode != "OBJECT":
        bpy.ops.object.mode_set(mode="OBJECT")

    high = find_source_object(args.object)
    print("High-poly source: %r (%d tris)" % (high.name, triangle_count(high.data)))

    # 1. duplicate, 2. decimate the duplicate into the low-poly cage
    low = duplicate_object(high, high.name + "_LOD0")
    decimate_to(low, args.target_tris)

    # 3. fresh UVs on the low-poly copy only
    smart_uv_project(low, args.margin)

    # 4. bake targets
    size = args.texture_size
    mat = ensure_material(low, low.name + "_mat")
    images = {
        "normal": make_image(low.name + "_normal", size, True, (0.5, 0.5, 1.0, 1.0)),
        "ao": make_image(low.name + "_ao", size, True, (1.0, 1.0, 1.0, 1.0)),
        "color": make_image(low.name + "_color", size, False, (0.5, 0.5, 0.5, 1.0)),
    }
    nodes = {
        "normal": add_image_node(mat, images["normal"], (-900, 300)),
        "ao": add_image_node(mat, images["ao"], (-900, 0)),
        "color": add_image_node(mat, images["color"], (-900, -300)),
    }

    configure_cycles(scene, args.bake_samples)
    extrusion = args.cage_extrusion
    if extrusion is None:
        extrusion = max(0.01, object_extent(high) * 0.05)
    print("Bake: cage_extrusion %.4f, %d samples, %dpx" % (extrusion, args.bake_samples, size))

    # selected-to-active: high-poly selected, low-poly selected AND active
    select_only([high, low])
    set_active(low)

    passes = [
        ("normal", "NORMAL", None),
        ("ao", "AO", None),
        # there is no type='COLOR'. DIFFUSE without pass_filter bakes lighting into
        # the albedo; {'COLOR'} keeps it a flat color transfer.
        ("color", "DIFFUSE", {"COLOR"}),
    ]
    for key, bake_type, pass_filter in passes:
        print("Baking %s ..." % key)
        activate_bake_target(mat, nodes[key])
        try:
            run_bake(bake_type, extrusion, pass_filter)
        except RuntimeError as exc:
            raise SystemExit("ERROR: %s bake failed: %s" % (key, exc))

    # 5. wire the baked maps into the Principled BSDF
    bsdf = principled_of(mat)
    if bsdf is None:
        print("WARNING: no Principled BSDF found, baked images left unconnected")
    else:
        links = mat.node_tree.links
        links.new(nodes["color"].outputs["Color"], bsdf.inputs["Base Color"])
        normal_map = mat.node_tree.nodes.new("ShaderNodeNormalMap")
        normal_map.location = (-500, 300)
        links.new(nodes["normal"].outputs["Color"], normal_map.inputs["Color"])
        links.new(normal_map.outputs["Normal"], bsdf.inputs["Normal"])
        print("Wired base color + normal map into Principled BSDF "
              "(AO stays unconnected - it belongs in the ORM pack)")

    # persist
    tex_dir = args.texture_dir
    if tex_dir is None:
        tex_dir = os.path.dirname(os.path.abspath(args.output)) if args.output else os.getcwd()
    for key, img in images.items():
        save_image(img, tex_dir, "%s_%s.png" % (low.name, key))

    if args.output:
        out = os.path.abspath(args.output)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        bpy.ops.wm.save_as_mainfile(filepath=out)
        print("Saved %s" % out)

    final_tris = triangle_count(low.data)
    print("DONE: %s -> %s, %d tris, %dpx maps"
          % (high.name, low.name, final_tris, size))
    print("Next: validate with validate_asset.py, then LOD chain + export "
          "(see FINISHING-PIPELINE.md)")


if __name__ == "__main__":
    main()
