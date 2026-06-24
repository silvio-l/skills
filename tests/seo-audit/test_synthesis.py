#!/usr/bin/env python3
"""Tests for seo-audit/scripts/synthesis.py.

Synthesis:
* Deduplicates identical findings.
* Groups by (file_path, category).
* Ranks by `severity * user_impact / fix_effort`, then by stable
  tiebreaker `(file_path, line_number, match)`.

Run from the repo root:
    python3 tests/seo-audit/test_synthesis.py
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import synthesis as S  # noqa: E402


def f(file_path="a.html", line=1, match="App", category="brand",
      severity="med", user_impact=2, fix_effort=1, **extra):
    return {
        "file_path": file_path,
        "line_number": line,
        "match": match,
        "category": category,
        "severity": severity,
        "user_impact": user_impact,
        "fix_effort": fix_effort,
        **extra,
    }


class RankAndDedup(unittest.TestCase):
    def test_score_formula(self):
        finding = f(severity="high", user_impact=3, fix_effort=1)
        # high=3, impact=3, effort=1 → 9.0
        self.assertEqual(S.score(finding), 9.0)

    def test_dedup_removes_identical_entries(self):
        findings = [f(), f(), f(line=2)]
        result = S.synthesize(findings)
        self.assertEqual(len(result["findings"]), 2)

    def test_deterministic_ranking_on_identical_input(self):
        findings = [
            f(file_path="b.html", line=10, severity="low",  user_impact=1, fix_effort=3),
            f(file_path="a.html", line=2,  severity="high", user_impact=3, fix_effort=1),
            f(file_path="a.html", line=1,  severity="med",  user_impact=2, fix_effort=2),
        ]
        out1 = S.synthesize(list(findings))
        out2 = S.synthesize(list(reversed(findings)))
        # Same set of inputs → same ranked output.
        keys1 = [(f["file_path"], f["line_number"]) for f in out1["findings"]]
        keys2 = [(f["file_path"], f["line_number"]) for f in out2["findings"]]
        self.assertEqual(keys1, keys2)

    def test_higher_score_ranks_first(self):
        findings = [
            f(file_path="a.html", severity="low",  user_impact=1, fix_effort=3),
            f(file_path="b.html", severity="high", user_impact=3, fix_effort=1),
        ]
        out = S.synthesize(findings)
        self.assertEqual(out["findings"][0]["file_path"], "b.html")

    def test_tiebreaker_is_file_line_match(self):
        # Same score → alphabetic file, then line, then match.
        findings = [
            f(file_path="b.html", line=5, match="Tool"),
            f(file_path="a.html", line=5, match="Tool"),
            f(file_path="a.html", line=2, match="Tool"),
            f(file_path="a.html", line=5, match="App"),
        ]
        out = S.synthesize(findings)
        keys = [(x["file_path"], x["line_number"], x["match"])
                for x in out["findings"]]
        self.assertEqual(keys, sorted(keys))

    def test_groups_summary_per_category(self):
        findings = [
            f(category="brand", file_path="a.html", line=1),
            f(category="brand", file_path="a.html", line=2, match="Tool"),
            f(category="seo-asset", file_path="robots.txt", line=1, match="missing"),
        ]
        out = S.synthesize(findings)
        self.assertIn("groups", out)
        cats = {g["category"]: g["count"] for g in out["groups"]}
        self.assertEqual(cats["brand"], 2)
        self.assertEqual(cats["seo-asset"], 1)

    def test_empty_input(self):
        out = S.synthesize([])
        self.assertEqual(out["findings"], [])
        self.assertEqual(out["groups"], [])

    def test_default_weights_when_missing(self):
        # Findings without severity/impact/effort still synthesize without error;
        # defaults are documented in synthesis.md.
        out = S.synthesize([{
            "file_path": "a.html", "line_number": 1, "match": "x",
            "category": "brand",
        }])
        self.assertEqual(len(out["findings"]), 1)
        self.assertIn("score", out["findings"][0])


class DimensionTrackAndScore(unittest.TestCase):
    """Tests for the new dimension/track fields and headline-score aggregation."""

    def _fd(self, dimension=None, track=None, **kw):
        """Build a finding, optionally with dimension/track set."""
        base = f(**kw)
        if dimension is not None:
            base["dimension"] = dimension
        if track is not None:
            base["track"] = track
        return base

    # ---- AC1: default dimension and track -----------------------------------

    def test_missing_dimension_defaults_to_brand(self):
        out = S.synthesize([f()])
        self.assertEqual(out["findings"][0].get("dimension"), S.DEFAULT_DIMENSION)

    def test_missing_track_defaults_to_technical(self):
        out = S.synthesize([f()])
        self.assertEqual(out["findings"][0].get("track"), S.DEFAULT_TRACK)

    def test_explicit_dimension_is_preserved(self):
        out = S.synthesize([self._fd(dimension="schema")])
        self.assertEqual(out["findings"][0]["dimension"], "schema")

    def test_explicit_track_strategic_is_preserved(self):
        out = S.synthesize([self._fd(track="strategic")])
        self.assertEqual(out["findings"][0]["track"], "strategic")

    # ---- AC2: headline score returned as versioned constant aggregate -------

    def test_headline_score_present_in_result(self):
        out = S.synthesize([f()])
        self.assertIn("headline_score", out)

    def test_dimensions_breakdown_present_in_result(self):
        out = S.synthesize([f()])
        self.assertIn("dimensions_breakdown", out)

    def test_no_findings_gives_perfect_headline_score(self):
        out = S.synthesize([])
        self.assertEqual(out["headline_score"], 100.0)

    def test_headline_score_between_0_and_100(self):
        # Many high-severity findings should depress the score, but not below 0.
        many = [
            f(severity="high", user_impact=3, fix_effort=1,
              line=i, file_path=f"f{i}.html")
            for i in range(50)
        ]
        out = S.synthesize(many)
        self.assertGreaterEqual(out["headline_score"], 0.0)
        self.assertLessEqual(out["headline_score"], 100.0)

    def test_findings_depress_their_dimension_score(self):
        out = S.synthesize([f(severity="high", user_impact=3, fix_effort=1)])
        brand_score = out["dimensions_breakdown"].get(S.DEFAULT_DIMENSION, 100.0)
        self.assertLess(brand_score, 100.0)

    def test_dimension_weights_are_module_constants(self):
        # DIMENSION_WEIGHTS_V1 must be a non-empty dict of floats summing to ~1.0.
        self.assertIsInstance(S.DIMENSION_WEIGHTS_V1, dict)
        self.assertGreater(len(S.DIMENSION_WEIGHTS_V1), 0)
        total = sum(S.DIMENSION_WEIGHTS_V1.values())
        self.assertAlmostEqual(total, 1.0, places=9)

    # ---- AC3: determinism over findings AND score ---------------------------

    def test_determinism_of_findings_and_score(self):
        findings = [
            f(file_path="b.html", line=10, severity="low",  user_impact=1, fix_effort=3),
            f(file_path="a.html", line=2,  severity="high", user_impact=3, fix_effort=1),
            self._fd(dimension="onpage", file_path="c.html", line=1,
                     severity="med", user_impact=2, fix_effort=2),
        ]
        out1 = S.synthesize(list(findings))
        out2 = S.synthesize(list(reversed(findings)))
        # Same ranked finding order.
        keys1 = [(x["file_path"], x["line_number"]) for x in out1["findings"]]
        keys2 = [(x["file_path"], x["line_number"]) for x in out2["findings"]]
        self.assertEqual(keys1, keys2)
        # Same headline score.
        self.assertEqual(out1["headline_score"], out2["headline_score"])
        # Same dimensions breakdown.
        self.assertEqual(out1["dimensions_breakdown"], out2["dimensions_breakdown"])

    def test_dedup_key_distinguishes_different_dimensions(self):
        # Same file/line/match/category but different dimension → two distinct findings.
        f1 = self._fd(dimension="onpage")
        f2 = self._fd(dimension="geo")
        out = S.synthesize([f1, f2])
        self.assertEqual(len(out["findings"]), 2)

    def test_dedup_key_same_dimension_collapses(self):
        # Same finding sent twice → deduplicated to one.
        finding = self._fd(dimension="onpage")
        out = S.synthesize([finding, finding])
        self.assertEqual(len(out["findings"]), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
