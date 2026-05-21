#!/usr/bin/env python3
"""Tests for the audit.py dispatcher wiring of --push and --dry-run."""

import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
AUDIT = SCRIPTS_DIR / "audit.py"
FIXTURE = REPO_ROOT / "tests" / "seo-audit" / "fixtures" / "sample-site"


def _run(*args, env=None) -> subprocess.CompletedProcess:
    base_env = dict(os.environ)
    base_env["PYTHONDONTWRITEBYTECODE"] = "1"
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, str(AUDIT), *args],
        capture_output=True, text=True, env=base_env,
    )


class PushDispatcher(unittest.TestCase):
    def test_dry_run_requires_push_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(
                "--root", str(FIXTURE),
                "--report-dir", tmp,
                "--dry-run",
            )
            self.assertNotEqual(result.returncode, 0,
                                msg=f"stdout={result.stdout}\nstderr={result.stderr}")
            self.assertIn("--dry-run", result.stderr)
            self.assertIn("--push", result.stderr)

    def test_push_dry_run_emits_markdown_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(
                "--root", str(FIXTURE),
                "--report-dir", tmp,
                "--push", "--dry-run",
            )
            self.assertEqual(result.returncode, 0,
                             msg=f"stderr={result.stderr}\nstdout={result.stdout}")
            # The plan section appears on stdout.
            self.assertIn("push — dry-run plan", result.stdout)
            self.assertIn("IndexNow", result.stdout)
            self.assertIn("Bing", result.stdout)

    def test_no_push_flag_means_no_plan_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = _run(
                "--root", str(FIXTURE),
                "--report-dir", tmp,
            )
            self.assertEqual(result.returncode, 0)
            self.assertNotIn("push — dry-run plan", result.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
