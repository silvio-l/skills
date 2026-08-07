#!/usr/bin/env python3
"""2D QA gate: the last step of routing category H (sprites, icons, tile art).

This script's exit code is the source of truth for whether a 2D asset is done -
not a look at the image.

    python3 validate_2d_asset.py --image sprite.png --target 512x512 --require-pot
    python3 validate_2d_asset.py --image enemy_a.png --target 512x512 --compare-to enemy_b.png

Structure mirrors validate_asset.py: the check_* functions are pure (plain ints,
strings and tuples, no imports) and are unit-tested without Pillow installed
(tests/game-asset-director/test_validate_2d_asset.py). The read_* functions are a
thin Pillow shell.

Dependency: Pillow (`pip install pillow`) for the read_* shell only. If it is
missing the script says so and exits non-zero - it never skips a check silently.
"""

import argparse
import os
import sys

ALLOWED_FORMATS = ("png", "webp")

# Alpha-edge quality thresholds (SPRITE-PIPELINE.md)
MIN_SOFT_EDGE_RATIO = 0.02   # below this the alpha is effectively a 1-bit mask
MAX_STRAY_ALPHA_RATIO = 0.25  # above this the cutout kept background haze


# ---------------------------------------------------------------------------
# Pure checks - no PIL, no I/O
# ---------------------------------------------------------------------------

def check_canvas_size(width, height, target_width, target_height):
    """Canvas must match the in-engine target exactly - import-time resampling
    destroys the edge quality this pipeline exists to protect."""
    if width <= 0 or height <= 0:
        return False, "invalid canvas %dx%d" % (width, height)
    if (width, height) != (target_width, target_height):
        return False, "canvas %dx%d does not match the target %dx%d" % (
            width, height, target_width, target_height)
    return True, "canvas %dx%d matches the target" % (width, height)


def is_power_of_two(n):
    return isinstance(n, int) and n > 0 and (n & (n - 1)) == 0


def check_power_of_two(width, height, required=True):
    """Only enforced where the engine expects it - pass required=False otherwise."""
    if not required:
        return True, "power-of-two not required for this target"
    bad = [("width", width), ("height", height)]
    offenders = ["%s=%d" % (label, value) for label, value in bad if not is_power_of_two(value)]
    if offenders:
        return False, "not power-of-two: %s" % ", ".join(offenders)
    return True, "%dx%d is power-of-two" % (width, height)


def check_format(path_or_extension, allowed=ALLOWED_FORMATS):
    """PNG/WebP only. JPEG has no alpha and its ringing lands on the silhouette."""
    text = str(path_or_extension).lower()
    ext = text.rsplit(".", 1)[-1] if "." in text else text
    ext = ext.lstrip(".").strip()
    if ext == "jpeg":
        ext = "jpg"
    allowed_norm = tuple(a.lower().lstrip(".") for a in allowed)
    if ext not in allowed_norm:
        return False, "format %r not allowed (expected one of %s)" % (
            ext, ", ".join(allowed_norm))
    return True, "format %r allowed" % ext


def check_alpha_edge_quality(total_pixels, soft_alpha_pixels, opaque_pixels):
    """Alpha must be genuinely anti-aliased but not haloed.

    soft_alpha_pixels = pixels with 0 < alpha < 255 (the silhouette's AA band).
    Too few relative to the opaque area means a 1-bit mask (stair-stepping);
    too many means the matte kept background haze around the subject.
    """
    if total_pixels <= 0:
        return False, "empty image"
    if opaque_pixels <= 0:
        return False, "image has no opaque pixels - the cutout removed the subject"
    ratio = float(soft_alpha_pixels) / float(opaque_pixels)
    if ratio < MIN_SOFT_EDGE_RATIO:
        return False, ("alpha edge is effectively 1-bit (%.3f soft/opaque, "
                       "minimum %.2f) - stair-stepped silhouette" % (ratio, MIN_SOFT_EDGE_RATIO))
    if ratio > MAX_STRAY_ALPHA_RATIO:
        return False, ("too much partial alpha (%.3f soft/opaque, maximum %.2f) - "
                       "halo or leftover background haze" % (ratio, MAX_STRAY_ALPHA_RATIO))
    return True, "alpha edge anti-aliased (%.3f soft/opaque)" % ratio


def _color_distance(a, b):
    return sum(abs(int(x) - int(y)) for x, y in zip(a[:3], b[:3]))


