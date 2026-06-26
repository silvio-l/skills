#!/usr/bin/env python3
"""Tests for the cross-run diff (slice 06 ``--compare-last``).

Run from the repo root:
    python3 tests/aso-research/test_diff.py

Covers the offline-testable pure logic: prior-run discovery (same-app,
chronological, ignoring non-run dirs / other apps), competitor in/out,
keyword rise/fall/new/gone, listing-recommendation changes, the
"no prior run to diff" notice, and determinism. Operates on fixture run
directories with machine-readable artefacts — no network, no LLM.
"""

import json
import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import diff  # noqa: E402


# ===========================================================================
# find_prior_run
# ===========================================================================

class FindPriorRunTests(unittest.TestCase):
    def test_most_recent_prior_same_app(self):
        with tempfile.TemporaryDirectory() as root:
            for rid in (
                "20260601-120000-habit-hero",
                "20260610-120000-habit-hero",
                "20260620-120000-habit-hero",
            ):
                os.makedirs(os.path.join(root, rid))
            prior = diff.find_prior_run(root, "20260620-120000-habit-hero")
            self.assertEqual(prior, "20260610-120000-habit-hero")

    def test_excludes_other_apps(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "20260610-120000-other-app"))
            os.makedirs(os.path.join(root, "20260615-120000-habit-hero"))
            prior = diff.find_prior_run(root, "20260620-120000-habit-hero")
            self.assertEqual(prior, "20260615-120000-habit-hero")

    def test_no_prior_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "20260620-120000-habit-hero"))
            self.assertIsNone(diff.find_prior_run(root, "20260620-120000-habit-hero"))

    def test_no_prior_of_same_app_returns_none(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "20260610-120000-other-app"))
            os.makedirs(os.path.join(root, "20260620-120000-habit-hero"))
            self.assertIsNone(diff.find_prior_run(root, "20260620-120000-habit-hero"))

    def test_ignores_non_run_directories(self):
        with tempfile.TemporaryDirectory() as root:
            os.makedirs(os.path.join(root, "some-random-dir"))
            os.makedirs(os.path.join(root, "20260610-120000-habit-hero"))
            prior = diff.find_prior_run(root, "20260620-120000-habit-hero")
            self.assertEqual(prior, "20260610-120000-habit-hero")

    def test_missing_output_root_returns_none(self):
        self.assertIsNone(diff.find_prior_run("/does/not/exist", "20260620-120000-x"))

    def test_is_run_id_shape(self):
        self.assertTrue(diff.is_run_id("20260601-120000-habit-hero"))
        self.assertFalse(diff.is_run_id("some-random-dir"))
        self.assertFalse(diff.is_run_id("20260601-120000"))  # no slug


# ===========================================================================
# compute_diff
# ===========================================================================

def _make_run(root, rid, *, competitors, keywords, listing=None, play_listing=None):
    d = os.path.join(root, rid)
    os.makedirs(d)
    with open(os.path.join(d, "competition.json"), "w", encoding="utf-8") as fh:
        json.dump(competitors, fh)
    with open(os.path.join(d, "keywords.json"), "w", encoding="utf-8") as fh:
        json.dump(keywords, fh)
    if listing or play_listing:
        os.makedirs(os.path.join(d, "llm"), exist_ok=True)
        if listing:
            with open(os.path.join(d, "llm/s2-listing.json"), "w", encoding="utf-8") as fh:
                json.dump(listing, fh)
        if play_listing:
            with open(os.path.join(d, "llm/s2-listing-play.json"), "w", encoding="utf-8") as fh:
                json.dump(play_listing, fh)
    return d


