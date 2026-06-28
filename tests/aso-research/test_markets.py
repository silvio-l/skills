#!/usr/bin/env python3
"""Tests for the cross-market keyword comparison (D4)."""

import os
import sys
import unittest

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "skills", "aso-research", "scripts"))

import markets  # noqa: E402


def _m(country, *terms):
    return {"country": country, "keywords": [{"term": t, "opportunity": o, "platform": "apple"} for t, o in terms]}


class CompareMarketsTests(unittest.TestCase):
    def test_per_country_opportunity_and_max(self):
        comp = markets.compare_markets([
            _m("de", ("transkription", 60), ("diktat", 40)),
            _m("us", ("transcription", 58), ("diktat", 5)),
        ])
        self.assertEqual(comp["countries"], ["de", "us"])
        row = next(r for r in comp["rows"] if r["term"] == "transkription")
        self.assertEqual(row["by_country"], {"de": 60, "us": 0})
        self.assertEqual(row["max_opp"], 60)

    def test_market_gap_flagged(self):
        comp = markets.compare_markets([
            _m("de", ("transkription", 60)),
            _m("us", ("transkription", 4)),
        ])
        row = comp["rows"][0]
        self.assertTrue(row["gap"])
        self.assertIn("de", row["gap_note"])
        self.assertIn("transkription", comp["market_specific"]["de"])

    def test_no_gap_when_balanced(self):
        comp = markets.compare_markets([
            _m("de", ("voice", 50)),
            _m("us", ("voice", 48)),
        ])
        self.assertFalse(comp["rows"][0]["gap"])

    def test_zero_only_terms_excluded(self):
        comp = markets.compare_markets([_m("de", ("x", 0)), _m("us", ("x", 0))])
        self.assertEqual(comp["rows"], [])

    def test_rows_sorted_by_max_opp(self):
        comp = markets.compare_markets([
            _m("de", ("low", 10), ("high", 90)),
            _m("us", ("low", 12), ("high", 80)),
        ])
        self.assertEqual([r["term"] for r in comp["rows"]], ["high", "low"])

    def test_deterministic(self):
        a = markets.compare_markets([_m("de", ("a", 30), ("b", 40)), _m("us", ("a", 20))])
        b = markets.compare_markets([_m("de", ("b", 40), ("a", 30)), _m("us", ("a", 20))])
        self.assertEqual(a, b)

    def test_render_html_self_contained(self):
        comp = markets.compare_markets([_m("de", ("t", 50)), _m("us", ("t", 10))])
        html = markets.render_html(comp, app_name="App", generated="2026-06-28 12:00:00")
        self.assertIn("<!DOCTYPE html>", html)
        self.assertNotIn("src=\"http", html)
        self.assertIn("Markt-Vergleich", html)


if __name__ == "__main__":
    unittest.main()
