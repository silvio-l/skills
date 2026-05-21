#!/usr/bin/env python3
"""Tests for the PageSpeed Insights adapter.

The adapter must:
* skip silently with no findings when PAGESPEED_API_KEY is unset,
* normalise the API response into Finding-shaped dicts when key is set.
"""

import contextlib
import io
import json
import os
import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURE = (REPO_ROOT / "tests" / "seo-audit" / "fixtures"
           / "probes" / "pagespeed" / "sample.json")

sys.path.insert(0, str(SCRIPTS_DIR))

from probes import pagespeed_adapter as PSI  # noqa: E402


class PagespeedNormaliser(unittest.TestCase):
    def setUp(self):
        self.raw = json.loads(FIXTURE.read_text(encoding="utf-8"))

    def test_normaliser_emits_expected_findings(self):
        findings = PSI.normalise(self.raw, url="https://whispaste.de/")
        matches = {f["match"] for f in findings}
        # Failing CrUX metric → CLS SLOW + LCP AVERAGE.
        self.assertIn("crux:CUMULATIVE_LAYOUT_SHIFT_SCORE", matches)
        # Lighthouse performance category < 0.9 → finding.
        self.assertIn("category:performance", matches)
        for f in findings:
            self.assertNotIn("score", f)
            self.assertEqual(f["file_path"], "https://whispaste.de/")

    def test_fast_crux_metric_skipped(self):
        findings = PSI.normalise(self.raw, url="https://whispaste.de/")
        matches = {f["match"] for f in findings}
        self.assertNotIn("crux:FIRST_INPUT_DELAY_MS", matches)

    def test_slow_crux_is_high_severity(self):
        findings = PSI.normalise(self.raw, url="https://whispaste.de/")
        cls = next(
            f for f in findings if f["match"] == "crux:CUMULATIVE_LAYOUT_SHIFT_SCORE"
        )
        self.assertEqual(cls["severity"], "high")


class PagespeedSkipBehaviour(unittest.TestCase):
    def test_skips_silently_without_key(self):
        env = dict(os.environ)
        env.pop("PAGESPEED_API_KEY", None)
        captured = io.StringIO()
        with contextlib.redirect_stderr(captured):
            findings = PSI.run(
                "https://whispaste.de/",
                env=env,
                fetcher=lambda u: {"unreached": True},
            )
        self.assertEqual(findings, [])
        # Optional: log the skip on stderr so the user can see why.
        self.assertIn("PAGESPEED_API_KEY", captured.getvalue())

    def test_runs_with_injected_fetcher_when_key_present(self):
        env = dict(os.environ)
        env["PAGESPEED_API_KEY"] = "fake"
        sample = json.loads(FIXTURE.read_text(encoding="utf-8"))

        def fake_fetcher(url):
            return sample

        findings = PSI.run(
            "https://whispaste.de/", env=env, fetcher=fake_fetcher
        )
        self.assertTrue(findings)


if __name__ == "__main__":
    unittest.main(verbosity=2)
