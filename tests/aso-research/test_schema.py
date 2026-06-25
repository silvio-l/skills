#!/usr/bin/env python3
"""Tests for schema mapping (slice 02): raw store JSON -> Core + Slots.

Run from the repo root:
    python3 tests/aso-research/test_schema.py

Covers the offline-testable pure logic only (no network/browser):
HTML/dropped-tag stripping in the description slot, subtitle
mis-fielding (subtitle not in iTunes JSON -> empty until browser merge),
keyword_hints inference by inversion, the browser-slot merge, and the
discovery ``similar_app_ids`` de-dup.
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import schema  # noqa: E402

RAW_WITH_HTML_DESC = {
    "trackId": 111,
    "trackName": "Habit Hero",
    "artistName": "HeroCo",
    "primaryGenreName": "Health & Fitness",
    "description": "A <b>gamified</b> habit tracker.<br/>Build <p>streaks</p> & routines.",
    "formattedPrice": "Gratis",
    "price": 0.0,
    "screenshotUrls": ["a"],
}

RAW_NO_DESC = {
    "trackId": 222,
    "trackName": "Calm Sleep",
    "primaryGenreName": "Health & Fitness",
}


class StripHtmlTests(unittest.TestCase):
    def test_strips_tags_and_collapses_whitespace(self):
        self.assertEqual(schema.strip_html("A <b>gamified</b> habit.<br/>"), "A gamified habit.")

    def test_dropped_tags_leave_clean_text(self):
        out = schema.strip_html("Build <p>streaks</p> &amp; <div>routines</div>")
        self.assertNotIn("<", out)
        self.assertNotIn(">", out)
        self.assertIn("streaks", out)
        self.assertIn("routines", out)

    def test_empty_input(self):
        self.assertEqual(schema.strip_html(""), "")
        self.assertEqual(schema.strip_html(None), "")


class MapCoreSlotsTests(unittest.TestCase):
    def test_description_slot_populated_and_html_stripped(self):
        core = schema.map_itunes_to_core(RAW_WITH_HTML_DESC)
        self.assertNotIn("<b>", core["description"])
        self.assertIn("gamified", core["description"])
        self.assertIn("streaks", core["description"])

    def test_subtitle_mis_fielding_stays_empty_without_browser(self):
        # iTunes JSON never carries the subtitle -> empty until browser merge
        core = schema.map_itunes_to_core(RAW_WITH_HTML_DESC)
        self.assertEqual(core["subtitle"], "")

    def test_keyword_hints_inferred_by_inversion(self):
        core = schema.map_itunes_to_core(RAW_WITH_HTML_DESC)
        # title tokens drive the hints
        self.assertIn("habit", core["keyword_hints"])
        self.assertIn("hero", core["keyword_hints"])

    def test_dropped_tags_handling_on_missing_description(self):
        core = schema.map_itunes_to_core(RAW_NO_DESC)
        self.assertEqual(core["description"], "")
        # title tokens still drive inversion hints ("Calm Sleep")
        self.assertEqual(core["keyword_hints"], ["calm", "sleep"])

    def test_similar_app_ids_slot_present_empty(self):
        core = schema.map_itunes_to_core(RAW_WITH_HTML_DESC)
        self.assertEqual(core["similar_app_ids"], [])


class MergeAppleSlotsTests(unittest.TestCase):
    def setUp(self):
        self.core = schema.map_itunes_to_core(RAW_WITH_HTML_DESC)

    def test_subtitle_merge_fills_slot_and_reinfers_hints(self):
        merged = schema.merge_apple_slots(self.core, subtitle="Gewohnheits-Tracker")
        self.assertEqual(merged["subtitle"], "Gewohnheits-Tracker")
        # subtitle is a high-signal field -> its tokens join the hints
        self.assertIn("gewohnheits", merged["keyword_hints"])
        self.assertIn("tracker", merged["keyword_hints"])

    def test_merge_does_not_mutate_input(self):
        before = dict(self.core)
        schema.merge_apple_slots(self.core, subtitle="X", similar_app_ids=["1"])
        self.assertEqual(self.core, before)

    def test_similar_app_ids_dedup_and_coerce(self):
        merged = schema.merge_apple_slots(self.core, similar_app_ids=["3", " 3 ", "5", ""])
        self.assertEqual(merged["similar_app_ids"], ["3", "5"])

    def test_subtitle_html_stripped_on_merge(self):
        merged = schema.merge_apple_slots(self.core, subtitle="<i>Routine</i> & Ruhe")
        self.assertNotIn("<", merged["subtitle"])
        self.assertIn("Routine", merged["subtitle"])


if __name__ == "__main__":
    unittest.main()
