#!/usr/bin/env python3
"""3D QA gate: the last step of every 3D branch of game-asset-director.

This script's output is the source of truth for whether an asset is done - not a
render, not a file listing, not the agent's own reading of the mesh.

Run inside Blender against the finished asset:

    blender --background finished.blend --python validate_asset.py -- --class character

Structure: the check_* functions below are pure. They take plain ints, lists and
tuples, import nothing, and are unit-tested without Blender installed
(tests/game-asset-director/test_validate_asset.py). The read_* functions are a
thin bpy shell that turns a scene into those primitives. A boundary bug in a
budget check would print ALL CHECKS PASSED on a genuinely broken asset, which is
exactly why the predicates are separated out and tested.
"""

import argparse
import sys

# ---------------------------------------------------------------------------
# Budgets (FINISHING-PIPELINE.md)
# ---------------------------------------------------------------------------

TRI_BUDGETS = {
    "character": (3000, 10000),   # character / hero
    "prop": (100, 2000),          # background / mid-ground prop
}

TEXTURE_BUDGETS = {
    "character": (1024, 2048),    # 2K standard, 1K acceptable
    "prop": (512, 1024),          # small props: 1K or 512
}

LOD_REDUCTION = 0.75              # ~75% of the triangles drop per LOD level
LOD_TOLERANCE = 0.10              # +/- 10 percentage points is still a valid step


# ---------------------------------------------------------------------------
# Pure checks - no bpy, no I/O
# ---------------------------------------------------------------------------

def check_tri_budget(tri_count, asset_class):
    """Triangle count against the class budget. Returns (ok, reason)."""
    if asset_class not in TRI_BUDGETS:
        return False, "unknown asset class %r (expected one of %s)" % (
            asset_class, ", ".join(sorted(TRI_BUDGETS)))
    lo, hi = TRI_BUDGETS[asset_class]
    if tri_count < lo:
        return False, "%d tris is below the %s budget (%d-%d) - under-detailed or empty" % (
            tri_count, asset_class, lo, hi)
    if tri_count > hi:
        return False, "%d tris exceeds the %s budget (%d-%d)" % (
            tri_count, asset_class, lo, hi)
    return True, "%d tris within the %s budget (%d-%d)" % (tri_count, asset_class, lo, hi)


STACKED_BBOX_RATIO = 0.6   # bbox intersection this deep into the smaller island = stacked


def check_uv_shells(shells):
    """UV islands must sit inside 0-1 space and must not be stacked on each other.

    `shells` is a list of islands; each island is a list of (u, v) tuples.

    The 0-1 test is exact. The overlap test is a *bounding-box* heuristic: a
    correctly packed layout has islands whose boxes routinely clip each other
    (they interlock without sharing texel area), so flagging every box
    intersection would fail every well-packed unwrap. Instead an overlap is
    reported only when the intersection covers more than STACKED_BBOX_RATIO of
    the smaller island's box - the signature of genuinely stacked or duplicated
    islands, which is the failure that actually corrupts a bake.
    """
    if not shells:
        return False, "no UV shells - the mesh is unwrapped or has no UV layer"

    boxes = []
    for i, shell in enumerate(shells):
        if not shell:
            return False, "UV shell %d is empty" % i
        us = [uv[0] for uv in shell]
        vs = [uv[1] for uv in shell]
        u_min, u_max, v_min, v_max = min(us), max(us), min(vs), max(vs)
        if u_min < 0.0 or v_min < 0.0 or u_max > 1.0 or v_max > 1.0:
            return False, ("UV shell %d leaves 0-1 space "
                           "(u %.3f-%.3f, v %.3f-%.3f)" % (i, u_min, u_max, v_min, v_max))
        # collinear UVs carry no texel area - the bake has nowhere to write
        if u_max - u_min <= 0.0 or v_max - v_min <= 0.0:
            return False, "UV shell %d is degenerate (zero area, collinear UVs)" % i
        boxes.append((u_min, u_max, v_min, v_max))

    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            overlap_u = min(a[1], b[1]) - max(a[0], b[0])
            overlap_v = min(a[3], b[3]) - max(a[2], b[2])
            if overlap_u <= 0.0 or overlap_v <= 0.0:
                continue
            area_a = (a[1] - a[0]) * (a[3] - a[2])
            area_b = (b[1] - b[0]) * (b[3] - b[2])
            smaller = min(area_a, area_b)
            if (overlap_u * overlap_v) / smaller > STACKED_BBOX_RATIO:
                return False, "UV shells %d and %d are stacked on each other" % (i, j)

    return True, "%d UV shell(s) inside 0-1 space, none stacked" % len(shells)


