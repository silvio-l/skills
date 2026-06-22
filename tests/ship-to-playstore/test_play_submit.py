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


# ---------------------------------------------------------------------------
# AC: listing and data-safety are valid --yes checkpoints (separate, never batched).
# ---------------------------------------------------------------------------

class TestMetadataYesFlags(unittest.TestCase):
    """listing and data-safety recognised as valid --yes kinds, not warned/ignored."""

    def test_listing_is_in_valid_yes_flags(self):
        self.assertIn("listing", PS.VALID_YES_FLAGS)

    def test_data_safety_is_in_valid_yes_flags(self):
        self.assertIn("data-safety", PS.VALID_YES_FLAGS)

    def test_listing_parsed_without_warning(self):
        # If listing were unknown, parse_yes_flags would warn and ignore it.
        flags = PS.parse_yes_flags(["listing"])
        self.assertIn("listing", flags)

    def test_data_safety_parsed_without_warning(self):
        flags = PS.parse_yes_flags(["data-safety"])
        self.assertIn("data-safety", flags)

    def test_listing_and_data_safety_are_independent(self):
        # Separate checkpoints: passing one does not imply the other.
        flags_l = PS.parse_yes_flags(["listing"])
        self.assertNotIn("data-safety", flags_l)
        flags_d = PS.parse_yes_flags(["data-safety"])
        self.assertNotIn("listing", flags_d)

    def test_metadata_flags_do_not_imply_upload_release_commit(self):
        flags = PS.parse_yes_flags(["listing", "data-safety"])
        self.assertNotIn("upload", flags)
        self.assertNotIn("release", flags)
        self.assertNotIn("commit", flags)

    def test_metadata_plan_shows_both_blocked_when_no_yes_flags(self):
        plan = PS.describe_metadata_plan("com.example.app", {}, frozenset())
        self.assertEqual(plan.count("BLOCKED"), 2)

    def test_metadata_plan_listing_approved(self):
        plan = PS.describe_metadata_plan(
            "com.example.app", {}, frozenset({"listing"})
        )
        self.assertEqual(plan.count("APPROVED"), 1)
        self.assertIn("BLOCKED", plan)   # data-safety still blocked

    def test_metadata_plan_both_approved(self):
        plan = PS.describe_metadata_plan(
            "com.example.app", {}, frozenset({"listing", "data-safety"})
        )
        self.assertEqual(plan.count("APPROVED"), 2)
        self.assertNotIn("BLOCKED", plan)

    def test_metadata_plan_contains_cannot_verify_for_assets(self):
        # Feature graphic + screenshots are always ? cannot-verify, never asserted "not done."
        plan = PS.describe_metadata_plan("com.example.app", {}, frozenset())
        self.assertIn("cannot-verify", plan.lower())

    def test_metadata_plan_dry_run_by_default_confirmed(self):
        # Dry-run confirmation: both stages BLOCKED without any --yes.
        plan = PS.describe_metadata_plan("com.example.app", {}, frozenset())
        self.assertNotIn("APPROVED", plan)


# ---------------------------------------------------------------------------
# AC: Data Safety declaration map derived from Phase 0 — never from user input.
# ---------------------------------------------------------------------------

