#!/usr/bin/env python3
"""Tests for ship-to-appstore/scripts/phase0-introspect.

Run from the repo root:
    python3 tests/ship-to-appstore/test_phase0.py

Tests exercise the script's stdout/exit-code contract (the highest available
seam) against three synthetic fixture repos:
  - fixtures/happy_path/      : full Flutter/iOS project with signing config
  - fixtures/non_flutter/     : no pubspec.yaml at all
  - fixtures/missing_signing/ : Flutter/iOS project without Team ID or signing style

Lives outside skills/ on purpose: the skills CLI bundles a skill directory
as-is, and shipping tests to every install would bloat the bundle.
See CLAUDE.md -> "Tooling and testing".
"""

import json
import os
import subprocess
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT = os.path.join(REPO_ROOT, "skills", "ship-to-appstore", "scripts", "phase0-introspect")
FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


def _run(fixture_name: str) -> subprocess.CompletedProcess:
    """Run the introspection script against a named fixture directory."""
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, SCRIPT, os.path.join(FIXTURES, fixture_name)],
        capture_output=True,
        text=True,
        env=env,
    )


class HappyPathTests(unittest.TestCase):
    """Full Flutter/iOS project — all situation-report fields expected."""

    @classmethod
    def setUpClass(cls):
        cls.result = _run("happy_path")
        try:
            cls.data = json.loads(cls.result.stdout)
        except json.JSONDecodeError:
            cls.data = None

    def test_exit_code_zero(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)

    def test_stdout_is_valid_json(self):
        self.assertIsNotNone(self.data, "stdout is not valid JSON")
        self.assertIsInstance(self.data, dict)

    def test_flutter_ios_true(self):
        self.assertTrue(self.data["flutter_ios"])

    def test_app_display_name(self):
        self.assertEqual(self.data["app_display_name"], "test_app")

    def test_marketing_version(self):
        self.assertEqual(self.data["marketing_version"], "1.2.3")

    def test_build_number(self):
        self.assertEqual(self.data["build_number"], "5")

    def test_bundle_id(self):
        self.assertEqual(self.data["bundle_id"], "com.example.testapp")

    def test_team_id(self):
        self.assertEqual(self.data["team_id"], "ABCD123456")

    def test_signing_style_automatic(self):
        self.assertEqual(self.data["signing_style"], "automatic")

    def test_icon_set_complete(self):
        self.assertTrue(self.data["icon_set"]["complete"])
        self.assertEqual(self.data["icon_set"]["missing_sizes"], [])

    def test_icon_set_counts(self):
        self.assertEqual(self.data["icon_set"]["total_required"], 3)
        self.assertEqual(self.data["icon_set"]["present"], 3)

    def test_launch_assets_storyboard_present(self):
        self.assertTrue(self.data["launch_assets"]["has_launch_screen_storyboard"])

    def test_launch_assets_no_launch_image_dir(self):
        # happy_path fixture has no LaunchImage.imageset — that is normal for
        # modern Flutter projects that use a LaunchScreen storyboard instead.
        self.assertFalse(self.data["launch_assets"]["has_launch_image_assets"])

    def test_all_required_top_level_fields_present(self):
        required = [
            "flutter_ios",
            "app_display_name",
            "marketing_version",
            "build_number",
            "bundle_id",
            "team_id",
            "signing_style",
            "icon_set",
            "launch_assets",
        ]
        for field in required:
            self.assertIn(field, self.data, f"Missing top-level field: {field}")

    def test_icon_set_subfields_present(self):
        for field in ("complete", "missing_sizes", "total_required", "present"):
            self.assertIn(field, self.data["icon_set"], f"Missing icon_set field: {field}")

    def test_launch_assets_subfields_present(self):
        for field in ("has_launch_screen_storyboard", "has_launch_image_assets"):
            self.assertIn(field, self.data["launch_assets"], f"Missing launch_assets field: {field}")

    def test_no_pem_certificates_in_output(self):
        # Verify the script never emits PEM-encoded secrets.
        self.assertNotIn("-----BEGIN", self.result.stdout)

    def test_no_api_key_in_output(self):
        self.assertNotIn("api_key", self.result.stdout.lower())

    def test_no_password_in_output(self):
        self.assertNotIn("password", self.result.stdout.lower())


class NonFlutterTests(unittest.TestCase):
    """Non-Flutter repo — script must abort cleanly with a warning."""

    @classmethod
    def setUpClass(cls):
        cls.result = _run("non_flutter")

    def test_exit_code_is_1(self):
        self.assertEqual(self.result.returncode, 1)

    def test_stderr_contains_warning(self):
        self.assertIn("WARNING", self.result.stderr)

    def test_stderr_mentions_flutter(self):
        self.assertIn("Flutter", self.result.stderr)

    def test_stdout_is_empty(self):
        # No JSON situation report emitted for non-Flutter repos.
        self.assertEqual(self.result.stdout.strip(), "")


class MissingSigningTests(unittest.TestCase):
    """Flutter/iOS project without Team ID or signing style in pbxproj."""

    @classmethod
    def setUpClass(cls):
        cls.result = _run("missing_signing")
        try:
            cls.data = json.loads(cls.result.stdout)
        except json.JSONDecodeError:
            cls.data = None

    def test_exit_code_zero(self):
        # Still a Flutter/iOS project — just missing signing config.
        self.assertEqual(self.result.returncode, 0, self.result.stderr)

    def test_stdout_is_valid_json(self):
        self.assertIsNotNone(self.data, "stdout is not valid JSON")

    def test_team_id_is_null(self):
        self.assertIsNone(self.data["team_id"])

    def test_signing_style_is_unknown(self):
        self.assertEqual(self.data["signing_style"], "unknown")

    def test_bundle_id_extracted(self):
        self.assertEqual(self.data["bundle_id"], "com.example.missingapp")

    def test_flutter_ios_true(self):
        self.assertTrue(self.data["flutter_ios"])

    def test_marketing_version(self):
        self.assertEqual(self.data["marketing_version"], "2.0.0")

    def test_build_number(self):
        self.assertEqual(self.data["build_number"], "10")


class NoCachePollutionTest(unittest.TestCase):
    """Running the tests must not leave __pycache__ inside skills/."""

    def test_no_pycache_under_skills(self):
        skills_dir = os.path.join(REPO_ROOT, "skills")
        for dirpath, dirnames, _ in os.walk(skills_dir):
            # Modify dirnames in-place so os.walk does not descend further.
            if "__pycache__" in dirnames:
                self.fail(
                    f"__pycache__ found under skills/: {os.path.join(dirpath, '__pycache__')}"
                )


if __name__ == "__main__":
    unittest.main(verbosity=2)
