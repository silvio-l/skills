#!/usr/bin/env python3
"""Tests for the W3C Nu validator adapter normaliser."""

import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURE = (REPO_ROOT / "tests" / "seo-audit" / "fixtures"
           / "probes" / "w3c" / "sample.json")

sys.path.insert(0, str(SCRIPTS_DIR))

from probes import w3c_adapter as W3  # noqa: E402


class W3CNormaliser(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_normaliser_emits_expected_findings(self):
        findings = W3.normalise(self.raw, url="https://whispaste.de/")
        self.assertEqual(len(findings), 4)
        for f in findings:
            self.assertEqual(f["category"], "html")
            self.assertNotIn("score", f)

    def test_error_is_high_warning_is_med_info_is_low(self):
        findings = W3.normalise(self.raw, url="https://whispaste.de/")
        sev_by_line = {f["line_number"]: f["severity"] for f in findings}
        self.assertEqual(sev_by_line[12], "high")  # error
        self.assertEqual(sev_by_line[47], "high")  # error
        self.assertEqual(sev_by_line[3], "med")   # info+subType=warning
        self.assertEqual(sev_by_line[1], "low")   # plain info

    def test_line_number_from_last_line(self):
        findings = W3.normalise(self.raw, url="https://whispaste.de/")
        lines = sorted(f["line_number"] for f in findings)
        self.assertEqual(lines, [1, 3, 12, 47])

    def test_match_is_concise_message_prefix(self):
        findings = W3.normalise(self.raw, url="https://whispaste.de/")
        dup = next(f for f in findings if f["line_number"] == 47)
        self.assertTrue(dup["match"].startswith("Duplicate ID"))

    def test_handles_empty_messages_list(self):
        self.assertEqual(W3.normalise({"messages": []}, url="x"), [])
        self.assertEqual(W3.normalise({}, url="x"), [])
        self.assertEqual(W3.normalise(None, url="x"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
