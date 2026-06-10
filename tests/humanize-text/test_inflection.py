#!/usr/bin/env python3
"""Tests for the opt-in `inflect` lexicon flag — humanize-text.

The scanner matches lexicon patterns with \\b…\\b by default (exact token).
Entries may set `"inflect": true` to capture purely-additive German
declension endings (nahtlos → nahtlose/nahtlosen/nahtloser …) by compiling
the trailing boundary as \\w*\\b instead.

A stemming bug here fails silently: it would over-match unrelated words or
under-match inflected forms without changing any exit code, so it gets an
explicit test (see CLAUDE.md testing policy).

Run from repo root:
    python3 tests/humanize-text/test_inflection.py
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "humanize-text" / "scripts"
LEXICON_DIR = REPO_ROOT / "skills" / "humanize-text"
LEXICON_DE = LEXICON_DIR / "lexicon.de.json"
LEXICON_EN = LEXICON_DIR / "lexicon.en.json"
sys.path.insert(0, str(SCRIPTS_DIR))

import slop_scanner  # noqa: E402


def _load(path: pathlib.Path) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


class TestInflectionFlag(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._de = _load(LEXICON_DE)
        self._en = _load(LEXICON_EN)

    def tearDown(self):
        self._tmp.cleanup()

    def _scan(self, text: str, lexicon: list) -> set:
        path = os.path.join(self._tmp.name, "in.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return {f["pattern_id"] for f in slop_scanner.scan_file(path, lexicon)}

    # --- inflect=true: additive German endings are matched -------------------

    def test_inflected_adjective_forms_match(self):
        """nahtlose / ganzheitlichen / tiefgreifender hit their stem entry."""
        cases = {
            "Eine nahtlose Integration.\n": "de_nahtlos",
            "Ein ganzheitlichen Ansatz.\n": "de_ganzheitlich",
            "Eine tiefgreifender Wandel.\n": "de_tiefgreifend",
            "Die revolutionäre Idee.\n": "de_revolutionaer",
        }
        for text, pid in cases.items():
            with self.subTest(text=text):
                self.assertIn(pid, self._scan(text, self._de))

    def test_uninflected_base_form_still_matches(self):
        """The bare stem must still match when inflect=true."""
        self.assertIn("de_nahtlos", self._scan("Das ist nahtlos.\n", self._de))

    # --- inflect default off: exact-match contract preserved -----------------

    def test_non_inflect_de_entry_does_not_stem(self):
        """de_letztendlich has no inflect flag → must not match a longer token."""
        # "Letztendliche" is not standard German, but the point is the scanner
        # must NOT stem an entry that did not opt in.
        ids = self._scan("Letztendliche Dinge.\n", self._de)
        self.assertNotIn("de_letztendlich", ids)

    def test_en_entries_never_stem(self):
        """English is exact-match only: 'leverages' must not hit en_leverage."""
        ids = self._scan("This leverages our tools.\n", self._en)
        self.assertNotIn("en_leverage", ids)

    def test_inflect_does_not_overmatch_prefix_collision(self):
        """\\w* must not let a stem swallow an unrelated following word."""
        # "nahtlos" + space: the \\w* stops at the word boundary, so the match
        # is exactly 'nahtlos', never 'nahtlos integration' across the space.
        path = os.path.join(self._tmp.name, "in2.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Eine nahtlose Lösung.\n")
        findings = slop_scanner.scan_file(path, self._de)
        matches = [f["match"] for f in findings if f["pattern_id"] == "de_nahtlos"]
        self.assertEqual(["nahtlose"], matches)


if __name__ == "__main__":
    unittest.main()
