#!/usr/bin/env python3
"""Tests for the Mozilla Observatory adapter normaliser."""

import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURE = (REPO_ROOT / "tests" / "seo-audit" / "fixtures"
           / "probes" / "observatory" / "sample.json")

sys.path.insert(0, str(SCRIPTS_DIR))

from probes import observatory_adapter as OBS  # noqa: E402


class ObservatoryNormaliser(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_normaliser_emits_one_finding_per_failed_test(self):
        findings = OBS.normalise(self.raw, url="https://whispaste.de/")
        matches = sorted(f["match"] for f in findings)
        # Three failed tests + one "grade C" summary finding = 4.
        self.assertIn("content-security-policy", matches)
        self.assertIn("x-frame-options", matches)
        self.assertIn("referrer-policy", matches)
        self.assertIn("observatory:grade", matches)
        self.assertNotIn("strict-transport-security", matches)
        self.assertNotIn("redirection", matches)

    def test_severity_scales_with_score_modifier(self):
        findings = OBS.normalise(self.raw, url="https://whispaste.de/")
        by_match = {f["match"]: f for f in findings}
        # |modifier| >= 20 → high, 5..19 → med, <5 → low.
        self.assertEqual(by_match["content-security-policy"]["severity"], "high")
        self.assertEqual(by_match["x-frame-options"]["severity"], "high")
        self.assertEqual(by_match["referrer-policy"]["severity"], "med")

    def test_category_is_security(self):
        findings = OBS.normalise(self.raw, url="https://whispaste.de/")
        for f in findings:
            self.assertEqual(f["category"], "security")
            self.assertNotIn("score", f)

    def test_grade_a_produces_no_grade_finding(self):
        a_grade = {"host": "x", "grade": "A+", "score": 100, "tests": {}}
        findings = OBS.normalise(a_grade, url="x")
        self.assertEqual(findings, [])

    def test_empty_input(self):
        self.assertEqual(OBS.normalise(None, url="x"), [])
        self.assertEqual(OBS.normalise({}, url="x"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
