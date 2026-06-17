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


class CredentialsPresentTests(unittest.TestCase):
    """Flutter/iOS repo with a .p8 file and fastlane Appfile — credential section populated.

    This fixture also verifies the security hard constraint: the script must
    report file existence/path only and must never emit the file's contents.
    The dummy .p8 file contains a known sentinel string ('DUMMY_P8_PLACEHOLDER_CONTENT').
    If that string appears in stdout, the script is leaking secrets.
    """

    @classmethod
    def setUpClass(cls):
        cls.result = _run("with_credentials")
        try:
            cls.data = json.loads(cls.result.stdout)
        except json.JSONDecodeError:
            cls.data = None

    def test_exit_code_zero(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)

    def test_stdout_is_valid_json(self):
        self.assertIsNotNone(self.data, "stdout is not valid JSON")

    def test_credentials_section_present(self):
        self.assertIn("credentials", self.data, "Missing top-level 'credentials' key")

    def test_p8_file_detected(self):
        creds = self.data["credentials"]
        self.assertGreater(len(creds["p8_files"]), 0, "Expected at least one .p8 entry")

    def test_p8_path_field_present(self):
        p8 = self.data["credentials"]["p8_files"][0]
        self.assertIn("path", p8)

    def test_p8_path_ends_with_p8(self):
        p8 = self.data["credentials"]["p8_files"][0]
        self.assertTrue(p8["path"].endswith(".p8"), f"Expected .p8 extension, got: {p8['path']}")

    def test_p8_path_is_relative(self):
        # Path must be relative so it is portable and does not reveal the host filesystem.
        p8 = self.data["credentials"]["p8_files"][0]
        self.assertFalse(os.path.isabs(p8["path"]), f"Expected relative path, got: {p8['path']}")

    def test_fastlane_appfile_detected(self):
        self.assertIsNotNone(
            self.data["credentials"]["fastlane_appfile"],
            "Expected fastlane_appfile to be non-null when Appfile exists",
        )

    def test_fastlane_appfile_path_field(self):
        appfile = self.data["credentials"]["fastlane_appfile"]
        self.assertIn("path", appfile)

    # --- Security hard constraint: no secret contents ever emitted ---

    def test_p8_sentinel_not_in_stdout(self):
        """The dummy .p8 contains 'DUMMY_P8_PLACEHOLDER_CONTENT'. Must never appear in output."""
        self.assertNotIn(
            "DUMMY_P8_PLACEHOLDER_CONTENT",
            self.result.stdout,
            "Secret leak: .p8 file contents appeared in stdout",
        )

    def test_no_pem_header_in_output(self):
        """Real .p8 keys start with '-----BEGIN'. Must never appear in output."""
        self.assertNotIn("-----BEGIN", self.result.stdout)

    def test_no_password_in_output(self):
        self.assertNotIn("password", self.result.stdout.lower())


class CredentialsAbsentTests(unittest.TestCase):
    """Flutter/iOS repo with no credential files — credentials section reflects absence.

    Reuses the happy_path fixture, which has no .p8 files, no fastlane/Appfile,
    and no .env files.
    """

    @classmethod
    def setUpClass(cls):
        cls.result = _run("happy_path")
        try:
            cls.data = json.loads(cls.result.stdout)
        except json.JSONDecodeError:
            cls.data = None

    def test_exit_code_zero(self):
        self.assertEqual(self.result.returncode, 0, self.result.stderr)

    def test_credentials_section_present(self):
        self.assertIn("credentials", self.data, "Missing top-level 'credentials' key")

    def test_p8_files_empty(self):
        self.assertEqual(
            self.data["credentials"]["p8_files"],
            [],
            "Expected empty p8_files list when no .p8 files exist",
        )

    def test_fastlane_appfile_absent(self):
        self.assertIsNone(
            self.data["credentials"]["fastlane_appfile"],
            "Expected fastlane_appfile to be null when Appfile does not exist",
        )

    def test_fastlane_env_absent(self):
        self.assertIsNone(
            self.data["credentials"]["fastlane_env"],
            "Expected fastlane_env to be null when no .env file exists",
        )

    def test_credentials_subfields_present(self):
        creds = self.data["credentials"]
        for field in ("p8_files", "fastlane_appfile", "fastlane_env", "env_hints"):
            self.assertIn(field, creds, f"Missing credentials sub-field: {field}")


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
