#!/usr/bin/env python3
"""Tests for the Token-Budget Gate (slice 03, stage 50).

Run from the repo root:
    python3 tests/aso-research/test_llm_gate.py

Covers the offline-testable deterministic logic: token estimation, the
measure + auto-trim boundary (oversized representation -> trimmed below
the limit; small representation -> unchanged), and the trim order
(profiles before score table).
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import llm_gate  # noqa: E402


def _profile(i: int) -> dict:
    # A realistically-sized condensed profile (~ a few hundred chars).
    return {
        "app_id": str(i),
        "title": f"Competitor Number {i}",
        "positioning": (
            f"A habit-tracking application targeting users who want to build "
            f"daily routines with streaks, reminders, and gamified rewards "
            f"for consistency over time. Profile index {i}."
        ),
        "top_keywords": ["habit", "tracker", "routine", "streak", "daily"],
        "tag": "habit-tracker",
    }


def _representation(n_profiles: int) -> dict:
    return {
        "own_app_id": None,
        "meta": {"app_name": "Habit Hero", "category": "health_fitness", "seed_keywords": ["habit"]},
        "condensed_profiles": [_profile(i) for i in range(n_profiles)],
        "score_table": [
            {"term": "habit", "competition": 30, "relevance": 80, "opportunity": 56, "split": "primary-candidate", "is_gap": False, "suggest": True},
            {"term": "tracker", "competition": 40, "relevance": 70, "opportunity": 42, "split": "primary-candidate", "is_gap": False, "suggest": False},
        ],
        "reddit_summaries": [
            {"subreddit": "getdisciplined", "title": "best habit tracker app?", "score": 42},
        ],
    }


class EstimateTokensTests(unittest.TestCase):
    def test_chars_div_4_with_min_one(self):
        self.assertEqual(llm_gate.estimate_tokens(""), 0)
        self.assertEqual(llm_gate.estimate_tokens("abcd"), 1)
        self.assertEqual(llm_gate.estimate_tokens("abcdefgh"), 2)

    def test_is_deterministic(self):
        self.assertEqual(
            llm_gate.estimate_tokens("x" * 1000),
            llm_gate.estimate_tokens("x" * 1000),
        )


class MeasureRepresentationTests(unittest.TestCase):
    def test_more_profiles_means_more_tokens(self):
        small = _representation(3)
        big = _representation(30)
        self.assertLess(
            llm_gate.measure_representation(small),
            llm_gate.measure_representation(big),
        )

    def test_is_stable_for_identical_input(self):
        rep = _representation(5)
        self.assertEqual(
            llm_gate.measure_representation(rep),
            llm_gate.measure_representation(rep),
        )


class ApplyTokenGateTests(unittest.TestCase):
    def test_small_representation_not_trimmed(self):
        rep = _representation(3)
        limit = llm_gate.measure_representation(rep) + 10_000  # comfortably above
        trimmed, gate_report = llm_gate.apply_token_gate(rep, limit)
        self.assertFalse(gate_report["trimmed"])
        self.assertEqual(gate_report["profiles_kept"], 3)
        self.assertEqual(gate_report["profiles_before"], 3)
        # payload unchanged
        self.assertEqual(
            len(trimmed["condensed_profiles"]), len(rep["condensed_profiles"])
        )

    def test_oversized_representation_trimmed_below_limit(self):
        rep = _representation(40)
        # A deliberately tiny limit forces heavy trimming of profiles.
        limit = 200
        trimmed, gate_report = llm_gate.apply_token_gate(rep, limit)
        self.assertTrue(gate_report["trimmed"])
        self.assertLess(gate_report["measured_after"], gate_report["measured_before"])
        self.assertLessEqual(gate_report["measured_after"], limit)
        self.assertLess(gate_report["profiles_kept"], gate_report["profiles_before"])

    def test_trim_drops_profiles_tail_keeps_score_table_whole(self):
        rep = _representation(20)
        before = llm_gate.measure_representation(rep)
        limit = before - 1  # just over -> should drop exactly enough profiles
        trimmed, gate_report = llm_gate.apply_token_gate(rep, limit)
        self.assertTrue(gate_report["trimmed"])
        self.assertLessEqual(gate_report["measured_after"], limit)
        # score table + reddit kept whole (profiles are the primary lever)
        self.assertEqual(len(trimmed["score_table"]), len(rep["score_table"]))
        self.assertEqual(len(trimmed["reddit_summaries"]), len(rep["reddit_summaries"]))

    def test_score_table_trimmed_only_when_profiles_exhausted(self):
        # One profile + a large score table, tiny limit: profiles can't trim
        # below 1, so the score table must give way.
        rep = _representation(1)
        rep["score_table"] = [
            {"term": f"kw{i}", "competition": 10, "relevance": 50, "opportunity": 45, "split": "primary-candidate", "is_gap": False, "suggest": False}
            for i in range(50)
        ]
        limit = 100
        trimmed, gate_report = llm_gate.apply_token_gate(rep, limit)
        self.assertTrue(gate_report["trimmed"])
        self.assertLessEqual(gate_report["measured_after"], limit)
        self.assertLess(len(trimmed["score_table"]), 50)

    def test_default_limit_used_when_nonpositive(self):
        rep = _representation(3)
        trimmed, gate_report = llm_gate.apply_token_gate(rep, 0)
        self.assertFalse(gate_report["trimmed"])
        self.assertEqual(gate_report["limit"], llm_gate.DEFAULT_GATE_TOKEN_LIMIT)


if __name__ == "__main__":
    unittest.main()
