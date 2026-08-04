#!/usr/bin/env python3
"""Generate and validate platform-native app icon asset sets from a single
vector or high-resolution raster master: macOS (.icns), Windows (.ico),
iOS (App Store Connect PNG), Android (launcher mipmaps, optional adaptive
icon, Play Store listing icon), and optionally the full Microsoft Store
MSIX asset set (windows-store).

Sizes and formats are taken from each platform's own current published
spec, not guessed: Apple App Store Connect (1024x1024, opaque, no alpha),
Google Play Console (512x512, 32-bit PNG *with* alpha), and Microsoft
Learn's Windows app icon construction + MSIX package requirements docs
(classic .ico bare minimum 16/24/32/48/256; MSIX Store minimum is the
AppList target-size set in three plate variants, StoreLogo at five scale
factors, and one Medium tile at 100%).

Every run ends with a deterministic validation pass: every file the
platform spec says must exist is checked for existence, valid image data,
and correct pixel dimensions. Nothing is left to "looks about right."

Requires: Pillow (pip install pillow).
SVG masters additionally require rsvg-convert (brew install librsvg, or
apt install librsvg2-bin); a pre-rendered >=1024px square PNG master can
be used instead to skip that dependency.
macOS .icns packaging additionally uses `iconutil` (built into macOS). On
a non-macOS host the .iconset folder is still produced, but the final
.icns packaging step is skipped with an explicit note in the report.
"""

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

try:
    from PIL import Image
except ImportError:
    print("Error: Pillow is required. Install with: pip install pillow", file=sys.stderr)
    sys.exit(1)

PLATFORMS = ["ios", "macos", "windows", "windows-store", "android"]

MACOS_ICONSET = {
    "icon_16x16.png": 16,
    "icon_16x16@2x.png": 32,
    "icon_32x32.png": 32,
    "icon_32x32@2x.png": 64,
    "icon_128x128.png": 128,
    "icon_128x128@2x.png": 256,
    "icon_256x256.png": 256,
    "icon_256x256@2x.png": 512,
    "icon_512x512.png": 512,
    "icon_512x512@2x.png": 1024,
}
# Microsoft Learn's documented Win32/.ico "bare minimum": 16, 24, 32, 48, 256.
WINDOWS_ICO_SIZES = [16, 24, 32, 48, 256]

# MSIX Store-publish minimum, per learn.microsoft.com/windows/apps/design/iconography/app-icon-construction:
# the 14 AppList target sizes in three plate variants, StoreLogo at five scale
# factors, and one Medium tile at 100% (Windows 11 no longer needs the rest of
# the tile set; Store publishing still requires this one).
WINDOWS_STORE_APPLIST_SIZES = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256]
WINDOWS_STORE_APPLIST_VARIANTS = ["", "_altform-unplated", "_altform-lightunplated"]
WINDOWS_STORE_LOGO_SCALES = {"scale-100": 50, "scale-125": 63, "scale-150": 75, "scale-200": 100, "scale-400": 200}
WINDOWS_STORE_MEDTILE_SIZE = 150

ANDROID_MIPMAP = {"mipmap-mdpi": 48, "mipmap-hdpi": 72, "mipmap-xhdpi": 96, "mipmap-xxhdpi": 144, "mipmap-xxxhdpi": 192}
ANDROID_ADAPTIVE_MIPMAP = {"mipmap-mdpi": 108, "mipmap-hdpi": 162, "mipmap-xhdpi": 216, "mipmap-xxhdpi": 324, "mipmap-xxxhdpi": 432}


def render_svg_master(svg_path: Path, size: int, out_png: Path):
    if shutil.which("rsvg-convert") is None:
        print(
            "Error: master is an .svg but rsvg-convert is not installed "
            "(brew install librsvg). Pre-render a >=1024px PNG instead and pass it with --master.",
            file=sys.stderr,
        )
        sys.exit(1)
    subprocess.run(
        ["rsvg-convert", "-w", str(size), "-h", str(size), str(svg_path), "-o", str(out_png)],
        check=True,
    )


def load_master(master_path: Path, work_dir: Path) -> Image.Image:
    if master_path.suffix.lower() == ".svg":
        rendered = work_dir / "_master_2048.png"
        render_svg_master(master_path, 2048, rendered)
        im = Image.open(rendered).convert("RGBA")
    else:
        im = Image.open(master_path).convert("RGBA")
    if im.width != im.height:
        print(f"Error: master must be square, got {im.width}x{im.height}", file=sys.stderr)
        sys.exit(1)
    if im.width < 1024:
        print(f"Warning: master is only {im.width}px; upscaling below 1024px degrades quality.", file=sys.stderr)
    return im