class ComputeDiffTests(unittest.TestCase):
    def test_competitor_entered_and_left(self):
        with tempfile.TemporaryDirectory() as root:
            pri = _make_run(
                root, "20260601-120000-habit-hero",
                competitors=[
                    {"id": "1", "platform": "apple"},
                    {"id": "2", "platform": "apple"},
                ],
                keywords=[],
            )
            cur = _make_run(
                root, "20260610-120000-habit-hero",
                competitors=[
                    {"id": "2", "platform": "apple"},
                    {"id": "3", "platform": "play"},
                ],
                keywords=[],
            )
            d = diff.compute_diff(cur, pri)
            entered = {(c["id"], c["platform"]) for c in d["competitors_entered"]}
            left = {(c["id"], c["platform"]) for c in d["competitors_left"]}
            self.assertEqual(entered, {("3", "play")})
            self.assertEqual(left, {("1", "apple")})

    def test_keyword_rise_fall_new_gone(self):
        with tempfile.TemporaryDirectory() as root:
            pri = _make_run(
                root, "20260601-120000-habit-hero",
                competitors=[],
                keywords=[
                    {"term": "habit", "platform": "apple", "opportunity": 50},
                    {"term": "tracker", "platform": "apple", "opportunity": 40},
                    {"term": "old", "platform": "apple", "opportunity": 30},
                ],
            )
            cur = _make_run(
                root, "20260610-120000-habit-hero",
                competitors=[],
                keywords=[
                    {"term": "habit", "platform": "apple", "opportunity": 70},
                    {"term": "tracker", "platform": "apple", "opportunity": 20},
                    {"term": "fresh", "platform": "apple", "opportunity": 60},
                ],
            )
            d = diff.compute_diff(cur, pri)
            risen = {k["term"]: k["delta"] for k in d["keywords_risen"]}
            fallen = {k["term"]: k["delta"] for k in d["keywords_fallen"]}
            new = {k["term"] for k in d["keywords_new"]}
            gone = {k["term"] for k in d["keywords_gone"]}
            self.assertEqual(risen, {"habit": 20})
            self.assertEqual(fallen, {"tracker": -20})
            self.assertEqual(new, {"fresh"})
            self.assertEqual(gone, {"old"})

    def test_keyword_risen_ordered_by_magnitude(self):
        with tempfile.TemporaryDirectory() as root:
            pri = _make_run(
                root, "20260601-120000-habit-hero", competitors=[],
                keywords=[
                    {"term": "a", "platform": "apple", "opportunity": 10},
                    {"term": "b", "platform": "apple", "opportunity": 10},
                ],
            )
            cur = _make_run(
                root, "20260610-120000-habit-hero", competitors=[],
                keywords=[
                    {"term": "a", "platform": "apple", "opportunity": 35},  # +25
                    {"term": "b", "platform": "apple", "opportunity": 50},  # +40
                ],
            )
            d = diff.compute_diff(cur, pri)
            order = [k["term"] for k in d["keywords_risen"]]
            self.assertEqual(order, ["b", "a"])  # biggest delta first

    def test_listing_change_detected(self):
        with tempfile.TemporaryDirectory() as root:
            pri = _make_run(
                root, "20260601-120000-habit-hero", competitors=[], keywords=[],
                listing={"store": "apple", "slots": [
                    {"slot": "title", "recommended": {"text": "Old Title", "char_count": 9}},
                ]},
            )
            cur = _make_run(
                root, "20260610-120000-habit-hero", competitors=[], keywords=[],
                listing={"store": "apple", "slots": [
                    {"slot": "title", "recommended": {"text": "New Title", "char_count": 9}},
                ]},
            )
            d = diff.compute_diff(cur, pri)
            self.assertEqual(len(d["listing_changes"]), 1)
            change = d["listing_changes"][0]
            self.assertEqual(change["store"], "apple")
            self.assertEqual(change["slot"], "title")
            self.assertEqual(change["before"], "Old Title")
            self.assertEqual(change["after"], "New Title")

    def test_listing_unchanged_yields_no_change(self):
        with tempfile.TemporaryDirectory() as root:
            listing = {"store": "apple", "slots": [
                {"slot": "title", "recommended": {"text": "Same", "char_count": 4}},
            ]}
            pri = _make_run(root, "20260601-120000-habit-hero",
                            competitors=[], keywords=[], listing=listing)
            cur = _make_run(root, "20260610-120000-habit-hero",
                            competitors=[], keywords=[], listing=listing)
            d = diff.compute_diff(cur, pri)
            self.assertEqual(d["listing_changes"], [])

    def test_missing_listing_files_yield_empty_changes(self):
        with tempfile.TemporaryDirectory() as root:
            pri = _make_run(root, "20260601-120000-habit-hero",
                            competitors=[], keywords=[])
            cur = _make_run(root, "20260610-120000-habit-hero",
                            competitors=[], keywords=[])
            d = diff.compute_diff(cur, pri)
            self.assertEqual(d["listing_changes"], [])

    def test_play_listing_change_detected(self):
        with tempfile.TemporaryDirectory() as root:
            pri = _make_run(
                root, "20260601-120000-habit-hero", competitors=[], keywords=[],
                play_listing={"store": "play", "slots": [
                    {"slot": "short", "recommended": {"text": "Alt A", "char_count": 5}},
                ]},
            )
            cur = _make_run(
                root, "20260610-120000-habit-hero", competitors=[], keywords=[],
                play_listing={"store": "play", "slots": [
                    {"slot": "short", "recommended": {"text": "Alt B", "char_count": 5}},
                ]},
            )
            d = diff.compute_diff(cur, pri)
            self.assertTrue(any(c["store"] == "play" for c in d["listing_changes"]))


