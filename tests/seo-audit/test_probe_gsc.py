#!/usr/bin/env python3
"""Tests for the GSC adapter normaliser and the injectable client.

The adapter calls `mcp__gsc__*` MCP tools at runtime. The worker cannot
do that, so we inject a fake client that returns a frozen composite
shape (see fixture). The test asserts the normaliser maps each section
of the composite shape into the expected findings.
"""

import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURE = (REPO_ROOT / "tests" / "seo-audit" / "fixtures"
           / "probes" / "gsc" / "sample.json")

sys.path.insert(0, str(SCRIPTS_DIR))

from probes import gsc_adapter as GSC  # noqa: E402


class GscNormaliser(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_normaliser_emits_expected_findings(self):
        findings = GSC.normalise(self.raw, url="https://whispaste.de/")
        cats = {f["category"] for f in findings}
        # Findings touch indexing, gsc/ctr, gsc/performance.
        self.assertIn("indexing", cats)
        self.assertIn("gsc", cats)
        for f in findings:
            self.assertNotIn("score", f)

    def test_indexing_issues_become_findings(self):
        findings = GSC.normalise(self.raw, url="https://whispaste.de/")
        urls = {f["file_path"] for f in findings if f["category"] == "indexing"}
        self.assertIn("https://whispaste.de/old", urls)
        self.assertIn("https://whispaste.de/404", urls)

    def test_low_ctr_pages_become_findings(self):
        findings = GSC.normalise(self.raw, url="https://whispaste.de/")
        ctr_matches = [
            f["match"] for f in findings
            if f["match"].startswith("ctr:")
        ]
        # CTR < 0.01 with impressions > 1000 → finding.
        self.assertIn("ctr:secure paste", ctr_matches)
        # 0.08 CTR / 200 impressions does NOT meet the threshold.
        self.assertNotIn("ctr:whispaste", ctr_matches)

    def test_overall_low_ctr_summary_finding(self):
        findings = GSC.normalise(self.raw, url="https://whispaste.de/")
        matches = {f["match"] for f in findings}
        # 0.014 average CTR is below 0.02 → summary finding.
        self.assertIn("gsc:avg-ctr-low", matches)


class GscInjectedClient(unittest.TestCase):
    def test_run_calls_injected_client_and_normalises(self):
        composite = {
            "performance": {"site": "x", "total_clicks": 1,
                             "total_impressions": 1000,
                             "avg_ctr": 0.001, "avg_position": 30.0},
            "indexing": {"issues": []},
            "low_ctr_pages": [],
        }
        calls = []

        def fake_client(site: str):
            calls.append(site)
            return composite

        findings = GSC.run("https://x.example/", gsc_client=fake_client)
        self.assertEqual(calls, ["https://x.example/"])
        self.assertTrue(findings, "expected at least the avg-ctr-low finding")

    def test_run_with_no_client_returns_empty(self):
        # Default client is the MCP wrapper which is unavailable in tests;
        # adapter must degrade gracefully when it returns None.
        result = GSC.run("https://x.example/", gsc_client=lambda site: None)
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
