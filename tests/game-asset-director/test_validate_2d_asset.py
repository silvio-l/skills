#!/usr/bin/env python3
"""Tests for game-asset-director/scripts/validate_2d_asset.py.

Covers the pure predicate functions only - no Pillow, no image files. A wrong
boundary here would let a non-power-of-two canvas or a haloed alpha edge report
ALL CHECKS PASSED, which is the exact plausible-but-wrong failure this repo's
test bar targets.

Run from the repo root:
    python3 tests/game-asset-director/test_validate_2d_asset.py
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "game-asset-director" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import validate_2d_asset as V  # noqa: E402


class ImportabilityTests(unittest.TestCase):
    def test_module_imports_without_pillow(self):
        """The pure/shell split means PIL is only touched by the read_* helpers."""
        self.assertNotIn("PIL", sys.modules)
        self.assertTrue(callable(V.check_canvas_size))


class CanvasSizeTests(unittest.TestCase):
    def test_exact_match_passes(self):
        ok, _ = V.check_canvas_size(512, 512, 512, 512)
        self.assertTrue(ok)

    def test_one_pixel_off_fails(self):
        ok, reason = V.check_canvas_size(513, 512, 512, 512)
        self.assertFalse(ok)
        self.assertIn("does not match", reason)

    def test_transposed_dimensions_fail(self):
        self.assertFalse(V.check_canvas_size(512, 256, 256, 512)[0])

    def test_non_square_target_matches(self):
        self.assertTrue(V.check_canvas_size(256, 512, 256, 512)[0])

    def test_zero_canvas_fails(self):
        ok, reason = V.check_canvas_size(0, 512, 0, 512)
        self.assertFalse(ok)
        self.assertIn("invalid", reason)


class PowerOfTwoTests(unittest.TestCase):
    def test_power_of_two_passes(self):
        for n in (1, 2, 256, 512, 1024, 2048):
            self.assertTrue(V.is_power_of_two(n), n)

    def test_non_power_of_two(self):
        for n in (0, -512, 3, 100, 513, 1023, 1025):
            self.assertFalse(V.is_power_of_two(n), n)

    def test_check_flags_the_offending_axis(self):
        ok, reason = V.check_power_of_two(512, 300)
        self.assertFalse(ok)
        self.assertIn("height=300", reason)
        self.assertNotIn("width", reason)

    def test_both_axes_reported(self):
        ok, reason = V.check_power_of_two(300, 300)
        self.assertFalse(ok)
        self.assertIn("width=300", reason)
        self.assertIn("height=300", reason)

    def test_not_required_passes_anything(self):
        ok, reason = V.check_power_of_two(333, 777, required=False)
        self.assertTrue(ok)
        self.assertIn("not required", reason)


class FormatTests(unittest.TestCase):
    def test_png_path_passes(self):
        self.assertTrue(V.check_format("assets/hero_idle.png")[0])

    def test_webp_passes(self):
        self.assertTrue(V.check_format("tile.webp")[0])

    def test_bare_extension_passes(self):
        self.assertTrue(V.check_format("png")[0])
        self.assertTrue(V.check_format(".png")[0])

    def test_uppercase_passes(self):
        self.assertTrue(V.check_format("SPRITE.PNG")[0])

    def test_jpeg_fails(self):
        ok, reason = V.check_format("sprite.jpg")
        self.assertFalse(ok)
        self.assertIn("not allowed", reason)
        self.assertFalse(V.check_format("sprite.jpeg")[0])

    def test_tga_fails(self):
        self.assertFalse(V.check_format("sprite.tga")[0])

    def test_custom_allowlist(self):
        self.assertTrue(V.check_format("sprite.tga", allowed=("tga",))[0])
        self.assertFalse(V.check_format("sprite.png", allowed=("tga",))[0])

    def test_dotted_filename_uses_last_extension(self):
        self.assertTrue(V.check_format("enemy.v2.final.png")[0])


class AlphaEdgeTests(unittest.TestCase):
    def test_healthy_antialiased_edge_passes(self):
        # 10000 opaque pixels with a ~800px soft silhouette band
        ok, _ = V.check_alpha_edge_quality(20000, 800, 10000)
        self.assertTrue(ok)

    def test_hard_1bit_mask_fails(self):
        ok, reason = V.check_alpha_edge_quality(20000, 0, 10000)
        self.assertFalse(ok)
        self.assertIn("1-bit", reason)

    def test_just_below_soft_minimum_fails(self):
        ok, _ = V.check_alpha_edge_quality(20000, 199, 10000)   # 0.0199 < 0.02
        self.assertFalse(ok)

    def test_exactly_at_soft_minimum_passes(self):
        ok, _ = V.check_alpha_edge_quality(20000, 200, 10000)   # 0.02
        self.assertTrue(ok)

    def test_halo_fails(self):
        ok, reason = V.check_alpha_edge_quality(20000, 5000, 10000)   # 0.5
        self.assertFalse(ok)
        self.assertIn("halo", reason)

    def test_exactly_at_stray_maximum_passes(self):
        ok, _ = V.check_alpha_edge_quality(20000, 2500, 10000)   # 0.25
        self.assertTrue(ok)

    def test_subject_removed_fails(self):
        ok, reason = V.check_alpha_edge_quality(20000, 300, 0)
        self.assertFalse(ok)
        self.assertIn("removed the subject", reason)

    def test_empty_image_fails(self):
        self.assertFalse(V.check_alpha_edge_quality(0, 0, 0)[0])


class PaletteConsistencyTests(unittest.TestCase):
    def test_identical_palettes_pass(self):
        pal = [(200, 30, 30), (20, 20, 40), (240, 220, 180)]
        ok, _ = V.check_palette_consistency(pal, pal)
        self.assertTrue(ok)

    def test_slight_drift_within_tolerance_passes(self):
        a = [(200, 30, 30), (20, 20, 40)]
        b = [(210, 40, 45), (25, 30, 35)]   # max Manhattan distance 35
        self.assertTrue(V.check_palette_consistency(a, b)[0])

    def test_different_palette_fails(self):
        a = [(200, 30, 30)]
        b = [(20, 200, 220)]
        ok, reason = V.check_palette_consistency(a, b)
        self.assertFalse(ok)
        self.assertIn("no match", reason)

    def test_tolerance_boundary(self):
        a = [(100, 100, 100)]
        b = [(130, 130, 130)]   # Manhattan distance exactly 90
        self.assertTrue(V.check_palette_consistency(a, b, tolerance=90)[0])
        self.assertFalse(V.check_palette_consistency(a, b, tolerance=89)[0])

    def test_extra_colors_in_b_are_fine(self):
        a = [(10, 10, 10)]
        b = [(10, 10, 10), (250, 0, 0), (0, 250, 0)]
        self.assertTrue(V.check_palette_consistency(a, b)[0])

    def test_rgba_tuples_ignore_alpha(self):
        a = [(10, 10, 10, 255)]
        b = [(10, 10, 10, 0)]
        self.assertTrue(V.check_palette_consistency(a, b)[0])

    def test_missing_data_fails(self):
        self.assertFalse(V.check_palette_consistency([], [(1, 2, 3)])[0])
        self.assertFalse(V.check_palette_consistency([(1, 2, 3)], [])[0])


class ParseTargetTests(unittest.TestCase):
    def test_parses_dimensions(self):
        self.assertEqual(V.parse_target("512x512"), (512, 512))
        self.assertEqual(V.parse_target("1024X768"), (1024, 768))
        self.assertEqual(V.parse_target(" 256 x 256 "), (256, 256))

    def test_rejects_garbage(self):
        with self.assertRaises(ValueError):
            V.parse_target("512")
        with self.assertRaises(ValueError):
            V.parse_target("512x512x512")


class ReportTests(unittest.TestCase):
    def test_all_pass_returns_zero(self):
        self.assertEqual(V.report([("canvas", True, "ok")]), 0)

    def test_any_failure_returns_one(self):
        self.assertEqual(V.report([("canvas", True, "ok"), ("format", False, "bad")]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
