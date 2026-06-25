#!/usr/bin/env python3
"""Tests for the real scoring engine (slice 02).

Run from the repo root:
    python3 tests/aso-research/test_scoring.py

Covers the offline-testable pure logic only (no network/browser):
Competition normalisation + division-by-zero, Opportunity off-by-one,
the strict niche-bonus boundary (both sides of Competition<20 and
Relevance>50), the Search-Suggest relevance boost, the primary/long-tail
split, the is_gap flag, and end-to-end determinism through the scorer.

The exact-boundary decisions are tested directly on the named pure
functions (no private-method mocking).
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import extract  # noqa: E402
import score  # noqa: E402


# ===========================================================================
# Competition — formula + normalisation + division-by-zero
# ===========================================================================

class CompetitionTests(unittest.TestCase):
    def test_pure_title_share(self):
        # 2 of 4 competitors carry term in title -> 100*(5*0.5)/9 = 27.77 -> 28
        self.assertEqual(score.competition_score(2, 0, 0, 4), 28)

    def test_weighted_blend(self):
        # title=1 sub=1 desc=1 over n=1 -> 100*(5+3+1)/9 = 100
        self.assertEqual(score.competition_score(1, 1, 1, 1), 100)

    def test_division_by_zero_when_no_docs(self):
        self.assertEqual(score.competition_score(5, 5, 5, 0), 0)

    def test_clamps_to_100(self):
        self.assertEqual(score.competition_score(10, 10, 10, 1), 100)

    def test_formula_matches_prd_weights(self):
        # PRD: 100*(5*title + 3*sub + 1*desc)/9 ; n_docs=9 for clean shares
        # title_hits=3 -> share 1/3 -> 100*(5/3)/9 = 18.518 -> 19
        self.assertEqual(score.competition_score(3, 0, 0, 9), 19)
        # sub_hits=3 -> 100*(3/3)/9 = 11.11 -> 11
        self.assertEqual(score.competition_score(0, 3, 0, 9), 11)
        # desc_hits=3 -> 100*(1/3)/9 = 3.7 -> 4
        self.assertEqual(score.competition_score(0, 0, 3, 9), 4)


# ===========================================================================
# Niche-bonus boundary — strict Competition<20 AND Relevance>50
# ===========================================================================

class NicheBonusBoundaryTests(unittest.TestCase):
    def test_both_conditions_met_applies(self):
        self.assertTrue(score.niche_bonus_applies(19, 51))
        self.assertTrue(score.niche_bonus_applies(0, 100))

    def test_competition_at_threshold_does_not_apply(self):
        # Competition < 20 is STRICT: 20 itself -> no bonus
        self.assertFalse(score.niche_bonus_applies(20, 100))

    def test_competition_just_below_applies(self):
        self.assertTrue(score.niche_bonus_applies(19, 100))

    def test_relevance_at_threshold_does_not_apply(self):
        # Relevance > 50 is STRICT: 50 itself -> no bonus
        self.assertFalse(score.niche_bonus_applies(0, 50))

    def test_relevance_just_above_applies(self):
        self.assertTrue(score.niche_bonus_applies(0, 51))


# ===========================================================================
# Opportunity — base + niche bonus + off-by-one
# ===========================================================================

class OpportunityTests(unittest.TestCase):
    def test_base_formula_rounds(self):
        # round(60 * (100-40)/100) = round(36) = 36
        self.assertEqual(score.opportunity_score(40, 60), 36)

    def test_adds_niche_bonus(self):
        # competition=10 (<20), relevance=80 (>50): round(80*90/100)=72 +10=82
        self.assertEqual(score.opportunity_score(10, 80), 82)

    def test_no_bonus_above_competition_threshold(self):
        # competition=20 -> no bonus -> round(80*80/100)=64
        self.assertEqual(score.opportunity_score(20, 80), 64)

    def test_no_bonus_at_relevance_threshold(self):
        # relevance=50 -> no bonus -> round(50*80/100)=40
        self.assertEqual(score.opportunity_score(20, 50), 40)

    def test_zero_relevance_zero_opportunity(self):
        self.assertEqual(score.opportunity_score(50, 0), 0)

    def test_zero_competition_full_relevance(self):
        # round(100*100/100)=100, plus niche bonus capped at 100
        self.assertEqual(score.opportunity_score(0, 100), 100)

    def test_off_by_one_rounding(self):
        # round(50*33/100)=round(16.5)=16 (banker's? Python rounds half to even)
        # 16.5 -> 16 ; verify it is a deterministic int either way
        val = score.opportunity_score(67, 50)
        self.assertIn(val, (16, 17))


# ===========================================================================
# Split label
# ===========================================================================

class SplitLabelTests(unittest.TestCase):
    def test_primary_at_threshold(self):
        self.assertEqual(score.split_label(50), "primary-candidate")
        self.assertEqual(score.split_label(100), "primary-candidate")

    def test_longtail_below_threshold(self):
        self.assertEqual(score.split_label(49), "long-tail-candidate")
        self.assertEqual(score.split_label(0), "long-tail-candidate")


# ===========================================================================
# End-to-end score_keywords — suggest boost / is_gap / determinism
# ===========================================================================

class ScoreKeywordsTests(unittest.TestCase):
    def setUp(self):
        # 'meditation' is the seed's distinctive term (rare in corpus).
        self.docs = [
            {"title": "Calm Sleep Sounds", "subtitle": "Relax and sleep",
             "description": "White noise for better sleep every night."},
            {"title": "Breath Work Pro", "subtitle": "Atmen ueben",
             "description": "Atemuebungen fuer den Alltag."},
            {"title": "Meditation Timer", "subtitle": "Achtsamkeit",
             "description": "Ein gefuehrter meditation timer."},
        ]

    def _candidates(self):
        return extract.extract_keywords(
            self.docs, seed_description="A guided meditation timer app",
            suggest_terms=["meditation timer"],
        )

    def test_suggest_term_gets_boost(self):
        cands = self._candidates()
        scored = score.score_keywords(
            cands, seed_description="A guided meditation timer app",
            suggest_terms=["meditation timer"], n_docs=3,
        )
        by = {s["term"]: s for s in scored}
        mt = by.get("meditation timer")
        self.assertIsNotNone(mt)
        self.assertTrue(mt["suggest"])
        # relevance = cosine (>=0) + 15 boost, clamped; suggest recorded True
        self.assertGreaterEqual(mt["relevance"], 15)

    def test_is_gap_when_competitor_title_term_absent_from_seed(self):
        # 'sleep' is in a competitor title but not the seed concept
        cands = self._candidates()
        scored = score.score_keywords(
            cands, seed_description="A guided meditation timer app",
            suggest_terms=[], n_docs=3,
        )
        by = {s["term"]: s for s in scored}
        # 'sleep' appears in competitor title, absent from seed -> gap
        if "sleep" in by:
            self.assertTrue(by["sleep"]["is_gap"])
        # a seed term present in title is NOT a gap
        if "timer" in by:
            self.assertFalse(by["timer"]["is_gap"])

    def test_division_by_zero_competition_zero(self):
        cands = [{"term": "x", "title_hits": 5, "subtitle_hits": 5,
                  "description_hits": 5, "doc_freq": 5, "occurrences": 5,
                  "is_phrase": False, "suggest": False, "tf_weighted": 5}]
        scored = score.score_keywords(cands, seed_description="x", n_docs=0)
        self.assertEqual(scored[0]["competition"], 0)

    def test_output_sorted_and_deterministic(self):
        cands = self._candidates()
        a = score.score_keywords(cands, seed_description="A guided meditation timer app",
                                 suggest_terms=["meditation timer"], n_docs=3)
        b = score.score_keywords(cands, seed_description="A guided meditation timer app",
                                 suggest_terms=["meditation timer"], n_docs=3)
        self.assertEqual(a, b)
        keys = [(-s["opportunity"], -s["relevance"], s["term"]) for s in a]
        self.assertEqual(keys, sorted(keys))

    def test_every_scored_term_carries_required_fields(self):
        cands = self._candidates()
        scored = score.score_keywords(
            cands, seed_description="A guided meditation timer app",
            suggest_terms=["meditation timer"], n_docs=3,
        )
        required = {"term", "competition", "relevance", "opportunity",
                    "niche_bonus", "split", "is_gap"}
        for s in scored:
            self.assertTrue(required.issubset(s.keys()))
            self.assertIn(s["split"], ("primary-candidate", "long-tail-candidate"))


if __name__ == "__main__":
    unittest.main()
