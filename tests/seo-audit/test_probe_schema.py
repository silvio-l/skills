#!/usr/bin/env python3
"""Tests for the schema.org validator adapter normaliser."""

import json
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURE = (REPO_ROOT / "tests" / "seo-audit" / "fixtures"
           / "probes" / "schema" / "sample.json")

sys.path.insert(0, str(SCRIPTS_DIR))

from probes import schema_adapter as SCH  # noqa: E402


class SchemaNormaliser(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_normaliser_emits_one_finding_per_error(self):
        findings = SCH.normalise(self.raw, url="https://whispaste.de/")
        # 2 errors on Article + 1 on Organization = 3 findings.
        self.assertEqual(len(findings), 3)
        for f in findings:
            self.assertEqual(f["category"], "schema")
            self.assertEqual(f["file_path"], "https://whispaste.de/")
            self.assertNotIn("score", f)

    def test_error_is_high_warning_is_med(self):
        findings = SCH.normalise(self.raw, url="https://whispaste.de/")
        severities = sorted(f["severity"] for f in findings)
        self.assertEqual(severities, ["high", "high", "med"])

    def test_match_includes_type_and_path(self):
        findings = SCH.normalise(self.raw, url="https://whispaste.de/")
        matches = {f["match"] for f in findings}
        self.assertIn("Article: Missing required property: author"[:60], matches)

    def test_no_errors_means_no_findings(self):
        empty = {"tripleGroups": [{"nodes": [{"typeName": "X"}], "errors": []}]}
        self.assertEqual(SCH.normalise(empty, url="x"), [])
        self.assertEqual(SCH.normalise({}, url="x"), [])
        self.assertEqual(SCH.normalise(None, url="x"), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
