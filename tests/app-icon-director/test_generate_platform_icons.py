#!/usr/bin/env python3
"""Regression tests for the platform icon generator, focused on the exact
class of bug that's easy to reintroduce silently: opaque vs. alpha-preserving
output per platform (Apple's App Store icon must be opaque; Google Play
Console's listing icon must keep alpha; a classic Windows .ico keeps alpha
too). Dimensions are also checked since a resize regression is just as silent.

Run: python3 tests/app-icon-director/test_generate_platform_icons.py

Uses an in-memory synthetic master (no rsvg-convert dependency) so this runs
anywhere Pillow is installed. macOS-only parts (iconutil-based .icns) are
skipped when iconutil isn't present rather than faked.
"""
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "app-icon-director" / "scripts"))

from PIL import Image, ImageDraw  # noqa: E402

import generate_platform_icons as gpi  # noqa: E402


def synthetic_master(size=1024):
    # Left half opaque, right half fully transparent, so alpha-loss on resize
    # or on an accidental opaque-flatten is directly detectable afterwards.
    im = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(im)
    draw.rectangle([0, 0, size // 2, size], fill=(59, 130, 246, 255))
    return im


class TestPlatformIconGeneration(unittest.TestCase):
    def setUp(self):
        self.master = synthetic_master(1024)
        self.tmp = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_ios_icon_is_opaque_and_1024(self):
        expected = []
        gpi.generate_ios(self.master, self.tmp, expected)
        path = self.tmp / "ios" / "AppIcon-1024.png"
        im = Image.open(path)
        self.assertEqual(im.size, (1024, 1024))
        self.assertEqual(im.mode, "RGB", "App Store Connect icon must not carry an alpha channel")

    def test_android_play_store_icon_keeps_alpha_and_512(self):
        expected = []
        gpi.generate_android(self.master, self.tmp, expected, foreground=None)
        path = self.tmp / "android" / "play-store-icon.png"
        im = Image.open(path).convert("RGBA")
        self.assertEqual(im.size, (512, 512))
        self.assertEqual(im.mode, "RGBA", "Play Console listing icon must be 32-bit PNG with alpha")
        # right half of the synthetic master was fully transparent -- confirm
        # that transparency actually survived the resize, not just the mode tag.
        right_half_alpha = im.getpixel((im.width - 5, im.height // 2))[3]
        self.assertEqual(right_half_alpha, 0)

    def test_windows_ico_contains_documented_minimum_sizes(self):
        expected = []
        gpi.generate_windows(self.master, self.tmp, expected)
        path = self.tmp / "windows" / "icon.ico"
        sizes = Image.open(path).info.get("sizes", set())
        for s in gpi.WINDOWS_ICO_SIZES:
            self.assertIn((s, s), sizes, f"missing documented minimum ICO size {s}x{s}")

    def test_android_launcher_mipmap_sizes(self):
        expected = []
        gpi.generate_android(self.master, self.tmp, expected, foreground=None)
        for mipmap, size in gpi.ANDROID_MIPMAP.items():
            im = Image.open(self.tmp / "android" / mipmap / "ic_launcher.png")
            self.assertEqual(im.size, (size, size), mipmap)

    @unittest.skipUnless(shutil.which("iconutil"), "iconutil is macOS-only")
    def test_macos_icns_is_produced(self):
        expected, report = [], []
        gpi.generate_macos(self.master, self.tmp, expected, report)
        icns_path = self.tmp / "macos" / "AppIcon.icns"
        self.assertTrue(icns_path.exists())
        Image.open(icns_path).load()  # raises if not a structurally valid .icns


if __name__ == "__main__":
    unittest.main()