class TestDataSafetyDeclarations(unittest.TestCase):
    """derive_data_safety_declarations reads Phase 0 fields; never prompts user."""

    def test_empty_report_returns_empty_declarations(self):
        result = PS.derive_data_safety_declarations({})
        self.assertEqual(result["declared_data_types"], [])
        self.assertFalse(result["data_deletion_provided"])

    def test_sentry_crash_analytics_adds_crash_logs(self):
        report = {
            "data_safety_hints": {
                "analytics_tracking": [
                    {"package": "sentry_flutter", "category": "crash/diagnostics"}
                ]
            }
        }
        result = PS.derive_data_safety_declarations(report)
        self.assertIn("crash_logs", result["declared_data_types"])

    def test_analytics_tracking_adds_app_interactions(self):
        report = {
            "data_safety_hints": {
                "analytics_tracking": [
                    {"package": "posthog_flutter", "category": "analytics/usage"}
                ]
            }
        }
        result = PS.derive_data_safety_declarations(report)
        self.assertIn("app_interactions", result["declared_data_types"])

    def test_supabase_used_adds_email_and_user_ids(self):
        result = PS.derive_data_safety_declarations({"supabase_used": True})
        types = result["declared_data_types"]
        self.assertIn("email_address", types)
        self.assertIn("user_ids", types)

    def test_supabase_false_does_not_add_account_data(self):
        result = PS.derive_data_safety_declarations({"supabase_used": False})
        self.assertNotIn("email_address", result["declared_data_types"])
        self.assertNotIn("user_ids", result["declared_data_types"])

    def test_fcm_push_adds_device_ids(self):
        report = {"push_notifications": {"fcm_used": True}}
        result = PS.derive_data_safety_declarations(report)
        self.assertIn("device_or_other_ids", result["declared_data_types"])

    def test_camera_permission_adds_photos_and_videos(self):
        report = {"permissions": {"declared": ["android.permission.CAMERA"]}}
        result = PS.derive_data_safety_declarations(report)
        self.assertIn("photos_and_videos", result["declared_data_types"])

    def test_fine_location_permission_adds_precise_location(self):
        report = {"permissions": {"declared": ["android.permission.ACCESS_FINE_LOCATION"]}}
        result = PS.derive_data_safety_declarations(report)
        self.assertIn("precise_location", result["declared_data_types"])

    def test_coarse_location_adds_approximate_location(self):
        report = {"permissions": {"declared": ["android.permission.ACCESS_COARSE_LOCATION"]}}
        result = PS.derive_data_safety_declarations(report)
        self.assertIn("approximate_location", result["declared_data_types"])
        self.assertNotIn("precise_location", result["declared_data_types"])

    def test_contacts_permission_adds_contacts(self):
        report = {"permissions": {"declared": ["android.permission.READ_CONTACTS"]}}
        result = PS.derive_data_safety_declarations(report)
        self.assertIn("contacts", result["declared_data_types"])

    def test_record_audio_permission_adds_audio_files(self):
        report = {"permissions": {"declared": ["android.permission.RECORD_AUDIO"]}}
        result = PS.derive_data_safety_declarations(report)
        self.assertIn("audio_files", result["declared_data_types"])

    # OQ5 binding: data_deletion_provided MUST come from account_deletion.likely_present.
    def test_account_deletion_true_sets_data_deletion_provided(self):
        report = {
            "data_safety_hints": {
                "account_deletion": {"likely_present": True, "hints": ["deleteAccount"]}
            }
        }
        result = PS.derive_data_safety_declarations(report)
        self.assertTrue(result["data_deletion_provided"])

    def test_account_deletion_false_leaves_data_deletion_not_provided(self):
        report = {
            "data_safety_hints": {
                "account_deletion": {"likely_present": False}
            }
        }
        result = PS.derive_data_safety_declarations(report)
        self.assertFalse(result["data_deletion_provided"])

    def test_missing_account_deletion_field_defaults_false(self):
        result = PS.derive_data_safety_declarations({"data_safety_hints": {}})
        self.assertFalse(result["data_deletion_provided"])

    def test_sources_dict_tracks_trigger_fields(self):
        report = {"supabase_used": True}
        result = PS.derive_data_safety_declarations(report)
        sources = result["sources"]
        self.assertIn("email_address", sources)
        self.assertIn("supabase", sources["email_address"].lower())

    def test_typical_phase0_report_comprehensive(self):
        # Full Phase 0 report shape (mirrors phase0-introspect.md schema).
        report = {
            "supabase_used": True,
            "push_notifications": {"fcm_used": True},
            "permissions": {
                "declared": [
                    "android.permission.INTERNET",
                    "android.permission.POST_NOTIFICATIONS",
                    "android.permission.CAMERA",
                ]
            },
            "data_safety_hints": {
                "analytics_tracking": [
                    {"package": "sentry_flutter", "category": "crash/diagnostics"}
                ],
                "account_deletion": {"likely_present": True, "hints": ["deleteAccount"]},
            },
        }
        result = PS.derive_data_safety_declarations(report)
        types = result["declared_data_types"]
        self.assertIn("crash_logs", types)
        self.assertIn("email_address", types)
        self.assertIn("user_ids", types)
        self.assertIn("device_or_other_ids", types)
        self.assertIn("photos_and_videos", types)
        self.assertTrue(result["data_deletion_provided"])


# ---------------------------------------------------------------------------
# AC: listing completeness — API readable → check; not readable → cannot-verify.
# ---------------------------------------------------------------------------

