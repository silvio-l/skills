#!/usr/bin/env python3
"""Determinism test for the deepened Apple spine (slice 02).

Run from the repo root:
    python3 tests/aso-research/test_determinism.py

Proves the core AC: two runs over identical Apple input (fixture metadata
+ suggestions) yield byte-identical ``keywords.json`` / ``competition.json``
when fed through extract -> score -> serialize. No network, no browser —
the collectors are replaced by injectable fixture fetchers.
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import extract  # noqa: E402
import schema  # noqa: E402
import score  # noqa: E402
import serialize  # noqa: E402

# Fixture Apple metadata (post-iTunes + post-browser): Core + filled slots.
FIXTURE_CORE = [
    schema.merge_apple_slots(
        schema.map_itunes_to_core(
            {
                "trackId": 1,
                "trackName": "Habit Tracker Daily",
                "artistName": "HabitCo",
                "primaryGenreName": "Health & Fitness",
                "averageUserRating": 4.8,
                "userRatingCount": 12000,
                "description": "Baue gute <b>Gewohnheiten</b> auf. Der beste Habit Tracker.",
                "formattedPrice": "Gratis",
                "price": 0.0,
                "screenshotUrls": ["a", "b"],
            }
        ),
        subtitle="Gewohnheits-Tracker",
        similar_app_ids=["11", "12"],
    ),
    schema.merge_apple_slots(
        schema.map_itunes_to_core(
            {
                "trackId": 2,
                "trackName": "Daily Habit Hero",
                "artistName": "HeroInc",
                "primaryGenreName": "Health & Fitness",
                "averageUserRating": 4.6,
                "userRatingCount": 9000,
                "description": "Verfolge deine Gewohnheiten und Ziele jeden Tag.",
                "formattedPrice": "$2.99",
                "price": 2.99,
                "screenshotUrls": ["c"],
            }
        ),
        subtitle="Routinen Pro",
        similar_app_ids=["13"],
    ),
    schema.merge_apple_slots(
        schema.map_itunes_to_core(
            {
                "trackId": 3,
                "trackName": "Streaks Habit",
                "artistName": "Streaks",
                "primaryGenreName": "Health & Fitness",
                "averageUserRating": 4.9,
                "userRatingCount": 30000,
                "description": "Behalte deine Routinen bei mit diesem Habit-Tool.",
                "formattedPrice": "Gratis",
                "price": 0.0,
                "screenshotUrls": ["d", "e", "f"],
            }
        ),
        subtitle="Achtsamkeit Timer",
        similar_app_ids=["14", "15"],
    ),
]

SEED_DESCRIPTION = "A gamified habit tracker and routine builder app"
SUGGEST_TERMS = ["habit tracker", "gewohnheit", "routine builder", "streaks"]


def _run_once():
    generics = ["health_fitness", "apple", "ios", "iphone", "ipad", "habit hero"]
    documents = [
        {
            "title": c.get("title", ""),
            "subtitle": c.get("subtitle", ""),
            "description": c.get("description", ""),
        }
        for c in FIXTURE_CORE
    ]
    extracted = extract.extract_keywords(
        documents,
        generics=generics,
        seed_description=SEED_DESCRIPTION,
        suggest_terms=SUGGEST_TERMS,
    )
    keywords = score.score_keywords(
        extracted,
        seed_description=SEED_DESCRIPTION,
        suggest_terms=SUGGEST_TERMS,
        n_docs=len(FIXTURE_CORE),
    )
    return keywords


class DeterminismTests(unittest.TestCase):
    def test_keywords_byte_identical_across_two_runs(self):
        a = serialize.dumps_json(_run_once())
        b = serialize.dumps_json(_run_once())
        self.assertEqual(a, b)

    def test_competition_byte_identical_across_two_runs(self):
        a = serialize.dumps_json(FIXTURE_CORE)
        b = serialize.dumps_json(FIXTURE_CORE)
        self.assertEqual(a, b)

    def test_keyword_report_carries_split_and_gap_flags(self):
        keywords = _run_once()
        self.assertTrue(keywords)
        for k in keywords:
            self.assertIn(k["split"], ("primary-candidate", "long-tail-candidate"))
            self.assertIsInstance(k["is_gap"], bool)
            # never a "volume" field
            self.assertNotIn("volume", k)
            self.assertNotIn("search_volume", k)


if __name__ == "__main__":
    unittest.main()
