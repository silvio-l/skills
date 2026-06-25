#!/usr/bin/env python3
"""Tests for the H2 Cross-Checker rubric + listing char-count validation
(slice 03).

Run from the repo root:
    python3 tests/aso-research/test_crosscheck.py

Covers: the contradiction rubric is non-trivial (DoD criterion 10) — it
rejects a recommendation carrying a low-opportunity/high-competition
keyword or an unscored term, and accepts a clean one (AC5); the Apple
slot char-count validator flags over-limit + inaccurate counts (AC4).
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import crosscheck  # noqa: E402


def _score_table():
    return [
        {"term": "habit", "competition": 30, "relevance": 80, "opportunity": 56, "split": "primary-candidate", "is_gap": False},
        {"term": "tracker", "competition": 40, "relevance": 70, "opportunity": 42, "split": "primary-candidate", "is_gap": False},
        # a low-opportunity, high-competition term (a "trap"):
        {"term": "game", "competition": 90, "relevance": 10, "opportunity": 1, "split": "long-tail-candidate", "is_gap": False},
    ]


def _slot(name, rec_text, alt1, alt2):
    return {
        "slot": name,
        "recommended": {"text": rec_text, "char_count": len(rec_text)},
        "alternatives": [{"text": alt1, "char_count": len(alt1)}, {"text": alt2, "char_count": len(alt2)}],
    }


def _listing(title="Habit Tracker", subtitle="Daily Routine Builder", kw="habit tracker"):
    return {
        "store": "apple",
        "slots": [
            _slot("title", title, "Habit Buddy", "Streak Habit"),
            _slot("subtitle", subtitle, "Build Habits Daily", "Routine & Streaks"),
            _slot("keyword_field", kw, "habit,tracker,routine", "streak,daily,habit"),
        ],
    }


class CrosscheckListingTests(unittest.TestCase):
    def test_clean_recommendation_accepted(self):
        out = crosscheck.crosscheck_listing(_listing(), _score_table())
        self.assertEqual(out["status"], "ok")
        self.assertEqual(out["findings"], [])

    def test_low_opportunity_keyword_rejected(self):
        # 'game' is in the score table but opportunity 1 < OPPORTUNITY_MIN.
        listing = _listing(title="Habit Game")
        out = crosscheck.crosscheck_listing(listing, _score_table())
        self.assertEqual(out["status"], "rejected")
        reasons = [f for r in out["findings"] for f in r["reasons"]]
        self.assertTrue(any("opportunity" in r for r in reasons))

    def test_high_competition_keyword_rejected(self):
        # 'game' has competition 90 > COMPETITION_MAX.
        listing = _listing(subtitle="Fun Game Time")
        out = crosscheck.crosscheck_listing(listing, _score_table())
        self.assertEqual(out["status"], "rejected")
        reasons = [f for r in out["findings"] for f in r["reasons"]]
        self.assertTrue(any("competition" in r for r in reasons))

    def test_unscored_invented_keyword_rejected(self):
        # 'quantum' in the Keyword Field is an explicit keyword with no
        # evidence (not in the score table) -> contradiction.
        listing = _listing(kw="quantum power")
        out = crosscheck.crosscheck_listing(listing, _score_table())
        self.assertEqual(out["status"], "rejected")
        reasons = [f for r in out["findings"] for f in r["reasons"]]
        self.assertTrue(any("unscored" in r for r in reasons))

    def test_findings_carry_slot_and_source(self):
        listing = _listing(title="Habit Game")
        out = crosscheck.crosscheck_listing(listing, _score_table())
        self.assertTrue(out["findings"])
        f = out["findings"][0]
        self.assertIn(f["slot"], ("title", "subtitle", "keyword_field"))
        self.assertIn(f["source"], ("recommended", "alternative"))

    def test_custom_thresholds(self):
        # With a very strict opp_min, even the clean 'habit' (opp 56) passes
        # but a stricter floor (60) would reject it.
        out_strict = crosscheck.crosscheck_listing(
            _listing(title="Habit Tracker"), _score_table(), opp_min=60
        )
        # 'habit' opp 56 < 60 -> rejected under the stricter floor
        self.assertEqual(out_strict["status"], "rejected")


class ValidateListingTests(unittest.TestCase):
    def test_fitting_accurate_listing_valid(self):
        out = crosscheck.validate_listing(_listing())
        self.assertTrue(out["valid"])
        for slot in out["slots"]:
            self.assertTrue(slot["recommended"]["fits"])
            self.assertTrue(slot["recommended"]["accurate"])
            self.assertEqual(len(slot["alternatives"]), 2)

    def test_over_limit_title_flagged(self):
        long_title = "x" * 35  # > 30 limit
        listing = _listing(title=long_title)
        out = crosscheck.validate_listing(listing)
        self.assertFalse(out["valid"])
        title_slot = next(s for s in out["slots"] if s["slot"] == "title")
        self.assertFalse(title_slot["recommended"]["fits"])

    def test_inaccurate_char_count_flagged(self):
        listing = _listing(title="Habit Tracker")
        listing["slots"][0]["recommended"]["char_count"] = 999  # wrong
        out = crosscheck.validate_listing(listing)
        self.assertFalse(out["valid"])
        title_slot = next(s for s in out["slots"] if s["slot"] == "title")
        self.assertFalse(title_slot["recommended"]["accurate"])

    def test_keyword_field_limit_is_100(self):
        self.assertEqual(crosscheck.APPLE_SLOTS["keyword_field"], 100)
        self.assertEqual(crosscheck.APPLE_SLOTS["title"], 30)
        self.assertEqual(crosscheck.APPLE_SLOTS["subtitle"], 30)


if __name__ == "__main__":
    unittest.main()