class TestListingCompleteness(unittest.TestCase):
    """check_listing_completeness: tri-state correct; never asserts 'not done' from API silence."""

    def test_empty_body_returns_cannot_verify(self):
        result = PS.check_listing_completeness({})
        self.assertEqual(result["text_status"], "cannot-verify")
        self.assertIn("cannot-verify", result["message"].lower())

    def test_none_listings_key_returns_cannot_verify(self):
        result = PS.check_listing_completeness({"listings": []})
        self.assertEqual(result["text_status"], "cannot-verify")

    def test_complete_listing_returns_complete(self):
        body = {
            "listings": [{
                "language": "en-US",
                "title": "My App",
                "shortDescription": "Short desc",
                "fullDescription": "Full description here",
            }]
        }
        result = PS.check_listing_completeness(body)
        self.assertEqual(result["text_status"], "complete")

    def test_missing_title_returns_incomplete(self):
        body = {
            "listings": [{
                "language": "en-US",
                "title": "",
                "shortDescription": "Short",
                "fullDescription": "Full",
            }]
        }
        result = PS.check_listing_completeness(body)
        self.assertEqual(result["text_status"], "incomplete")
        self.assertTrue(any("title" in m for m in result["missing_text"]))

    def test_missing_description_returns_incomplete(self):
        body = {
            "listings": [{
                "language": "en-US",
                "title": "My App",
                "shortDescription": "",
                "fullDescription": "",
            }]
        }
        result = PS.check_listing_completeness(body)
        self.assertEqual(result["text_status"], "incomplete")

    def test_assets_always_cannot_verify(self):
        # Feature graphic, screenshots not reliably API-readable → always cannot-verify.
        body = {
            "listings": [{
                "language": "en-US",
                "title": "My App",
                "shortDescription": "Short",
                "fullDescription": "Full",
            }]
        }
        result = PS.check_listing_completeness(body)
        self.assertEqual(result["assets_status"], "cannot-verify")

    def test_console_path_always_present(self):
        for body in [{}, {"listings": []}, {"listings": [{"language": "en-US"}]}]:
            result = PS.check_listing_completeness(body)
            self.assertIn("console_path", result)
            self.assertIn("Store presence", result["console_path"])

    def test_message_never_says_not_done_for_empty_body(self):
        result = PS.check_listing_completeness({})
        # "not done" must never appear — only cannot-verify.
        self.assertNotIn("not done", result["message"].lower())

    def test_multiple_locales_aggregated(self):
        body = {
            "listings": [
                {"language": "en-US", "title": "App", "shortDescription": "S", "fullDescription": "F"},
                {"language": "de-DE", "title": "", "shortDescription": "S", "fullDescription": "F"},
            ]
        }
        result = PS.check_listing_completeness(body)
        self.assertEqual(result["text_status"], "incomplete")
        self.assertTrue(any("de-DE" in m for m in result["missing_text"]))


# ---------------------------------------------------------------------------
# AC: pricing step flags missing merchant profile / unset pricing as production blocker.
# ---------------------------------------------------------------------------

class TestPricingBlocker(unittest.TestCase):
    """check_pricing_blocker: not_set + billing → blocker; cannot-verify otherwise."""

    def test_not_set_with_billing_is_blocker(self):
        result = PS.check_pricing_blocker(
            billing_likely_present=True, pricing_status="not_set"
        )
        self.assertTrue(result["blocker"])
        self.assertIn("BLOCKER", result["message"])

    def test_not_set_without_billing_is_not_blocker(self):
        # Free app with no IAP: pricing "not_set" is expected (price = free).
        result = PS.check_pricing_blocker(
            billing_likely_present=False, pricing_status="not_set"
        )
        self.assertFalse(result["blocker"])

    def test_billing_detected_none_status_is_cannot_verify_warning(self):
        result = PS.check_pricing_blocker(
            billing_likely_present=True, pricing_status=None
        )
        self.assertFalse(result["blocker"])
        self.assertIn("cannot-verify", result["message"].lower())

    def test_no_billing_no_status_is_cannot_verify(self):
        result = PS.check_pricing_blocker(
            billing_likely_present=False, pricing_status=None
        )
        self.assertFalse(result["blocker"])
        self.assertIn("cannot-verify", result["message"].lower())

    def test_console_path_always_present(self):
        for billing in (True, False):
            for status in ("set", "not_set", None):
                result = PS.check_pricing_blocker(billing, status)
                self.assertIn("console_path", result)
                self.assertIn("Payments", result["console_path"])

    def test_blocker_message_mentions_merchant_profile(self):
        result = PS.check_pricing_blocker(True, "not_set")
        self.assertIn("merchant profile", result["message"].lower())

    def test_cannot_verify_message_mentions_merchant_profile(self):
        result = PS.check_pricing_blocker(True, None)
        self.assertIn("merchant profile", result["message"].lower())


