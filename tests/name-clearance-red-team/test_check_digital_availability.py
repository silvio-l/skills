#!/usr/bin/env python3
"""Tests for name-clearance-red-team/scripts/check_digital_availability.py.

Network-free by design - only the pure classifiers (classify_rdap,
classify_by_http_existence) are under test. These are exactly the functions
that decide "available" vs. "taken" vs. "unknown"; a bug here produces a
plausible-but-wrong domain-availability claim that nothing else in the
pipeline would catch.

Run from the repo root:
    python3 tests/name-clearance-red-team/test_check_digital_availability.py
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "name-clearance-red-team" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import check_digital_availability as C  # noqa: E402


class ClassifyRdapTests(unittest.TestCase):
    def test_404_is_available(self):
        status, reason = C.classify_rdap(404, "")
        self.assertEqual(status, "available")

    def test_200_with_ldhname_is_taken(self):
        status, reason = C.classify_rdap(200, '{"ldhName": "example.com"}')
        self.assertEqual(status, "taken")

    def test_200_without_ldhname_is_unknown(self):
        status, reason = C.classify_rdap(200, '{"foo": "bar"}')
        self.assertEqual(status, "unknown")

    def test_200_unparseable_body_is_unknown(self):
        status, reason = C.classify_rdap(200, "not json{")
        self.assertEqual(status, "unknown")

    def test_tld_not_in_bootstrap_is_unknown_never_available(self):
        status, reason = C.classify_rdap(404, "", tld_supported=False)
        self.assertEqual(status, "unknown")
        self.assertNotEqual(status, "available")

    def test_network_error_is_unknown(self):
        status, reason = C.classify_rdap(None, "")
        self.assertEqual(status, "unknown")

    def test_rate_limited_is_unknown(self):
        for code in (429, 503):
            with self.subTest(code=code):
                status, reason = C.classify_rdap(code, "")
                self.assertEqual(status, "unknown")

    def test_unexpected_status_is_unknown(self):
        status, reason = C.classify_rdap(500, "")
        self.assertEqual(status, "unknown")


class ClassifyByHttpExistenceTests(unittest.TestCase):
    def test_404_is_available(self):
        status, reason = C.classify_by_http_existence(404, "npm")
        self.assertEqual(status, "available")

    def test_200_is_taken(self):
        status, reason = C.classify_by_http_existence(200, "npm")
        self.assertEqual(status, "taken")

    def test_network_error_is_unknown(self):
        status, reason = C.classify_by_http_existence(None, "npm")
        self.assertEqual(status, "unknown")

    def test_unexpected_status_is_unknown(self):
        status, reason = C.classify_by_http_existence(500, "npm")
        self.assertEqual(status, "unknown")

    def test_reason_carries_source_label(self):
        _, reason = C.classify_by_http_existence(404, "pypi")
        self.assertIn("pypi", reason)


class SlugifyTests(unittest.TestCase):
    def test_lowercases_and_strips_non_alnum(self):
        self.assertEqual(C.slugify("My Brand!"), "mybrand")

    def test_umlaut_stripped_not_transliterated(self):
        # slugify is a crude ASCII filter for API calls, not a linguistic transform
        self.assertEqual(C.slugify("Bär"), "br")


if __name__ == "__main__":
    unittest.main()
