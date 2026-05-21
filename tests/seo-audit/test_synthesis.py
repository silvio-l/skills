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


if __name__ == "__main__":
    unittest.main(verbosity=2)
