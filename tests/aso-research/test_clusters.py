#!/usr/bin/env python3
"""Tests for the keyword clustering + target-set recommendation (D3)."""

import os
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "skills", "aso-research", "scripts"))

import clusters  # noqa: E402


def _kw(term, opp, rank=None, platform="apple"):
    return {
        "term": term, "opportunity": opp, "platform": platform,
        "rank_score": rank if rank is not None else float(opp),
    }


def _corpus():
    return [
        _kw("transkription", 60),
        _kw("transkription sprache", 50),
        _kw("transkriptor", 45),
        _kw("spracheingabe", 58),
        _kw("sprache zu text", 64),
        _kw("voice input", 40),
        _kw("voice typing", 38),
        _kw("game", 0),  # filtered (opp 0)
    ]


class ClusterTests(unittest.TestCase):
    def test_groups_by_shared_token(self):
        cl = clusters.cluster_keywords(_corpus(), min_cluster=2)
        self.assertTrue(cl)  # the corpus has shared-token themes
        for c in cl:
            # cluster invariant: every member shares the head token, >= min size,
            # and the label is one of the members.
            self.assertGreaterEqual(c["size"], 2)
            self.assertIn(c["label"], c["terms"])
            for term in c["terms"]:
                self.assertIn(c["head"], clusters._kw_tokens(term),
                              f"{term!r} lacks head {c['head']!r}")

    def test_zero_opportunity_excluded(self):
        cl = clusters.cluster_keywords(_corpus())
        flat = [t for c in cl for t in c["terms"]]
        self.assertNotIn("game", flat)

    def test_deterministic(self):
        a = clusters.cluster_keywords(_corpus())
        b = clusters.cluster_keywords(list(reversed(_corpus())))
        self.assertEqual(a, b)

    def test_empty(self):
        self.assertEqual(clusters.cluster_keywords([]), [])


class TargetSetTests(unittest.TestCase):
    def test_slots_respect_char_budgets(self):
        ts = clusters.recommend_target_set(_corpus())
        self.assertLessEqual(len(" ".join(ts["title"])), clusters.TITLE_MAX)
        self.assertLessEqual(len(" ".join(ts["subtitle"])), clusters.SUBTITLE_MAX)
        self.assertLessEqual(len(",".join(ts["keyword_field"])), clusters.KEYWORD_FIELD_MAX)

    def test_title_and_subtitle_disjoint(self):
        ts = clusters.recommend_target_set(_corpus())
        self.assertFalse(set(ts["title"]) & set(ts["subtitle"]))

    def test_keyword_field_excludes_visible_slots(self):
        ts = clusters.recommend_target_set(_corpus())
        visible = set(ts["title"]) | set(ts["subtitle"])
        self.assertFalse(visible & set(ts["keyword_field"]))

    def test_build_strategy_shape(self):
        s = clusters.build_strategy(_corpus())
        self.assertIn("clusters", s)
        self.assertIn("target_set", s)
        self.assertEqual(set(s["target_set"]), {"title", "subtitle", "keyword_field"})


if __name__ == "__main__":
    unittest.main()