def check_uv_padding(shells, texture_size, min_texels=2):
    """Islands need a gap between them or they bleed into each other at mip levels.

    Padding is what `retopo_bake.py --margin` buys; too little shows up as seams
    on-device and not in the editor, so it is worth an explicit check. Measured
    as the smallest bounding-box gap between any two islands, converted to texels
    at `texture_size`.

    The default of 2 texels is deliberately lax: it catches the real failure
    (margin 0 - islands touching) without false-failing a tightly interlocked
    pack, where two islands' *boxes* can clip while their texels never do. A
    measured healthy unwrap at margin 0.02 sits around 8 texels at 1024.
    """
    if len(shells) < 2:
        return True, "single UV shell - no inter-island padding to check"
    if texture_size <= 0:
        return False, "invalid texture size %r" % texture_size

    boxes = []
    for shell in shells:
        us = [uv[0] for uv in shell]
        vs = [uv[1] for uv in shell]
        boxes.append((min(us), max(us), min(vs), max(vs)))

    worst = None
    for i in range(len(boxes)):
        for j in range(i + 1, len(boxes)):
            a, b = boxes[i], boxes[j]
            gap_u = max(b[0] - a[1], a[0] - b[1])
            gap_v = max(b[2] - a[3], a[2] - b[3])
            gap = max(gap_u, gap_v)   # separated if either axis separates them
            if worst is None or gap < worst[0]:
                worst = (gap, i, j)

    gap, i, j = worst
    texels = gap * texture_size
    if texels < min_texels:
        return False, ("UV shells %d and %d are only %.1f texels apart at %dpx "
                       "(minimum %d) - raise --margin and re-bake"
                       % (i, j, texels, texture_size, min_texels))
    return True, "tightest UV island gap is %.1f texels at %dpx (minimum %d)" % (
        texels, texture_size, min_texels)


def check_ngons(face_vertex_counts):
    """Quads and tris only. `face_vertex_counts` is one int per face."""
    if not face_vertex_counts:
        return False, "mesh has no faces"
    ngons = [n for n in face_vertex_counts if n > 4]
    degenerate = [n for n in face_vertex_counts if n < 3]
    if degenerate:
        return False, "%d degenerate face(s) with fewer than 3 vertices" % len(degenerate)
    if ngons:
        return False, "%d n-gon(s) found (largest: %d vertices) - triangulate or re-topologize" % (
            len(ngons), max(ngons))
    quads = sum(1 for n in face_vertex_counts if n == 4)
    tris = sum(1 for n in face_vertex_counts if n == 3)
    return True, "%d faces, quads/tris only (%d quads, %d tris)" % (
        len(face_vertex_counts), quads, tris)


def is_power_of_two(n):
    return isinstance(n, int) and n > 0 and (n & (n - 1)) == 0


def check_texture_dims(width, height, asset_class):
    """Power-of-two, square, and within the class's size range."""
    if asset_class not in TEXTURE_BUDGETS:
        return False, "unknown asset class %r" % asset_class
    if not is_power_of_two(width) or not is_power_of_two(height):
        return False, "texture %dx%d is not power-of-two" % (width, height)
    if width != height:
        return False, "texture %dx%d is not square" % (width, height)
    lo, hi = TEXTURE_BUDGETS[asset_class]
    if width < lo:
        return False, "texture %dpx is below the %s minimum (%dpx)" % (width, asset_class, lo)
    if width > hi:
        return False, "texture %dpx exceeds the %s maximum (%dpx)" % (width, asset_class, hi)
    return True, "texture %dx%d within the %s range (%d-%dpx)" % (
        width, height, asset_class, lo, hi)


def check_lod_chain(tri_counts):
    """Each LOD level should drop ~75% of the previous level's triangles."""
    if len(tri_counts) < 2:
        return False, "an LOD chain needs at least two levels"
    for i in range(1, len(tri_counts)):
        prev, cur = tri_counts[i - 1], tri_counts[i]
        if prev <= 0:
            return False, "LOD%d has no triangles" % (i - 1)
        reduction = 1.0 - (float(cur) / float(prev))
        if reduction < LOD_REDUCTION - LOD_TOLERANCE:
            return False, ("LOD%d only drops %.0f%% of LOD%d (expected ~%.0f%%)"
                           % (i, reduction * 100, i - 1, LOD_REDUCTION * 100))
        if reduction > LOD_REDUCTION + LOD_TOLERANCE:
            return False, ("LOD%d drops %.0f%% of LOD%d - too aggressive (expected ~%.0f%%)"
                           % (i, reduction * 100, i - 1, LOD_REDUCTION * 100))
    return True, "LOD chain %s reduces ~%.0f%% per level" % (
        list(tri_counts), LOD_REDUCTION * 100)


# ---------------------------------------------------------------------------
# bpy shell - imports Blender lazily so the checks above stay importable
# ---------------------------------------------------------------------------

def _bpy():
    import bpy  # noqa: PLC0415 - deliberate: keeps this module importable without Blender
    return bpy


def _pick_object(name=None):
    bpy = _bpy()
    if name:
        obj = bpy.data.objects.get(name)
        if obj is None or obj.type != "MESH":
            raise SystemExit("ERROR: no mesh object named %r" % name)
        return obj
    active = bpy.context.view_layer.objects.active
    if active is not None and active.type == "MESH":
        return active
    meshes = [o for o in bpy.context.scene.objects if o.type == "MESH"]
    if not meshes:
        raise SystemExit("ERROR: scene contains no mesh object")
    # the finished low-poly is the interesting one when a high-poly source is still present
    lods = [o for o in meshes if "LOD" in o.name.upper()]
    return (lods or meshes)[0]


