#!/usr/bin/env python3
"""Tests for the Lighthouse adapter normaliser.

Runs the normaliser against a frozen Lighthouse-12 JSON fixture and
asserts the Finding shape. The shell-out (`npx lighthouse …`) is NOT
exercised here — see skills/seo-audit/probes.md §Live-Smoke.

Run from the repo root:
    python3 tests/seo-audit/test_probe_lighthouse.py
"""

import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURE = (REPO_ROOT / "tests" / "seo-audit" / "fixtures"
           / "probes" / "lighthouse" / "sample.json")

sys.path.insert(0, str(SCRIPTS_DIR))

from probes import lighthouse_adapter as LH  # noqa: E402


class LighthouseNormaliser(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_normaliser_emits_expected_findings(self):
        findings = LH.normalise(self.raw, url="https://whispaste.de/")
        # Every finding has the Finding shape required by synthesis.
        for f in findings:
            self.assertIn("category", f)
            self.assertIn("severity", f)
            self.assertIn("user_impact", f)
            self.assertIn("fix_effort", f)
            self.assertIn("file_path", f)
            self.assertIn("line_number", f)
            self.assertIn("match", f)
            self.assertIn("rationale", f)
            self.assertNotIn("score", f,
                             "adapters must not pre-compute score")

    def test_low_category_score_produces_finding(self):
        findings = LH.normalise(self.raw, url="https://whispaste.de/")
        cats = [f["match"] for f in findings if f["category"] == "performance"]
        # Performance score 0.62 is below the 0.9 "good" threshold → finding.
        self.assertIn("category:performance", cats)

    def test_failed_audit_produces_finding(self):
        findings = LH.normalise(self.raw, url="https://whispaste.de/")
        matches = [f["match"] for f in findings]
        self.assertIn("audit:meta-description", matches)
        # Audit with score 1.0 must NOT produce a finding.
        self.assertNotIn("audit:uses-responsive-images", matches)
        # notApplicable audits are skipped.
        self.assertNotIn("audit:color-contrast", matches)

    def test_finding_url_is_recorded_in_file_path(self):
        findings = LH.normalise(self.raw, url="https://whispaste.de/")
        for f in findings:
            self.assertEqual(f["file_path"], "https://whispaste.de/")

    def test_high_severity_for_zero_score_audit(self):
        findings = LH.normalise(self.raw, url="https://whispaste.de/")
        md = next(f for f in findings if f["match"] == "audit:meta-description")
        self.assertEqual(md["severity"], "high")

    def test_deterministic_order(self):
        a = LH.normalise(self.raw, url="https://whispaste.de/")
        b = LH.normalise(self.raw, url="https://whispaste.de/")
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
