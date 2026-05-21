#!/usr/bin/env python3
"""Tests for the audit.py dispatcher wiring of --doctor / --setup / --verify.

Each test runs `audit.py` as a subprocess with the project fixture to
stay realistic. No real network call — verify is exercised via env
strip so all four tools skip cleanly.
"""

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
    # Strip every key the verify/doctor code might touch so the run is
    # deterministic and offline.
    base_env = {
        k: v for k, v in os.environ.items()
        if k not in (
            "INDEXNOW_KEY", "PAGESPEED_API_KEY", "BING_WEBMASTER_API_KEY",
            "BING_DAILY_LIMIT",
        )
    }
    base_env["PYTHONDONTWRITEBYTECODE"] = "1"
    base_env["PATH"] = base_env.get("PATH", "")
    if env:
        base_env.update(env)
    return subprocess.run(
        [sys.executable, str(AUDIT), *args],
        capture_output=True, text=True, env=base_env,
    )


class DoctorMode(unittest.TestCase):
    def test_doctor_alone_runs_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--doctor")
            self.assertEqual(r.returncode, 0,
                             msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("seo-audit doctor", r.stdout)

    def test_doctor_emits_all_seven_section_titles(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--doctor")
            for title in ("npx tools", "IndexNow", "PageSpeed",
                          "Bing Webmaster", "GSC MCP", "Domain file",
                          "public/-path"):
                with self.subTest(title=title):
                    self.assertIn(title, r.stdout)


class VerifyMode(unittest.TestCase):
    def test_verify_alone_runs_and_exits_zero(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--verify")
            self.assertEqual(r.returncode, 0,
                             msg=f"stdout={r.stdout}\nstderr={r.stderr}")
            self.assertIn("seo-audit verify", r.stdout)

    def test_doctor_and_verify_run_sequentially(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--doctor", "--verify")
            self.assertEqual(r.returncode, 0,
                             msg=f"stderr={r.stderr}")
            doctor_idx = r.stdout.find("seo-audit doctor")
            verify_idx = r.stdout.find("seo-audit verify")
            self.assertNotEqual(doctor_idx, -1)
            self.assertNotEqual(verify_idx, -1)
            self.assertLess(doctor_idx, verify_idx,
                            "doctor section must come before verify")


class SetupMode(unittest.TestCase):
    def test_setup_unknown_tool_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--setup", "foo")
            self.assertEqual(r.returncode, 2)

    def test_setup_combined_with_doctor_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--setup", "pagespeed", "--doctor")
            self.assertEqual(r.returncode, 2)
            self.assertIn("single-tool", r.stderr)

    def test_setup_combined_with_verify_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--setup", "bing", "--verify")
            self.assertEqual(r.returncode, 2)

    def test_setup_indexnow_generates_key_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            # Build a tiny fake repo with a public dir.
            repo = tmp_path / "repo"
            repo.mkdir()
            public = repo / "public"
            public.mkdir()
            # IndexNow setup will detect public/ via the fallback path.
            r = _run("--root", str(repo),
                     "--dist", str(public),
                     "--report-dir", str(tmp_path / "scratch"),
                     "--setup", "indexnow")
            self.assertEqual(r.returncode, 0,
                             msg=f"stderr={r.stderr}\nstdout={r.stdout}")
            self.assertIn("export INDEXNOW_KEY=", r.stdout)
            # Exactly one .txt key file appeared.
            keys = list(public.glob("*.txt"))
            self.assertEqual(len(keys), 1)
            # Idempotent: second run keeps the same file.
            existing_key = keys[0].stem
            r2 = _run("--root", str(repo),
                      "--dist", str(public),
                      "--report-dir", str(tmp_path / "scratch"),
                      "--setup", "indexnow",
                      env={"INDEXNOW_KEY": existing_key})
            self.assertEqual(r2.returncode, 0)
            self.assertIn("already configured", r2.stdout)
            # Still only one key file.
            self.assertEqual(len(list(public.glob("*.txt"))), 1)

    def test_setup_indexnow_force_regenerates(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = pathlib.Path(tmp)
            repo = tmp_path / "repo"
            repo.mkdir()
            public = repo / "public"
            public.mkdir()
            (public / "oldkey.txt").write_text("oldkey", encoding="utf-8")
            r = _run("--root", str(repo),
                     "--dist", str(public),
                     "--report-dir", str(tmp_path / "scratch"),
                     "--setup", "indexnow", "--force",
                     env={"INDEXNOW_KEY": "oldkey"})
            self.assertEqual(r.returncode, 0, msg=r.stderr)
            keys = list(public.glob("*.txt"))
            self.assertEqual(len(keys), 2)  # old + new

    def test_setup_pagespeed_emits_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--setup", "pagespeed")
            self.assertEqual(r.returncode, 0)
            self.assertIn("PageSpeed", r.stdout)
            self.assertIn("PAGESPEED_API_KEY", r.stdout)

    def test_setup_bing_emits_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--setup", "bing")
            self.assertEqual(r.returncode, 0)
            self.assertIn("Bing Webmaster", r.stdout)
            self.assertIn("BING_WEBMASTER_API_KEY", r.stdout)

    def test_setup_gsc_emits_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--setup", "gsc")
            self.assertEqual(r.returncode, 0)
            self.assertIn("GSC", r.stdout)
            self.assertIn("mcp__gsc__reauthenticate", r.stdout)

    def test_force_without_setup_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp,
                     "--force")
            self.assertEqual(r.returncode, 2)


class NoFlagsRegression(unittest.TestCase):
    def test_audit_without_setup_flags_still_writes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = _run("--root", str(FIXTURE),
                     "--report-dir", tmp)
            self.assertEqual(r.returncode, 0,
                             msg=f"stderr={r.stderr}\nstdout={r.stdout}")
            # Existing audit flow prints the absolute report path.
            self.assertIn("seo-audit-", r.stdout)
            self.assertNotIn("seo-audit doctor", r.stdout)
            self.assertNotIn("seo-audit verify", r.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