def check_palette_consistency(dominant_colors_a, dominant_colors_b, tolerance=90):
    """Pack consistency: every dominant color in A needs a near match in B.

    Colors are (r, g, b) 0-255 tuples; distance is Manhattan across RGB, so
    `tolerance` is a sum across three channels (90 ~ 30 per channel).
    """
    if not dominant_colors_a or not dominant_colors_b:
        return False, "missing dominant-color data for one of the two images"
    unmatched = []
    for color in dominant_colors_a:
        best = min(_color_distance(color, other) for other in dominant_colors_b)
        if best > tolerance:
            unmatched.append((tuple(color[:3]), best))
    if unmatched:
        worst = max(unmatched, key=lambda item: item[1])
        return False, ("%d of %d dominant colors have no match within tolerance %d "
                       "(worst: rgb%s at distance %d) - the pack disagrees with itself"
                       % (len(unmatched), len(dominant_colors_a), tolerance, worst[0], worst[1]))
    return True, "%d dominant colors match within tolerance %d" % (
        len(dominant_colors_a), tolerance)


def parse_target(text):
    """'512x512' -> (512, 512). Raises ValueError on anything else."""
    parts = str(text).lower().replace(" ", "").split("x")
    if len(parts) != 2:
        raise ValueError("expected WIDTHxHEIGHT, got %r" % text)
    return int(parts[0]), int(parts[1])


# ---------------------------------------------------------------------------
# Pillow shell
# ---------------------------------------------------------------------------

def _pil_image():
    try:
        from PIL import Image  # noqa: PLC0415 - deliberate: keeps the checks importable
    except ImportError:
        raise SystemExit("ERROR: Pillow is required to read images "
                         "(pip install pillow). Checks were not run.")
    return Image


def read_image_size(path):
    Image = _pil_image()
    with Image.open(path) as img:
        return img.size


def read_alpha_edge_stats(path):
    """-> (total_pixels, soft_alpha_pixels, opaque_pixels)"""
    Image = _pil_image()
    with Image.open(path) as img:
        if "A" not in img.getbands():
            return img.size[0] * img.size[1], 0, img.size[0] * img.size[1]
        alpha = img.convert("RGBA").getchannel("A")
        histogram = alpha.histogram()
    total = sum(histogram)
    opaque = histogram[255]
    soft = sum(histogram[1:255])
    return total, soft, opaque


def read_dominant_colors(path, count=5):
    """-> [(r, g, b), ...] most frequent colors among the non-transparent pixels."""
    Image = _pil_image()
    with Image.open(path) as img:
        rgba = img.convert("RGBA")
        small = rgba.resize((64, 64))
        quantized = small.convert("RGB").quantize(colors=max(count * 2, 8))
        palette = quantized.getpalette() or []
        counts = sorted(quantized.getcolors() or [], reverse=True)
    colors = []
    for _, index in counts[:count]:
        base = index * 3
        if base + 2 < len(palette):
            colors.append((palette[base], palette[base + 1], palette[base + 2]))
    return colors


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def report(results):
    failures = []
    for label, ok, reason in results:
        print("%s  %-18s %s" % ("PASS" if ok else "FAIL", label, reason))
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
        prog="validate_2d_asset.py",
        description="2D game-asset QA gate. Non-zero exit on any failure.")
    p.add_argument("--image", required=True, help="Path to the finished sprite/icon.")
    p.add_argument("--target", required=True, help="Expected canvas, e.g. 512x512.")
    p.add_argument("--require-pot", action="store_true",
                   help="Enforce power-of-two dimensions (engine-dependent).")
    p.add_argument("--require-alpha", action="store_true",
                   help="Run the alpha-edge quality check (cut-out sprites).")
    p.add_argument("--compare-to", default=None,
                   help="Second image to check pack palette consistency against.")
    p.add_argument("--tolerance", type=int, default=90,
                   help="Palette-consistency tolerance, Manhattan RGB (default: 90).")
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(sys.argv[1:] if argv is None else argv)
    if not os.path.exists(args.image):
        print("FAIL: image not found: %s" % args.image)
        return 1
    target_w, target_h = parse_target(args.target)

    width, height = read_image_size(args.image)
    print("Validating %s (%dx%d)\n" % (args.image, width, height))

    results = [
        ("canvas",) + check_canvas_size(width, height, target_w, target_h),
        ("power-of-two",) + check_power_of_two(width, height, required=args.require_pot),
        ("format",) + check_format(args.image),
    ]

    if args.require_alpha:
        total, soft, opaque = read_alpha_edge_stats(args.image)
        results.append(("alpha-edge",) + check_alpha_edge_quality(total, soft, opaque))

    if args.compare_to:
        if not os.path.exists(args.compare_to):
            results.append(("palette", False, "comparison image not found: %s" % args.compare_to))
        else:
            results.append(("palette",) + check_palette_consistency(
                read_dominant_colors(args.image),
                read_dominant_colors(args.compare_to),
                tolerance=args.tolerance))

    return report(results)


if __name__ == "__main__":
    sys.exit(main())
