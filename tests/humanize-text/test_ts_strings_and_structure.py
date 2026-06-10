#!/usr/bin/env python3
"""Tests for general .ts string-literal extraction + strategy-aware structure.

Two behaviours that fail silently if broken (CLAUDE.md testing policy):

1. `.ts` files are scanned by extracting EVERY quoted string-literal value
   (i18n dictionaries, SEO maps, summary blocks), not just `summary { de, en }`.
   A regression here would silently make the scanner blind to real site copy.

2. Structure detectors (em-dash, negative parallelism) run over the SAME prose
   segments as the lexicon, so em-dashes inside comments / code / HTML tags are
   NOT flagged. A regression would silently flood real files with false hits.

Run from repo root:
    python3 tests/humanize-text/test_ts_strings_and_structure.py
"""

from __future__ import annotations

import os
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "humanize-text" / "scripts"
SKILL_DIR = REPO_ROOT / "skills" / "humanize-text"
sys.path.insert(0, str(SCRIPTS_DIR))

import slop_scanner  # noqa: E402


class TestTsStringExtraction(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _scan(self, text, lang, name="in.ts"):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return slop_scanner.scan_file_with_language(path, lang, str(SKILL_DIR))

    def test_i18n_dict_nested_values_scanned(self):
        """Slop inside a nested i18n dict value (no summary block) is found."""
        text = (
            "export const en = {\n"
            "  hero: {\n"
            "    title: 'We leverage cutting-edge tools.',\n"
            "    sub: 'A robust, seamless experience.',\n"
            "  },\n"
            "};\n"
        )
        ids = {f["pattern_id"] for f in self._scan(text, "en")["findings"]}
        self.assertIn("en_leverage", ids)
        self.assertIn("en_robust", ids)
        self.assertIn("en_seamless", ids)

    def test_identifier_not_scanned(self):
        """A slop word as an identifier (not quoted) must not fire."""
        text = "export const leverage = (x) => x;\nconst robust = 1;\n"
        ids = {f["pattern_id"] for f in self._scan(text, "en")["findings"]}
        self.assertNotIn("en_leverage", ids)
        self.assertNotIn("en_robust", ids)

    def test_double_and_backtick_strings_scanned(self):
        """Double-quoted and template-literal values are scanned too."""
        text = (
            'const a = "This is a groundbreaking result.";\n'
            "const b = `A myriad of options.`;\n"
        )
        ids = {f["pattern_id"] for f in self._scan(text, "en")["findings"]}
        self.assertIn("en_groundbreaking", ids)
        self.assertIn("en_myriad", ids)


class TestStrategyAwareStructure(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _scan(self, text, lang, name):
        path = os.path.join(self._tmp.name, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return slop_scanner.scan_file_with_language(path, lang, str(SKILL_DIR))

    def test_em_dash_in_ts_comment_not_flagged(self):
        """An em-dash in a .ts comment must NOT produce a punctuation finding."""
        text = (
            "// Honesty over marketing — no overclaims.\n"
            "export const de = {\n"
            "  tag: 'Klarer Text ohne Floskeln.',\n"
            "};\n"
        )
        punct = [f for f in self._scan(text, "de", "c.ts")["findings"]
                 if f["type"] == "punctuation"]
        self.assertEqual([], punct,
                         "em-dash inside a comment must not be flagged")

    def test_em_dash_in_ts_string_value_is_flagged(self):
        """An em-dash inside a string VALUE is real prose and IS flagged."""
        text = "export const de = {\n  lede: 'Technik — mein Spielplatz.',\n};\n"
        punct = [f for f in self._scan(text, "de", "v.ts")["findings"]
                 if f["type"] == "punctuation"]
        self.assertEqual(1, len(punct))
        self.assertEqual(2, punct[0]["line_number"])

    def test_em_dash_in_html_tag_not_flagged(self):
        """An em-dash inside an HTML attribute/tag region is not prose."""
        # The em-dash sits inside a comment-like tag attribute, stripped out.
        text = '<a title="a—b"></a>\n<p>Plain text.</p>\n'
        punct = [f for f in self._scan(text, "en", "p.html")["findings"]
                 if f["type"] == "punctuation"]
        self.assertEqual([], punct)


class TestNegativeParallelismFrames(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmp.cleanup()

    def _struct(self, text):
        path = os.path.join(self._tmp.name, "n.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return [f for f in slop_scanner.scan_file_with_structure(path, str(SKILL_DIR))
                if f["pattern_id"] == "struct_neg_parallelism"]

    def test_its_not_x_its_y(self):
        self.assertTrue(self._struct("It's not just a tool, it's a way of life.\n"))

    def test_not_a_x_but_a_y(self):
        self.assertTrue(self._struct("This is not a bug, but a feature.\n"))

    def test_de_es_geht_nicht_um(self):
        self.assertTrue(self._struct("Es geht nicht um Geld, sondern um Haltung.\n"))

    def test_ordinary_sentence_not_flagged(self):
        self.assertEqual([], self._struct("We ship a tool that helps people.\n"))


if __name__ == "__main__":
    unittest.main()