def resized(im: Image.Image, size: int) -> Image.Image:
    return im.resize((size, size), Image.LANCZOS)


def flatten_to_opaque(im: Image.Image, bg=(255, 255, 255)) -> Image.Image:
    base = Image.new("RGB", im.size, bg)
    base.paste(im, mask=im.split()[3] if im.mode == "RGBA" else None)
    return base


def write_png(im: Image.Image, size: int, out_path: Path, opaque: bool = False):
    out_path.parent.mkdir(parents=True, exist_ok=True)
    scaled = resized(im, size)
    if opaque:
        scaled = flatten_to_opaque(scaled)
    scaled.save(out_path)


def generate_ios(master: Image.Image, out_dir: Path, expected: list):
    path = out_dir / "ios" / "AppIcon-1024.png"
    write_png(master, 1024, path, opaque=True)
    expected.append((path, 1024, 1024))


def generate_macos(master: Image.Image, out_dir: Path, expected: list, report: list):
    iconset_dir = out_dir / "macos" / "AppIcon.iconset"
    for name, size in MACOS_ICONSET.items():
        path = iconset_dir / name
        write_png(master, size, path)
        expected.append((path, size, size))
    icns_path = out_dir / "macos" / "AppIcon.icns"
    if shutil.which("iconutil") is None:
        report.append("macOS: iconutil not found (macOS-only tool) — .iconset written, .icns packaging skipped.")
        return
    icns_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(["iconutil", "-c", "icns", str(iconset_dir), "-o", str(icns_path)], check=True)
    expected.append((icns_path, None, None))  # dimension check handled specially for .icns


def generate_windows(master: Image.Image, out_dir: Path, expected: list):
    """Classic Win32 .ico. Transparency is standard here (non-square silhouettes
    on a transparent background are the norm), unlike the store-listing icons."""
    path = out_dir / "windows" / "icon.ico"
    path.parent.mkdir(parents=True, exist_ok=True)
    resized(master, 256).save(path, sizes=[(s, s) for s in WINDOWS_ICO_SIZES])
    expected.append((path, None, None))  # dimension check handled specially for .ico


def generate_windows_store(master: Image.Image, out_dir: Path, expected: list):
    """Minimum MSIX asset set required to publish to the Microsoft Store, per
    Microsoft Learn's app-icon-construction doc: AppList target-size assets in
    three plate variants, StoreLogo at five scale factors, one Medium tile."""
    applist_dir = out_dir / "windows-store" / "AppList"
    for size in WINDOWS_STORE_APPLIST_SIZES:
        for variant in WINDOWS_STORE_APPLIST_VARIANTS:
            path = applist_dir / f"AppList.targetsize-{size}{variant}.png"
            write_png(master, size, path)
            expected.append((path, size, size))

    storelogo_dir = out_dir / "windows-store" / "StoreLogo"
    for scale_name, px in WINDOWS_STORE_LOGO_SCALES.items():
        path = storelogo_dir / f"StoreLogo.{scale_name}.png"
        write_png(master, px, path)
        expected.append((path, px, px))

    medtile_path = out_dir / "windows-store" / "Tiles" / "MedTile.scale-100.png"
    write_png(master, WINDOWS_STORE_MEDTILE_SIZE, medtile_path)
    expected.append((medtile_path, WINDOWS_STORE_MEDTILE_SIZE, WINDOWS_STORE_MEDTILE_SIZE))


def generate_android(master: Image.Image, out_dir: Path, expected: list, foreground: Image.Image | None):
    for mipmap, size in ANDROID_MIPMAP.items():
        path = out_dir / "android" / mipmap / "ic_launcher.png"
        write_png(master, size, path)
        expected.append((path, size, size))
    # Play Console requires a 32-bit PNG *with* alpha for the store listing icon
    # (unlike Apple's App Store icon, which must be opaque) -- do not flatten.
    play_store_path = out_dir / "android" / "play-store-icon.png"
    write_png(master, 512, play_store_path, opaque=False)
    expected.append((play_store_path, 512, 512))

    if foreground is not None:
        for mipmap, size in ANDROID_ADAPTIVE_MIPMAP.items():
            fg_path = out_dir / "android" / mipmap / "ic_launcher_foreground.png"
            write_png(foreground, size, fg_path)
            expected.append((fg_path, size, size))


