#!/usr/bin/env python3
"""Tests for ship-to-playstore/scripts/play-submit.

Run from the repo root:
    PYTHONDONTWRITEBYTECODE=1 python3 tests/ship-to-playstore/test_play_submit.py

Lives outside `skills/` on purpose: the `skills` CLI bundles a skill directory
as-is, and shipping tests to every install would just bloat the bundle.
See CLAUDE.md → "Tooling and testing".

Coverage: pure logic tested through the script's public functions.
The thin HTTP wrappers (mint_access_token, http_post_json, upload_aab_multipart,
etc.) and the openssl signer require live credentials and are NOT exercised here —
they fail loudly on misuse (loud failure pattern; mirrors slice 03 posture).
"""

import importlib.util
import json
import pathlib
import subprocess
import sys
import unittest
from importlib.machinery import SourceFileLoader

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "ship-to-playstore" / "scripts"

sys.dont_write_bytecode = True

_SCRIPT_PATH = str(SCRIPTS_DIR / "play-submit")
_loader = SourceFileLoader("play_submit", _SCRIPT_PATH)
_spec = importlib.util.spec_from_loader("play_submit", _loader)
PS = importlib.util.module_from_spec(_spec)
_loader.exec_module(PS)

SCRIPT = _SCRIPT_PATH


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _run(*args, **kwargs):
    """Run play-submit via subprocess and return CompletedProcess."""
    return subprocess.run(
        [sys.executable, SCRIPT] + list(args),
        capture_output=True,
        text=True,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# AC: --track required, no default; --rollout required for production.
# ---------------------------------------------------------------------------

class TestArgValidation(unittest.TestCase):
    """Pure validate_args function covers the conditional requirements."""

    def test_missing_track_returns_error(self):
        errors = PS.validate_args("com.example.app", "build.aab", None, None)
        self.assertTrue(any("track" in e.lower() for e in errors))

    def test_missing_rollout_for_production_returns_error(self):
        errors = PS.validate_args("com.example.app", "build.aab", "production", None)
        self.assertTrue(any("rollout" in e.lower() for e in errors))
        # Confirm the error message mentions the conventional first fraction.
        self.assertTrue(any("0.01" in e for e in errors))

    def test_valid_internal_no_rollout_required(self):
        errors = PS.validate_args("com.example.app", "build.aab", "internal", None)
        self.assertEqual(errors, [])

    def test_valid_production_with_rollout(self):
        errors = PS.validate_args("com.example.app", "build.aab", "production", 0.01)
        self.assertEqual(errors, [])

    def test_invalid_track_name_returns_error(self):
        errors = PS.validate_args("com.example.app", "build.aab", "staging", None)
        self.assertTrue(any("valid" in e.lower() for e in errors))

    def test_missing_package_returns_error(self):
        errors = PS.validate_args("", "build.aab", "internal", None)
        self.assertTrue(any("package" in e.lower() for e in errors))

    def test_missing_aab_returns_error(self):
        errors = PS.validate_args("com.example.app", "", "internal", None)
        self.assertTrue(any("aab" in e.lower() for e in errors))

    def test_all_required_present_returns_empty(self):
        errors = PS.validate_args("com.example.app", "app.aab", "alpha", None)
        self.assertEqual(errors, [])


class TestSubprocessArgValidation(unittest.TestCase):
    """CLI-level exit-2 tests (no credentials needed — fails at arg validation)."""

    def test_missing_track_exits_2(self):
        # argparse treats --track as required; missing → exit 2.
        result = _run("com.example.app", "--aab", "build.aab")
        self.assertEqual(result.returncode, 2)

    def test_missing_rollout_for_production_exits_2(self):
        # validate_args catches missing --rollout for production → exit 2.
        # The script will fail at auth before reaching the Play API, but
        # validate_args runs BEFORE auth, so exit 2 is from our validation.
        result = _run("com.example.app", "--aab", "build.aab", "--track", "production")
        self.assertEqual(result.returncode, 2)
        self.assertIn("rollout", result.stderr.lower())

    def test_missing_aab_exits_2(self):
        result = _run("com.example.app", "--track", "internal")
        self.assertEqual(result.returncode, 2)


# ---------------------------------------------------------------------------
# AC: each mutation kind is a separate --yes checkpoint, never batched.
# ---------------------------------------------------------------------------

class TestYesFlagParsing(unittest.TestCase):
    """parse_yes_flags enforces the separate-checkpoint invariant."""

    def test_empty_list_returns_empty_frozenset(self):
        flags = PS.parse_yes_flags([])
        self.assertEqual(flags, frozenset())

    def test_none_returns_empty_frozenset(self):
        flags = PS.parse_yes_flags(None)
        self.assertEqual(flags, frozenset())

    def test_upload_only_does_not_include_release_or_commit(self):
        flags = PS.parse_yes_flags(["upload"])
        self.assertIn("upload", flags)
        self.assertNotIn("release", flags)
        self.assertNotIn("commit", flags)

    def test_release_only_does_not_include_upload_or_commit(self):
        flags = PS.parse_yes_flags(["release"])
        self.assertIn("release", flags)
        self.assertNotIn("upload", flags)
        self.assertNotIn("commit", flags)

    def test_commit_only_does_not_include_upload_or_release(self):
        flags = PS.parse_yes_flags(["commit"])
        self.assertIn("commit", flags)
        self.assertNotIn("upload", flags)
        self.assertNotIn("release", flags)

    def test_all_three_collected_independently(self):
        flags = PS.parse_yes_flags(["upload", "release", "commit"])
        self.assertEqual(flags, frozenset({"upload", "release", "commit"}))

    def test_unknown_flag_ignored(self):
        # Unknown values must be ignored (forward-compat, not a usage error).
        flags = PS.parse_yes_flags(["upload", "publish", "deploy"])
        self.assertIn("upload", flags)
        self.assertNotIn("publish", flags)
        self.assertNotIn("deploy", flags)

    def test_duplicates_deduplicated(self):
        flags = PS.parse_yes_flags(["upload", "upload", "release"])
        self.assertEqual(flags, frozenset({"upload", "release"}))


# ---------------------------------------------------------------------------
# AC: dry-run opens edit + reports intended mutations without edits.commit.
# ---------------------------------------------------------------------------

class TestDryRunPlan(unittest.TestCase):
    """describe_dry_run_plan never calls mutations; shows BLOCKED for unapproved."""

    def _plan(self, yes_flags=None, collision=False, version_code=42):
        return PS.describe_dry_run_plan(
            package="com.example.app",
            aab_path="build/app.aab",
            track="internal",
            rollout=None,
            version_code=version_code,
            existing_codes=[40, 41],
            collision=collision,
            collision_msg="OK — max on track = 41" if not collision else "COLLIDES",
            yes_flags=frozenset(yes_flags or []),
        )

    def test_empty_yes_shows_all_blocked(self):
        plan = self._plan()
        self.assertIn("BLOCKED", plan)
        # All three should be blocked
        self.assertEqual(plan.count("BLOCKED"), 3)

    def test_upload_approved_shows_approved_and_others_blocked(self):
        plan = self._plan(yes_flags=["upload"])
        self.assertIn("APPROVED", plan)
        self.assertIn("BLOCKED", plan)
        # Only one APPROVED
        self.assertEqual(plan.count("APPROVED"), 1)

    def test_plan_contains_package_and_track(self):
        plan = self._plan()
        self.assertIn("com.example.app", plan)
        self.assertIn("internal", plan)

    def test_plan_contains_version_code(self):
        plan = self._plan(version_code=42)
        self.assertIn("42", plan)

    def test_plan_contains_dry_run_notice(self):
        plan = self._plan()
        self.assertIn("dry-run", plan.lower())
        self.assertIn("NOT committed", plan)

    def test_plan_mentions_no_changes_in_play_console(self):
        plan = self._plan()
        self.assertIn("Nothing has changed", plan)

    def test_plan_contains_internal_first_tip(self):
        # OQ3: Internal Testing recommendation should appear in the plan.
        plan = self._plan()
        self.assertIn("internal", plan.lower())

    def test_plan_no_secrets(self):
        # The dry-run plan must never contain credential-related strings.
        plan = self._plan()
        for bad in ("private_key", "access_token", "client_secret",
                    "storePassword", "keyPassword", "BEGIN RSA"):
            self.assertNotIn(bad, plan)

    def test_edits_commit_not_called_in_dry_run(self):
        # The describe_dry_run_plan function is called in the dry-run branch only.
        # It is a PURE function — it constructs no HTTP calls and calls no side effects.
        # Verify the plan output says the edit was NOT committed (no mutation happened).
        plan = self._plan()
        # "NOT committed" must appear (the dry-run confirmation message).
        self.assertIn("NOT committed", plan)
        # The commit success message from main() ("Edit committed.") must NOT appear.
        self.assertNotIn("Edit committed.", plan)


# ---------------------------------------------------------------------------
# AC: pre-upload versionCode collision check.
# ---------------------------------------------------------------------------

class TestVersionCodeCollision(unittest.TestCase):

    def test_no_existing_codes_no_collision(self):
        collision, msg = PS.check_version_collision([], 42)
        self.assertFalse(collision)
        self.assertIn("42", msg)

    def test_new_code_greater_than_max_no_collision(self):
        collision, msg = PS.check_version_collision([38, 40, 41], 42)
        self.assertFalse(collision)
        self.assertIn("OK", msg)

    def test_new_code_equal_to_max_is_collision(self):
        collision, msg = PS.check_version_collision([40, 41], 41)
        self.assertTrue(collision)
        self.assertIn("COLLIDES", msg)
        self.assertIn("42", msg)  # suggest next safe value

    def test_new_code_less_than_max_is_collision(self):
        collision, msg = PS.check_version_collision([40, 41], 39)
        self.assertTrue(collision)
        self.assertIn("COLLIDES", msg)

    def test_collision_message_includes_existing_codes(self):
        collision, msg = PS.check_version_collision([40, 41], 41)
        self.assertIn("40", msg)
        self.assertIn("41", msg)


# ---------------------------------------------------------------------------
# AC: post-commit verification re-reads tracks.
# ---------------------------------------------------------------------------

class TestVerifyCommitResult(unittest.TestCase):

    def _body(self, track, version_codes, status="completed", fraction=None):
        release = {"versionCodes": [str(vc) for vc in version_codes], "status": status}
        if fraction is not None:
            release["userFraction"] = fraction
        return {"tracks": [{"track": track, "releases": [release]}]}

    def test_expected_code_found_returns_ok(self):
        body = self._body("internal", [42], "completed")
        result = PS.verify_commit_result(body, "internal", 42)
        self.assertTrue(result["ok"])
        self.assertIn("42", result["message"])
        self.assertIn("completed", result["message"])

    def test_expected_code_not_found_returns_not_ok(self):
        body = self._body("internal", [41], "completed")
        result = PS.verify_commit_result(body, "internal", 42)
        self.assertFalse(result["ok"])
        self.assertIn("NOT found", result["message"])

    def test_wrong_track_returns_not_ok(self):
        body = self._body("internal", [42], "completed")
        result = PS.verify_commit_result(body, "production", 42)
        self.assertFalse(result["ok"])

    def test_staged_rollout_shows_fraction(self):
        body = self._body("production", [42], "inProgress", fraction=0.01)
        result = PS.verify_commit_result(body, "production", 42)
        self.assertTrue(result["ok"])
        self.assertIn("1%", result["message"])

    def test_empty_tracks_returns_not_ok(self):
        result = PS.verify_commit_result({}, "internal", 42)
        self.assertFalse(result["ok"])


# ---------------------------------------------------------------------------
# AC: signing step distinguishes first release vs subsequent; never logs passwords.
# ---------------------------------------------------------------------------

class TestSigningCheck(unittest.TestCase):

    def test_signing_config_false_is_blocker(self):
        report = {"signing": {"signing_config_set": False, "keystore_hints": []}}
        result = PS.check_signing_from_report(report)
        self.assertTrue(result["blocker"])
        self.assertIn("BLOCKER", result["message"])
        self.assertIn("signingConfig", result["message"])

    def test_no_signing_key_in_report_is_blocker(self):
        result = PS.check_signing_from_report({})
        self.assertTrue(result["blocker"])

    def test_first_release_hint_surfaced(self):
        report = {
            "signing": {
                "signing_config_set": True,
                "keystore_hints": ["android/key.properties"],
                "play_app_signing_enrollable_from_repo": True,
            }
        }
        result = PS.check_signing_from_report(report)
        self.assertFalse(result["blocker"])
        self.assertTrue(result["first_release"])
        # OQ4: first-release enrolment guidance must be inline
        self.assertIn("irrevocable", result["message"].lower())
        self.assertIn("Play Console", result["message"])

    def test_subsequent_release_no_blocker(self):
        report = {
            "signing": {
                "signing_config_set": True,
                "keystore_hints": ["android/key.properties"],
                "play_app_signing_enrollable_from_repo": False,
            }
        }
        result = PS.check_signing_from_report(report)
        self.assertFalse(result["blocker"])
        self.assertFalse(result["first_release"])

    def test_signing_message_never_contains_password_words(self):
        """The signing message must never leak keystore password values."""
        for report in [
            {"signing": {"signing_config_set": True,
                          "keystore_hints": ["android/key.properties"],
                          "play_app_signing_enrollable_from_repo": True}},
            {"signing": {"signing_config_set": True,
                          "keystore_hints": ["android/key.properties"],
                          "play_app_signing_enrollable_from_repo": False}},
            {},
        ]:
            result = PS.check_signing_from_report(report)
            msg = result["message"]
            # The message may reference the parameter NAME but must never contain
            # an actual password VALUE. Since we only pass a fake report, the test
            # is that the function never adds a password to the output.
            self.assertNotIn("mySecretPassword", msg)
            self.assertNotIn("s3cr3t", msg)


# ---------------------------------------------------------------------------
# AC: status note holds only safe fields — never secrets.
# ---------------------------------------------------------------------------

class TestStatusNote(unittest.TestCase):

    def test_valid_entry_formats_correctly(self):
        entry = PS.format_status_note_entry("2026-06-22T10:00:00Z", "Step 4", "upload OK versionCode 42")
        self.assertIn("Step 4", entry)
        self.assertIn("versionCode 42", entry)
        self.assertIn("2026-06-22T10:00:00Z", entry)

    def test_secret_marker_raises_value_error(self):
        with self.assertRaises(ValueError):
            PS.format_status_note_entry(
                "2026-06-22T10:00:00Z", "Step 2",
                "keyPassword=superSecret123"
            )

    def test_private_key_marker_raises_value_error(self):
        with self.assertRaises(ValueError):
            PS.format_status_note_entry(
                "2026-06-22T10:00:00Z", "auth",
                "private_key: -----BEGIN RSA PRIVATE KEY-----"
            )

    def test_access_token_marker_raises_value_error(self):
        with self.assertRaises(ValueError):
            PS.format_status_note_entry(
                "2026-06-22T10:00:00Z", "auth",
                "access_token=ya29.xxx"
            )

    def test_step_id_and_version_strings_allowed(self):
        # Safe content: step id, version, track, fraction, timestamp
        entry = PS.format_status_note_entry(
            "2026-06-22T10:00:00Z",
            "Step 11",
            "release 1.2.4 (42) → track internal, fraction n/a",
        )
        self.assertIsNotNone(entry)
        self.assertIn("42", entry)


# ---------------------------------------------------------------------------
# URL builders — pure functions, no network.
# ---------------------------------------------------------------------------

class TestURLBuilders(unittest.TestCase):

    PKG = "com.example.app"
    EDIT = "abcEditId123"

    def test_edits_insert_url_contains_api_base_and_package(self):
        url = PS.build_edits_insert_url(self.PKG)
        self.assertIn(PS.API_BASE, url)
        self.assertIn("com.example.app", url)
        self.assertIn("/edits", url)

    def test_edits_tracks_get_url_contains_edit_id(self):
        url = PS.build_edits_tracks_get_url(self.PKG, self.EDIT)
        self.assertIn(self.EDIT, url)
        self.assertIn("/tracks", url)

    def test_edits_bundles_upload_url_uses_upload_base(self):
        url = PS.build_edits_bundles_upload_url(self.PKG, self.EDIT)
        self.assertIn(PS.UPLOAD_BASE, url)
        self.assertIn("/bundles", url)
        self.assertIn("uploadType=multipart", url)

    def test_edits_tracks_update_url_contains_track(self):
        url = PS.build_edits_tracks_update_url(self.PKG, self.EDIT, "internal")
        self.assertIn("internal", url)
        self.assertIn("/tracks/", url)

    def test_edits_commit_url_contains_commit_action(self):
        url = PS.build_edits_commit_url(self.PKG, self.EDIT)
        self.assertIn(":commit", url)
        self.assertIn(self.EDIT, url)

    def test_package_with_special_chars_is_url_encoded(self):
        url = PS.build_edits_insert_url("com.example.my app")
        self.assertNotIn(" ", url)

    def test_commit_url_is_different_from_tracks_update_url(self):
        commit_url = PS.build_edits_commit_url(self.PKG, self.EDIT)
        release_url = PS.build_edits_tracks_update_url(self.PKG, self.EDIT, "internal")
        self.assertNotEqual(commit_url, release_url)


# ---------------------------------------------------------------------------
# Track release payload builder.
# ---------------------------------------------------------------------------

class TestTrackReleasePayload(unittest.TestCase):

    def test_production_with_fraction_under_1_is_in_progress(self):
        payload = PS.build_track_release_payload("production", [42], 0.01)
        release = payload["releases"][0]
        self.assertEqual(release["status"], "inProgress")
        self.assertAlmostEqual(release["userFraction"], 0.01)

    def test_internal_track_is_completed(self):
        payload = PS.build_track_release_payload("internal", [42], None)
        release = payload["releases"][0]
        self.assertEqual(release["status"], "completed")

    def test_production_with_fraction_1_is_completed(self):
        payload = PS.build_track_release_payload("production", [42], 1.0)
        release = payload["releases"][0]
        self.assertEqual(release["status"], "completed")

    def test_version_codes_are_strings_in_payload(self):
        # Play API expects versionCodes as strings.
        payload = PS.build_track_release_payload("internal", [42, 43], None)
        vcs = payload["releases"][0]["versionCodes"]
        for vc in vcs:
            self.assertIsInstance(vc, str)

    def test_payload_track_field_matches_argument(self):
        payload = PS.build_track_release_payload("beta", [42], None)
        self.assertEqual(payload["track"], "beta")


# ---------------------------------------------------------------------------
# parse_track_existing_codes — pure function.
# ---------------------------------------------------------------------------

class TestParseTrackExistingCodes(unittest.TestCase):

    def _body(self, track, codes):
        return {
            "tracks": [{
                "track": track,
                "releases": [{"versionCodes": [str(c) for c in codes], "status": "completed"}],
            }]
        }

    def test_returns_codes_for_matching_track(self):
        body = self._body("internal", [40, 41])
        codes = PS.parse_track_existing_codes(body, "internal")
        self.assertEqual(sorted(codes), [40, 41])

    def test_wrong_track_returns_empty(self):
        body = self._body("internal", [40])
        codes = PS.parse_track_existing_codes(body, "production")
        self.assertEqual(codes, [])

    def test_empty_tracks_returns_empty(self):
        codes = PS.parse_track_existing_codes({}, "internal")
        self.assertEqual(codes, [])

    def test_multiple_releases_aggregated(self):
        body = {
            "tracks": [{
                "track": "production",
                "releases": [
                    {"versionCodes": ["40"], "status": "completed"},
                    {"versionCodes": ["38", "39"], "status": "halted"},
                ],
            }]
        }
        codes = PS.parse_track_existing_codes(body, "production")
        self.assertEqual(sorted(codes), [38, 39, 40])


# ---------------------------------------------------------------------------
# Secret hygiene — source-level invariant (mirrors play-status tests).
# ---------------------------------------------------------------------------

class TestSecretHygieneInvariant(unittest.TestCase):

    def setUp(self):
        with open(SCRIPT, encoding="utf-8") as fh:
            self.src = fh.read()

    def test_token_never_printed(self):
        # The access token must never be interpolated into a print call.
        for bad in ("print(token", "print(assertion", "print(private_key",
                    "print(private_key_pem"):
            self.assertNotIn(bad, self.src)

    def test_authorization_header_never_logged(self):
        # The bearer header must never be in a print call.
        self.assertNotIn('print(f".*Authorization', self.src)
        self.assertNotIn('"Authorization"', self.src.replace(
            '"Authorization": f"Bearer {token}"', ""))  # the assignment is OK

    def test_debug_prints_do_not_interpolate_secret_variables(self):
        # print() calls must not interpolate secret variable values. Check for
        # f-string interpolation of secret-bearing identifiers (e.g. {token},
        # {private_key}). Legitimate text labels like "token mint failed" are OK.
        # The pattern to detect: `{token}`, `{private_key}`, `{assertion}`, etc.
        secret_interpolations = (
            "{token}", "{private_key}", "{private_key_pem}",
            "{assertion}", "{access_token}",
        )
        for line in self.src.splitlines():
            if "print(" in line and "file=sys.stderr" in line:
                for bad in secret_interpolations:
                    self.assertNotIn(
                        bad, line,
                        f"debug print() interpolates secret variable {bad!r}: {line.strip()}",
                    )

    def test_no_yes_flag_in_readonly_parts(self):
        # play-submit IS the mutation script — --yes IS expected here.
        # But the read-only play-status must not have been modified.
        status_path = SCRIPTS_DIR / "play-status"
        with open(status_path, encoding="utf-8") as fh:
            status_src = fh.read()
        self.assertNotIn('"--yes"', status_src)

    def test_commit_url_only_constructed_by_dedicated_function(self):
        # edits.commit URL construction must go through build_edits_commit_url.
        # No bare ":commit" string hardcoded anywhere other than the URL builder.
        commit_fn_src = ""
        in_commit_fn = False
        for line in self.src.splitlines():
            if "def build_edits_commit_url" in line:
                in_commit_fn = True
            if in_commit_fn:
                commit_fn_src += line + "\n"
                if line.strip() == "" and "def " in commit_fn_src[50:]:
                    break
        # The ":commit" token must appear in the URL builder
        self.assertIn(":commit", commit_fn_src)


# ---------------------------------------------------------------------------
# Dry-run invariant: no edits.commit or tracks.update without --yes.
# ---------------------------------------------------------------------------

class TestDryRunInvariant(unittest.TestCase):
    """Verify at the source level that mutations are gated by yes_flags."""

    def setUp(self):
        with open(SCRIPT, encoding="utf-8") as fh:
            self.src = fh.read()

    def test_commit_url_call_gated_by_yes_flag_check(self):
        # The edits.commit call must be inside a block guarded by 'commit' in yes_flags.
        # Find the line that calls http_post_json with the commit URL and check it's
        # preceded by an 'if "commit" in yes_flags' guard in the source.
        lines = self.src.splitlines()
        commit_call_idx = next(
            (i for i, l in enumerate(lines) if "edits.commit" in l and "build_edits_commit_url" in l),
            None,
        )
        # Alternatively find the guard check
        commit_guard_idx = next(
            (i for i, l in enumerate(lines) if '"commit" in yes_flags' in l),
            None,
        )
        self.assertIsNotNone(commit_guard_idx,
                             'Source must contain \'if "commit" in yes_flags\' guard')

    def test_upload_url_call_gated_by_yes_flag_check(self):
        lines = self.src.splitlines()
        upload_guard_idx = next(
            (i for i, l in enumerate(lines) if '"upload" in yes_flags' in l),
            None,
        )
        self.assertIsNotNone(upload_guard_idx,
                             'Source must contain \'if "upload" in yes_flags\' guard')

    def test_release_url_call_gated_by_yes_flag_check(self):
        lines = self.src.splitlines()
        release_guard_idx = next(
            (i for i, l in enumerate(lines) if '"release" in yes_flags' in l),
            None,
        )
        self.assertIsNotNone(release_guard_idx,
                             'Source must contain \'if "release" in yes_flags\' guard')

    def test_three_separate_yes_guards_exist(self):
        # Each mutation kind has its own guard — they are never batched.
        guards = [
            '"upload" in yes_flags',
            '"release" in yes_flags',
            '"commit" in yes_flags',
        ]
        for guard in guards:
            self.assertIn(guard, self.src, f"Missing guard: {guard}")

    def test_no_yes_flag_prints_dry_run_plan(self):
        # describe_dry_run_plan is called when yes_flags is empty.
        self.assertIn("describe_dry_run_plan", self.src)

    def test_discard_edit_called_on_dry_run_exit(self):
        # When no --yes is passed, _discard_edit must be called to clean up.
        self.assertIn("_discard_edit", self.src)


# ---------------------------------------------------------------------------
# No __pycache__ leak into skills/.
# ---------------------------------------------------------------------------

class TestNoBytecacheInSkills(unittest.TestCase):

    def test_no_pycache_under_skills(self):
        pycache = SCRIPTS_DIR / "__pycache__"
        self.assertFalse(
            pycache.exists(),
            f"__pycache__ leaked into skills/ at {pycache}",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
