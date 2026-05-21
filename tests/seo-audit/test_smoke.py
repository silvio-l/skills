#!/usr/bin/env python3
"""End-to-end smoke test for the seo-audit skill.

Runs the dispatcher (`skills/seo-audit/scripts/audit.py`) against the
fixture site under `tests/seo-audit/fixtures/sample-site/`, writing the
generated report into a temp directory. Verifies that:

* the report file is created and is named `seo-audit-<YYYY-MM-DD>.md`,
* the four canonical sections are present,
* the contrastive page contributed zero findings.

Run from the repo root:
    python3 tests/seo-audit/test_smoke.py
"""

import datetime
import glob
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
FIXTURE = REPO_ROOT / "tests" / "seo-audit" / "fixtures" / "sample-site"
AUDIT = SCRIPTS_DIR / "audit.py"

sys.dont_write_bytecode = True


class Smoke(unittest.TestCase):
    def _run(self, *args) -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, str(AUDIT), *args],
            capture_output=True, text=True, env=env,
        )

    def test_produces_report_with_four_sections(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run("--root", str(FIXTURE), "--report-dir", tmp)
            self.assertEqual(result.returncode, 0,
                             msg=f"stderr={result.stderr}\nstdout={result.stdout}")

            today = datetime.date.today().strftime("%Y-%m-%d")
            expected_name = f"seo-audit-{today}.md"
            reports = glob.glob(os.path.join(tmp, "*.md"))
            self.assertEqual(len(reports), 1,
                             msg=f"expected one report, got {reports}")
            self.assertEqual(os.path.basename(reports[0]), expected_name)

            content = pathlib.Path(reports[0]).read_text(encoding="utf-8")
            self.assertIn("## Executive Summary", content)
            self.assertIn("## Findings nach Kategorie", content)
            self.assertIn("## Diff zum letzten Lauf", content)
            self.assertIn("## Empfehlungen", content)

    def test_findings_reference_fixture_files_only_outside_contrastive(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run("--root", str(FIXTURE), "--report-dir", tmp)
            self.assertEqual(result.returncode, 0,
                             msg=f"stderr={result.stderr}\nstdout={result.stdout}")
            report = glob.glob(os.path.join(tmp, "*.md"))[0]
            content = pathlib.Path(report).read_text(encoding="utf-8")
            # Should mention index.html and about.html, never contrastive.html.
            self.assertIn("index.html", content)
            self.assertIn("about.html", content)
            self.assertNotIn("contrastive.html", content)

    def test_quick_flag_is_accepted_without_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run("--root", str(FIXTURE),
                               "--report-dir", tmp, "--quick")
            self.assertEqual(result.returncode, 0,
                             msg=f"stderr={result.stderr}")

    def test_compare_last_with_no_prior_report_leaves_diff_empty(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = self._run("--root", str(FIXTURE),
                               "--report-dir", tmp, "--compare-last")
            self.assertEqual(result.returncode, 0)
            report = glob.glob(os.path.join(tmp, "*.md"))[0]
            content = pathlib.Path(report).read_text(encoding="utf-8")
            # The diff section must still exist; content notes "no prior run".
            diff_match = re.search(
                r"## Diff zum letzten Lauf\n(.*?)(?=\n## |\Z)",
                content, re.DOTALL,
            )
            self.assertIsNotNone(diff_match)


if __name__ == "__main__":
    unittest.main(verbosity=2)
