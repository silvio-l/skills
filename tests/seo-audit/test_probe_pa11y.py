#!/usr/bin/env python3
"""Tests for the pa11y adapter normaliser."""

import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURE = (REPO_ROOT / "tests" / "seo-audit" / "fixtures"
           / "probes" / "pa11y" / "sample.json")

sys.path.insert(0, str(SCRIPTS_DIR))

from probes import pa11y_adapter as PA  # noqa: E402


class Pa11yNormaliser(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_normaliser_emits_expected_findings(self):
        findings = PA.normalise(self.raw, url="https://whispaste.de/")
        self.assertEqual(len(findings), 4)
        for f in findings:
            self.assertEqual(f["category"], "a11y")
            self.assertEqual(f["file_path"], "https://whispaste.de/")
            self.assertIn(f["severity"], {"high", "med", "low"})
            self.assertNotIn("score", f)

    def test_severity_uses_axe_impact(self):
        findings = PA.normalise(self.raw, url="https://whispaste.de/")
        by_code = {f["match"]: f for f in findings}
        self.assertEqual(by_code["image-alt"]["severity"], "high")     # critical
        self.assertEqual(by_code["color-contrast"]["severity"], "high")  # serious
        self.assertEqual(by_code["landmark-one-main"]["severity"], "med")  # moderate
        self.assertEqual(by_code["region"]["severity"], "low")  # minor

    def test_match_uses_axe_rule_id(self):
        findings = PA.normalise(self.raw, url="https://whispaste.de/")
        matches = {f["match"] for f in findings}
        self.assertEqual(
            matches,
            {"color-contrast", "image-alt", "landmark-one-main", "region"},
        )

    def test_rationale_includes_message_and_selector(self):
        findings = PA.normalise(self.raw, url="https://whispaste.de/")
        contrast = next(f for f in findings if f["match"] == "color-contrast")
        self.assertIn("color contrast", contrast["rationale"].lower())
        self.assertIn("header", contrast["rationale"])

    def test_empty_input_yields_no_findings(self):
        self.assertEqual(PA.normalise([], url="x"), [])
        self.assertEqual(PA.normalise(None, url="x"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
