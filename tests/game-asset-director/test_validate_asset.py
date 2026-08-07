#!/usr/bin/env python3
"""Tests for game-asset-director/scripts/validate_asset.py.

Covers the pure predicate functions only - no bpy, no Blender install needed.
A boundary off-by-one in one of these would make the validator print
ALL CHECKS PASSED on a genuinely broken asset, silently defeating the entire
validation step. That is the failure mode these tests exist for.

Run from the repo root:
    python3 tests/game-asset-director/test_validate_asset.py
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "game-asset-director" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import validate_asset as V  # noqa: E402


class ImportabilityTests(unittest.TestCase):
    def test_module_imports_without_blender(self):
        """The whole point of the pure/shell split: no bpy at import time."""
        self.assertNotIn("bpy", sys.modules)
        self.assertTrue(callable(V.check_tri_budget))


class TriBudgetTests(unittest.TestCase):
    def test_character_at_lower_bound_passes(self):
        ok, _ = V.check_tri_budget(3000, "character")
        self.assertTrue(ok)

    def test_character_at_upper_bound_passes(self):
        ok, _ = V.check_tri_budget(10000, "character")
        self.assertTrue(ok)

    def test_character_one_over_budget_fails(self):
        ok, reason = V.check_tri_budget(10001, "character")
        self.assertFalse(ok)
        self.assertIn("exceeds", reason)

    def test_character_one_under_budget_fails(self):
        ok, reason = V.check_tri_budget(2999, "character")
        self.assertFalse(ok)
        self.assertIn("below", reason)

    def test_prop_bounds(self):
        self.assertTrue(V.check_tri_budget(100, "prop")[0])
        self.assertTrue(V.check_tri_budget(2000, "prop")[0])
        self.assertFalse(V.check_tri_budget(99, "prop")[0])
        self.assertFalse(V.check_tri_budget(2001, "prop")[0])

    def test_character_budget_is_not_prop_budget(self):
        """5000 tris is fine for a character and far over budget for a prop."""
        self.assertTrue(V.check_tri_budget(5000, "character")[0])
        self.assertFalse(V.check_tri_budget(5000, "prop")[0])

    def test_unknown_class_fails_loudly(self):
        ok, reason = V.check_tri_budget(5000, "vehicle")
        self.assertFalse(ok)
        self.assertIn("unknown asset class", reason)

    def test_zero_tris_fails(self):
        self.assertFalse(V.check_tri_budget(0, "prop")[0])


class UvShellTests(unittest.TestCase):
    def test_two_disjoint_shells_pass(self):
        shells = [
            [(0.0, 0.0), (0.4, 0.0), (0.4, 0.4), (0.0, 0.4)],
            [(0.5, 0.5), (0.9, 0.5), (0.9, 0.9), (0.5, 0.9)],
        ]
        ok, _ = V.check_uv_shells(shells)
        self.assertTrue(ok)

    def test_touching_shells_do_not_count_as_overlap(self):
        """Edge-to-edge islands share a boundary but no area."""
        shells = [
            [(0.0, 0.0), (0.5, 0.0), (0.5, 0.5), (0.0, 0.5)],
            [(0.5, 0.0), (1.0, 0.0), (1.0, 0.5), (0.5, 0.5)],
        ]
        self.assertTrue(V.check_uv_shells(shells)[0])

    def test_stacked_shells_fail(self):
        """Two islands on top of each other - the failure that corrupts a bake."""
        shells = [
            [(0.1, 0.1), (0.6, 0.1), (0.6, 0.6), (0.1, 0.6)],
            [(0.12, 0.12), (0.58, 0.12), (0.58, 0.58), (0.12, 0.58)],
        ]
        ok, reason = V.check_uv_shells(shells)
        self.assertFalse(ok)
        self.assertIn("stacked", reason)

    def test_lightly_clipping_boxes_pass(self):
        """Tightly packed islands routinely clip bounding boxes without sharing
        texel area - flagging those would fail every well-packed unwrap."""
        shells = [
            [(0.0, 0.0), (0.6, 0.0), (0.6, 0.6), (0.0, 0.6)],
            [(0.55, 0.55), (1.0, 0.55), (1.0, 1.0), (0.55, 1.0)],
        ]
        self.assertTrue(V.check_uv_shells(shells)[0])

    def test_small_shell_buried_in_a_large_one_fails(self):
        shells = [
            [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)],
            [(0.4, 0.4), (0.5, 0.4), (0.5, 0.5), (0.4, 0.5)],
        ]
        ok, reason = V.check_uv_shells(shells)
        self.assertFalse(ok)
        self.assertIn("stacked", reason)

    def test_degenerate_zero_area_shell_fails(self):
        shells = [
            [(0.1, 0.1), (0.9, 0.1), (0.9, 0.9), (0.1, 0.9)],
            [(0.5, 0.2), (0.5, 0.8)],   # a line: zero area
        ]
        self.assertFalse(V.check_uv_shells(shells)[0])

    def test_shell_outside_upper_bound_fails(self):
        shells = [[(0.5, 0.5), (1.2, 0.5), (1.2, 0.9), (0.5, 0.9)]]
        ok, reason = V.check_uv_shells(shells)
        self.assertFalse(ok)
        self.assertIn("0-1 space", reason)

    def test_shell_with_negative_uv_fails(self):
        shells = [[(-0.01, 0.1), (0.5, 0.1), (0.5, 0.5), (-0.01, 0.5)]]
        self.assertFalse(V.check_uv_shells(shells)[0])

    def test_exactly_full_unit_square_passes(self):
        shells = [[(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]]
        self.assertTrue(V.check_uv_shells(shells)[0])

    def test_no_shells_fails(self):
        ok, reason = V.check_uv_shells([])
        self.assertFalse(ok)
        self.assertIn("no UV shells", reason)

    def test_empty_shell_fails(self):
        self.assertFalse(V.check_uv_shells([[]])[0])


class UvPaddingTests(unittest.TestCase):
    @staticmethod
    def _box(u0, u1, v0, v1):
        return [(u0, v0), (u1, v0), (u1, v1), (u0, v1)]

    def test_single_shell_has_nothing_to_check(self):
        ok, reason = V.check_uv_padding([self._box(0.1, 0.9, 0.1, 0.9)], 1024)
        self.assertTrue(ok)
        self.assertIn("single UV shell", reason)

    def test_healthy_gap_passes(self):
        # 0.02 gap at 1024px = ~20 texels
        shells = [self._box(0.0, 0.4, 0.0, 0.4), self._box(0.42, 0.8, 0.0, 0.4)]
        ok, reason = V.check_uv_padding(shells, 1024)
        self.assertTrue(ok)
        self.assertIn("20.5 texels", reason)

    def test_exactly_at_minimum_passes(self):
        # gap 0.002 at 1024px = 2.048 texels, minimum 2
        shells = [self._box(0.0, 0.4, 0.0, 0.4), self._box(0.402, 0.8, 0.0, 0.4)]
        self.assertTrue(V.check_uv_padding(shells, 1024, min_texels=2)[0])

    def test_one_under_minimum_fails(self):
        # gap 0.001 at 1024px = 1.024 texels
        shells = [self._box(0.0, 0.4, 0.0, 0.4), self._box(0.401, 0.8, 0.0, 0.4)]
        ok, reason = V.check_uv_padding(shells, 1024, min_texels=2)
        self.assertFalse(ok)
        self.assertIn("raise --margin", reason)

    def test_touching_islands_fail(self):
        shells = [self._box(0.0, 0.4, 0.0, 0.4), self._box(0.4, 0.8, 0.0, 0.4)]
        self.assertFalse(V.check_uv_padding(shells, 1024)[0])

    def test_same_gap_is_stricter_at_higher_resolution(self):
        """A margin that survives at 512px can be too tight at 2048px."""
        shells = [self._box(0.0, 0.4, 0.0, 0.4), self._box(0.4015, 0.8, 0.0, 0.4)]
        self.assertFalse(V.check_uv_padding(shells, 512, min_texels=2)[0])   # 0.77 texels
        self.assertTrue(V.check_uv_padding(shells, 2048, min_texels=2)[0])   # 3.07 texels

    def test_separation_on_either_axis_counts(self):
        """Islands stacked in u but far apart in v are still separated."""
        shells = [self._box(0.0, 0.4, 0.0, 0.3), self._box(0.0, 0.4, 0.5, 0.8)]
        self.assertTrue(V.check_uv_padding(shells, 1024)[0])

    def test_invalid_texture_size_fails(self):
        shells = [self._box(0.0, 0.4, 0.0, 0.4), self._box(0.5, 0.8, 0.0, 0.4)]
        self.assertFalse(V.check_uv_padding(shells, 0)[0])


class NgonTests(unittest.TestCase):
    def test_all_quads_pass(self):
        ok, _ = V.check_ngons([4] * 12)
        self.assertTrue(ok)

    def test_all_tris_pass(self):
        self.assertTrue(V.check_ngons([3] * 20)[0])

    def test_mixed_tris_and_quads_pass(self):
        ok, reason = V.check_ngons([3, 4, 4, 3, 4])
        self.assertTrue(ok)
        self.assertIn("3 quads", reason)

    def test_single_ngon_fails(self):
        ok, reason = V.check_ngons([4, 4, 5, 4])
        self.assertFalse(ok)
        self.assertIn("n-gon", reason)

    def test_reports_largest_ngon(self):
        ok, reason = V.check_ngons([4, 7, 5])
        self.assertFalse(ok)
        self.assertIn("7", reason)

    def test_degenerate_face_fails(self):
        ok, reason = V.check_ngons([4, 2, 4])
        self.assertFalse(ok)
        self.assertIn("degenerate", reason)

    def test_no_faces_fails(self):
        self.assertFalse(V.check_ngons([])[0])


class TextureDimTests(unittest.TestCase):
    def test_2k_character_passes(self):
        self.assertTrue(V.check_texture_dims(2048, 2048, "character")[0])

    def test_1k_character_passes(self):
        self.assertTrue(V.check_texture_dims(1024, 1024, "character")[0])

    def test_512_character_below_minimum_fails(self):
        ok, reason = V.check_texture_dims(512, 512, "character")
        self.assertFalse(ok)
        self.assertIn("below", reason)

    def test_2k_prop_over_maximum_fails(self):
        ok, reason = V.check_texture_dims(2048, 2048, "prop")
        self.assertFalse(ok)
        self.assertIn("exceeds", reason)

    def test_512_prop_passes(self):
        self.assertTrue(V.check_texture_dims(512, 512, "prop")[0])

    def test_non_power_of_two_fails(self):
        ok, reason = V.check_texture_dims(1000, 1000, "character")
        self.assertFalse(ok)
        self.assertIn("power-of-two", reason)

    def test_off_by_one_from_power_of_two_fails(self):
        self.assertFalse(V.check_texture_dims(1023, 1023, "character")[0])
        self.assertFalse(V.check_texture_dims(1025, 1025, "character")[0])

    def test_non_square_fails(self):
        ok, reason = V.check_texture_dims(2048, 1024, "character")
        self.assertFalse(ok)
        self.assertIn("square", reason)

    def test_zero_is_not_power_of_two(self):
        self.assertFalse(V.is_power_of_two(0))
        self.assertFalse(V.is_power_of_two(-8))
        self.assertTrue(V.is_power_of_two(1))


class LodChainTests(unittest.TestCase):
    def test_exact_75_percent_chain_passes(self):
        ok, _ = V.check_lod_chain([8000, 2000, 500])
        self.assertTrue(ok)

    def test_within_tolerance_passes(self):
        self.assertTrue(V.check_lod_chain([8000, 2400])[0])   # 70% drop
        self.assertTrue(V.check_lod_chain([8000, 1600])[0])   # 80% drop

    def test_too_shallow_reduction_fails(self):
        ok, reason = V.check_lod_chain([8000, 6000])          # 25% drop
        self.assertFalse(ok)
        self.assertIn("only drops", reason)

    def test_too_aggressive_reduction_fails(self):
        ok, reason = V.check_lod_chain([8000, 100])
        self.assertFalse(ok)
        self.assertIn("too aggressive", reason)

    def test_single_level_is_not_a_chain(self):
        self.assertFalse(V.check_lod_chain([8000])[0])


class ReportTests(unittest.TestCase):
    def test_all_pass_returns_zero(self):
        self.assertEqual(V.report([("a", True, "fine"), ("b", True, "fine")]), 0)

    def test_any_failure_returns_one(self):
        self.assertEqual(V.report([("a", True, "fine"), ("b", False, "broken")]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