# ===========================================================================
# compare_last (full entry point)
# ===========================================================================

class CompareLastTests(unittest.TestCase):
    def test_no_prior_run_reports_notice_not_error(self):
        with tempfile.TemporaryDirectory() as root:
            cur = os.path.join(root, "20260620-120000-habit-hero")
            os.makedirs(cur)
            md = diff.compare_last(cur, root, "20260620-120000-habit-hero")
            self.assertIn("no prior run", md.lower())

    def test_with_prior_produces_deltas_section(self):
        with tempfile.TemporaryDirectory() as root:
            pri = os.path.join(root, "20260601-120000-habit-hero")
            os.makedirs(pri)
            with open(os.path.join(pri, "competition.json"), "w", encoding="utf-8") as fh:
                json.dump([{"id": "1", "platform": "apple"}], fh)
            with open(os.path.join(pri, "keywords.json"), "w", encoding="utf-8") as fh:
                json.dump([], fh)
            cur = os.path.join(root, "20260610-120000-habit-hero")
            os.makedirs(cur)
            with open(os.path.join(cur, "competition.json"), "w", encoding="utf-8") as fh:
                json.dump([{"id": "1", "platform": "apple"},
                           {"id": "2", "platform": "apple"}], fh)
            with open(os.path.join(cur, "keywords.json"), "w", encoding="utf-8") as fh:
                json.dump([], fh)
            md = diff.compare_last(cur, root, "20260610-120000-habit-hero")
            self.assertIn("Diff vs last run", md)
            self.assertIn("20260601-120000-habit-hero", md)
            self.assertIn("entered", md.lower())

    def test_diff_is_deterministic(self):
        # US18: identical inputs always yield an identical diff.
        with tempfile.TemporaryDirectory() as root:
            pri = os.path.join(root, "20260601-120000-habit-hero")
            os.makedirs(pri)
            with open(os.path.join(pri, "competition.json"), "w", encoding="utf-8") as fh:
                json.dump([{"id": "1", "platform": "apple"}], fh)
            with open(os.path.join(pri, "keywords.json"), "w", encoding="utf-8") as fh:
                json.dump([{"term": "x", "platform": "apple", "opportunity": 10}], fh)
            cur = os.path.join(root, "20260610-120000-habit-hero")
            os.makedirs(cur)
            with open(os.path.join(cur, "competition.json"), "w", encoding="utf-8") as fh:
                json.dump([{"id": "2", "platform": "apple"}], fh)
            with open(os.path.join(cur, "keywords.json"), "w", encoding="utf-8") as fh:
                json.dump([{"term": "x", "platform": "apple", "opportunity": 30}], fh)
            a = diff.compare_last(cur, root, "20260610-120000-habit-hero")
            b = diff.compare_last(cur, root, "20260610-120000-habit-hero")
            self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