def read_mesh_stats(obj):
    """-> (triangle_count, [vertices per face, ...])"""
    counts = [len(p.vertices) for p in obj.data.polygons]
    tris = sum(n - 2 for n in counts)
    return tris, counts


UV_WELD_PRECISION = 5   # decimal places two UVs must share to count as the same point


def read_uv_shells(obj):
    """-> [[(u, v), ...], ...] one list of UV coords per UV island.

    Islands are grouped by shared *UV* coordinate, not by mesh connectivity: a
    seam splits one connected mesh into several islands, so grouping by mesh
    topology would report a seamed sphere as a single shell and the overlap
    check would never fire.
    """
    mesh = obj.data
    if not mesh.uv_layers:
        return []
    uv_layer = mesh.uv_layers.active or mesh.uv_layers[0]

    parent = list(range(len(mesh.polygons)))

    def find(a):
        while parent[a] != a:
            parent[a] = parent[parent[a]]
            a = parent[a]
        return a

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    # two faces belong to the same island when they share a welded UV point
    uv_to_face = {}
    face_uvs = []
    for fi, poly in enumerate(mesh.polygons):
        coords = []
        for li in poly.loop_indices:
            uv = uv_layer.data[li].uv
            coords.append((uv[0], uv[1]))
            key = (round(uv[0], UV_WELD_PRECISION), round(uv[1], UV_WELD_PRECISION))
            if key in uv_to_face:
                union(uv_to_face[key], fi)
            else:
                uv_to_face[key] = fi
        face_uvs.append(coords)

    islands = {}
    for fi in range(len(mesh.polygons)):
        islands.setdefault(find(fi), []).extend(face_uvs[fi])
    return list(islands.values())


def read_textures(obj):
    """-> [(name, width, height), ...] for every image used by the object's materials."""
    out = []
    for slot in obj.material_slots:
        mat = slot.material
        # node_tree, not use_nodes: the latter is deprecated as of 5.2 and reading
        # it emits a warning; an absent tree is the condition we actually care about
        if mat is None or getattr(mat, "node_tree", None) is None:
            continue
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image is not None:
                out.append((node.image.name, node.image.size[0], node.image.size[1]))
    return out


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report(results):
    """results: [(label, ok, reason), ...] -> exit code."""
    failures = []
    for label, ok, reason in results:
        print("%s  %-16s %s" % ("PASS" if ok else "FAIL", label, reason))
        if not ok:
            failures.append("%s: %s" % (label, reason))
    print("")
    if failures:
        print("FAIL: %s" % " | ".join(failures))
        return 1
    print("ALL CHECKS PASSED")
    return 0


def parse_args(argv):
    p = argparse.ArgumentParser(
        prog="validate_asset.py",
        description="3D mobile-game asset QA gate. Non-zero exit on any failure.")
    p.add_argument("--class", dest="asset_class", default="prop",
                   choices=sorted(TRI_BUDGETS),
                   help="Asset class the budgets are checked against (default: prop).")
    p.add_argument("--object", default=None,
                   help="Object to validate (default: active mesh, preferring a *LOD* name).")
    p.add_argument("--skip-textures", action="store_true",
                   help="Skip the texture-dimension check (untextured intermediate).")
    p.add_argument("--texture-size", type=int, default=None,
                   help="Map size the UV padding is measured against "
                        "(default: the largest texture on the material, else 1024).")
    p.add_argument("--min-texel-padding", type=int, default=2,
                   help="Minimum inter-island gap in texels (default: 2).")
    return p.parse_args(argv)


def script_argv(argv=None):
    argv = list(sys.argv if argv is None else argv)
    if "--" in argv:
        return argv[argv.index("--") + 1:]
    return []


def main():
    args = parse_args(script_argv())
    obj = _pick_object(args.object)
    print("Validating %r as class %r\n" % (obj.name, args.asset_class))

    tris, face_counts = read_mesh_stats(obj)
    shells = read_uv_shells(obj)
    textures = read_textures(obj)

    # padding is measured in texels, so it needs the actual map size
    texture_size = args.texture_size
    if texture_size is None:
        texture_size = max([w for _, w, _ in textures], default=1024)

    results = [
        ("tri-budget",) + check_tri_budget(tris, args.asset_class),
        ("topology",) + check_ngons(face_counts),
        ("uv-shells",) + check_uv_shells(shells),
        ("uv-padding",) + check_uv_padding(shells, texture_size, args.min_texel_padding),
    ]

    if not args.skip_textures:
        if not textures:
            results.append(("textures", False, "no image textures found on the material"))
        for name, w, h in textures:
            ok, reason = check_texture_dims(w, h, args.asset_class)
            results.append(("texture:%s" % name, ok, reason))

    sys.exit(report(results))


if __name__ == "__main__":
    main()