def validate(expected: list, ico_paths: list, icns_paths: list) -> bool:
    ok = True
    print("\n--- Validation ---")
    for path, w, h in expected:
        if not path.exists():
            print(f"FAIL  missing file: {path}")
            ok = False
            continue
        try:
            im = Image.open(path)
            im.load()
        except Exception as e:
            print(f"FAIL  unreadable image: {path} ({e})")
            ok = False
            continue
        if w is not None and im.size != (w, h):
            print(f"FAIL  wrong size: {path} expected {w}x{h}, got {im.size}")
            ok = False
        else:
            print(f"OK    {path}" + (f"  ({im.size[0]}x{im.size[1]})" if w else ""))

    for path in ico_paths:
        if not path.exists():
            continue
        sizes = Image.open(path).info.get("sizes", set())
        missing = [s for s in WINDOWS_ICO_SIZES if (s, s) not in sizes]
        if missing:
            print(f"FAIL  {path}: missing embedded sizes {missing}")
            ok = False
        else:
            print(f"OK    {path}  (embedded sizes: {sorted(sizes)})")

    for path in icns_paths:
        if not path.exists():
            print(f"FAIL  missing file: {path}")
            ok = False
            continue
        # The .iconset source PNGs are already validated at exact pixel sizes above
        # (that's the real correctness guarantee); Pillow's ICNS size introspection
        # reports point-size@scale tuples rather than raw pixels and is not a
        # reliable independent cross-check, so we only confirm the container itself
        # is a structurally valid ICNS that iconutil actually produced.
        try:
            Image.open(path).load()
            print(f"OK    {path}  (valid .icns container)")
        except Exception as e:
            print(f"FAIL  unreadable .icns: {path} ({e})")
            ok = False

    print(f"\n{'ALL CHECKS PASSED' if ok else 'VALIDATION FAILED'}")
    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--master", required=True, type=Path, help="Master icon: .svg or a square PNG >=1024px")
    parser.add_argument("--foreground", type=Path, default=None, help="Optional Android adaptive-icon foreground layer (.svg or transparent PNG)")
    parser.add_argument("--out", required=True, type=Path, help="Output directory")
    parser.add_argument(
        "--platforms",
        default="ios,macos,windows,android",
        help=f"Comma-separated subset of: {','.join(PLATFORMS)}. 'windows-store' (full MSIX Store asset set, ~50 files) is opt-in, not in the default set.",
    )
    args = parser.parse_args()

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    unknown = set(platforms) - set(PLATFORMS)
    if unknown:
        print(f"Error: unknown platform(s) {unknown}. Valid: {PLATFORMS}", file=sys.stderr)
        sys.exit(1)

    args.out.mkdir(parents=True, exist_ok=True)
    master = load_master(args.master, args.out)
    foreground = load_master(args.foreground, args.out) if args.foreground else None

    expected = []
    report = []
    ico_paths, icns_paths = [], []

    if "ios" in platforms:
        generate_ios(master, args.out, expected)
    if "macos" in platforms:
        generate_macos(master, args.out, expected, report)
        icns_paths.append(args.out / "macos" / "AppIcon.icns")
    if "windows" in platforms:
        generate_windows(master, args.out, expected)
        ico_paths.append(args.out / "windows" / "icon.ico")
    if "windows-store" in platforms:
        generate_windows_store(master, args.out, expected)
    if "android" in platforms:
        generate_android(master, args.out, expected, foreground)

    # Strip the dimension-less .icns/.ico placeholders from the plain-file
    # check list; they're validated separately via embedded-size introspection.
    plain_expected = [(p, w, h) for (p, w, h) in expected if w is not None]
    # Still confirm the containers exist as files even if empty due to a failed subprocess.
    for p in icns_paths + ico_paths:
        if p.exists():
            plain_expected.append((p, None, None))

    for line in report:
        print(line)

    ok = validate(plain_expected, ico_paths, icns_paths)
    manifest_path = args.out / "manifest.json"
    manifest_path.write_text(
        json.dumps({"platforms": platforms, "files": [str(p) for p, _, _ in plain_expected]}, indent=2)
    )
    sys.exit(0 if ok else 2)


if __name__ == "__main__":
    main()