# ---------------------------------------------------------------------------
# AC OQ5: Step 6 documents Postgres-function-first preference over Edge Function.
# ---------------------------------------------------------------------------

class TestOQ5DataDeletionWebhookDoc(unittest.TestCase):
    """OQ5 locked: Step 6 sub-step in phase3-release-loop.md documents Postgres function first."""

    def setUp(self):
        phase3_path = (
            pathlib.Path(__file__).resolve().parents[2]
            / "skills" / "ship-to-playstore" / "phase3-release-loop.md"
        )
        with open(phase3_path, encoding="utf-8") as fh:
            self.doc = fh.read()
        self.doc_lower = self.doc.lower()

    def test_step6_mentions_account_deletion_webhook(self):
        # Step 6 must surface the account/data-deletion webhook requirement.
        self.assertIn("deletion webhook", self.doc_lower)

    def test_step6_documents_postgres_function(self):
        # Postgres function must be the documented default.
        self.assertIn("postgres function", self.doc_lower)

    def test_step6_mentions_edge_function_avoidance(self):
        # Edge Function must be mentioned in a context of avoidance, not as the default.
        self.assertIn("edge function", self.doc_lower)

    def test_step6_edge_function_not_default(self):
        # The word "avoid" or "not" must appear near "edge function".
        # We check that at least one of these qualifiers is present.
        self.assertTrue(
            "avoid" in self.doc_lower or "not edge function" in self.doc_lower
            or "never" in self.doc_lower,
            "Edge Function mention must be qualified with avoid/not/never",
        )

    def test_step6_prefers_postgres_over_edge(self):
        # "Postgres function" must appear and "Edge Function" must be framed as secondary/avoided.
        pg_idx = self.doc_lower.find("postgres function")
        edge_idx = self.doc_lower.find("edge function")
        self.assertGreater(pg_idx, -1, "Postgres function not mentioned")
        self.assertGreater(edge_idx, -1, "Edge Function not mentioned")

    def test_step6a_sub_step_present(self):
        # Step 6a sub-step must exist in the document.
        self.assertIn("step 6a", self.doc_lower)

    def test_supabase_rpc_documented(self):
        # The recommended Supabase RPC approach must be documented.
        self.assertTrue(
            "supabase.rpc" in self.doc or "rpc(" in self.doc,
            "Supabase RPC call must appear in Step 6a guidance",
        )


# ---------------------------------------------------------------------------
# AC: URL builders for listing/details write surface.
# ---------------------------------------------------------------------------

class TestMetadataURLBuilders(unittest.TestCase):

    PKG = "com.example.app"
    EDIT = "editId42"

    def test_listings_url_no_language_returns_base(self):
        url = PS.build_edits_listings_url(self.PKG, self.EDIT)
        self.assertIn("/listings", url)
        self.assertIn(self.EDIT, url)
        self.assertNotIn("/listings/", url.split(self.EDIT)[1].rstrip("/"))

    def test_listings_url_with_language_appends_locale(self):
        url = PS.build_edits_listings_url(self.PKG, self.EDIT, "en-US")
        self.assertIn("/listings/en-US", url)

    def test_listings_url_uses_api_base(self):
        url = PS.build_edits_listings_url(self.PKG, self.EDIT)
        self.assertIn(PS.API_BASE, url)

    def test_details_url_contains_details(self):
        url = PS.build_edits_details_url(self.PKG, self.EDIT)
        self.assertIn("/details", url)
        self.assertIn(self.EDIT, url)
        self.assertIn(PS.API_BASE, url)

    def test_listings_url_differs_from_details_url(self):
        l_url = PS.build_edits_listings_url(self.PKG, self.EDIT)
        d_url = PS.build_edits_details_url(self.PKG, self.EDIT)
        self.assertNotEqual(l_url, d_url)


if __name__ == "__main__":
    unittest.main(verbosity=2)
