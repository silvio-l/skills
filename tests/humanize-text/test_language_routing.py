#!/usr/bin/env python3
"""Tests for EN lexicon and language routing — humanize-text slice 02.

Observable-behaviour only: tests drive the CLI and the public API.
No internal helpers tested directly.

Run from repo root:
    python3 tests/humanize-text/test_language_routing.py
    python3 -m unittest discover -s tests/humanize-text -t . -p 'test_*.py'
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

# EN text hitting all EN tier-1 patterns we curated
_EN_TIER1_TEXT = (
    "You should delve into this topic carefully.\n"          # en_delve
    "This forms a rich tapestry of ideas.\n"                 # en_tapestry
    "We can leverage our existing tools.\n"                  # en_leverage
    "It's worth noting that results may vary.\n"             # en_worth_noting
    "This is a groundbreaking discovery.\n"                  # en_groundbreaking
    "The landscape of modern tech is evolving.\n"            # en_landscape
    "We need a robust solution here.\n"                      # en_robust
    "This is a crucial step forward.\n"                      # en_crucial
    "Let us foster collaboration across teams.\n"            # en_foster
    "The realm of AI is expanding rapidly.\n"                # en_realm
)

# DE text from slice 01 — must NOT trigger EN patterns
_DE_TIER1_TEXT = (
    "Zudem ist das ein wichtiger Punkt.\n"
    "Darüber hinaus gibt es weitere Aspekte.\n"
    "Es ist wichtig zu beachten, dass wir aufpassen.\n"
    "Im Hinblick auf die Zukunft müssen wir handeln.\n"
    "In der heutigen Welt ist alles vernetzt.\n"
)

_EN_EXPECTED_IDS = {
    "en_delve",
    "en_tapestry",
    "en_leverage",
    "en_worth_noting",
    "en_groundbreaking",
    "en_landscape",
    "en_robust",
    "en_crucial",
    "en_foster",
    "en_realm",
}

_DE_EXPECTED_IDS = {
    "de_zudem",
    "de_darueber_hinaus",
    "de_wichtig_zu_beachten",
    "de_im_hinblick_auf",
    "de_heutigen_welt",
}


def _load_lexicon(path: pathlib.Path) -> list:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _write_temp(tmpdir: str, text: str, name: str = "input.md") -> str:
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ---------------------------------------------------------------------------
# AC1: lexicon.en.json — file exists, correct shape
# ---------------------------------------------------------------------------

class TestENLexiconShape(unittest.TestCase):
    """AC1: lexicon.en.json exists with curated EN tier-1 entries, same shape as DE."""

    def test_en_lexicon_file_exists(self):
        """AC1: lexicon.en.json must exist."""
        self.assertTrue(LEXICON_EN.is_file(),
                        f"Missing file: {LEXICON_EN}")

    def test_en_lexicon_is_valid_json_list(self):
        """AC1: lexicon.en.json is a valid JSON list."""
        entries = _load_lexicon(LEXICON_EN)
        self.assertIsInstance(entries, list)
        self.assertGreater(len(entries), 0)

    def test_en_lexicon_required_keys(self):
        """AC1: every entry has pattern_id, pattern, type, tier."""
        entries = _load_lexicon(LEXICON_EN)
        required = {"pattern_id", "pattern", "type", "tier"}
        for e in entries:
            missing = required - set(e.keys())
            self.assertEqual(set(), missing,
                             f"Entry missing keys {missing}: {e}")

    def test_en_lexicon_tier_is_1(self):
        """AC1: all EN lexicon entries have tier == 1."""
        entries = _load_lexicon(LEXICON_EN)
        for e in entries:
            self.assertEqual(1, e["tier"],
                             f"Non-tier-1 entry found: {e}")

    def test_en_lexicon_type_valid(self):
        """AC1: type must be 'word' or 'phrase' for all EN entries."""
        entries = _load_lexicon(LEXICON_EN)
        for e in entries:
            self.assertIn(e["type"], {"word", "phrase"},
                          f"Invalid type in entry: {e}")

    def test_en_lexicon_covers_expected_patterns(self):
        """AC1: EN lexicon must contain all expected curated pattern IDs."""
        entries = _load_lexicon(LEXICON_EN)
        present_ids = {e["pattern_id"] for e in entries}
        missing = _EN_EXPECTED_IDS - present_ids
        self.assertEqual(set(), missing,
                         f"EN lexicon missing pattern IDs: {missing}")


# ---------------------------------------------------------------------------
# AC2: EN fixture hits EN patterns; DE fixture has no EN hits (and vice versa)
# ---------------------------------------------------------------------------

class TestCrossLanguageSeparation(unittest.TestCase):
    """AC2: EN patterns found in EN text; DE text triggers zero EN hits."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._en_lexicon = _load_lexicon(LEXICON_EN)
        self._de_lexicon = _load_lexicon(LEXICON_DE)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_en_patterns_found_in_en_text(self):
        """AC2: all EN tier-1 expected patterns are found in the EN fixture."""
        path = _write_temp(self._tmpdir.name, _EN_TIER1_TEXT, "en_fixture.md")
        findings = slop_scanner.scan_file(path, self._en_lexicon)
        found_ids = {f["pattern_id"] for f in findings}
        missing = _EN_EXPECTED_IDS - found_ids
        self.assertEqual(set(), missing,
                         f"EN patterns not found: {missing}")

    def test_de_text_triggers_no_en_hits(self):
        """AC2: pure DE text must not trigger any EN lexicon patterns."""
        path = _write_temp(self._tmpdir.name, _DE_TIER1_TEXT, "de_fixture.md")
        findings = slop_scanner.scan_file(path, self._en_lexicon)
        self.assertEqual([], findings,
                         f"EN lexicon should not fire on DE text, got: {findings}")

    def test_en_text_triggers_no_de_hits(self):
        """AC2: pure EN text must not trigger any DE lexicon patterns."""
        path = _write_temp(self._tmpdir.name, _EN_TIER1_TEXT, "en_fixture2.md")
        findings = slop_scanner.scan_file(path, self._de_lexicon)
        self.assertEqual([], findings,
                         f"DE lexicon should not fire on EN text, got: {findings}")

    def test_apostrophe_phrase_matched(self):
        """AC2: phrase with apostrophe (\"it's worth noting\") is matched correctly."""
        path = _write_temp(self._tmpdir.name,
                           "It's worth noting that this matters.\n")
        findings = slop_scanner.scan_file(path, self._en_lexicon)
        ids = {f["pattern_id"] for f in findings}
        self.assertIn("en_worth_noting", ids,
                      "Apostrophe phrase 'it's worth noting' must be matched")

    def test_apostrophe_not_partial(self):
        """AC2: 'it's worth noting' must not match inside a longer token."""
        # Construct text that contains the words but not as the exact phrase
        path = _write_temp(self._tmpdir.name,
                           "It is worth noting that this matters.\n")
        findings = slop_scanner.scan_file(path, self._en_lexicon)
        ids = {f["pattern_id"] for f in findings}
        # "it is worth noting" is NOT the same phrase, so should not match
        self.assertNotIn("en_worth_noting", ids,
                         "'it is worth noting' must not match the apostrophe phrase")


# ---------------------------------------------------------------------------
# AC3: --lang flag forces correct lexicon
# ---------------------------------------------------------------------------

class TestLangFlag(unittest.TestCase):
    """AC3: --lang de / --lang en force the respective lexicon;
    --lang auto picks correctly for clear DE and EN fixtures."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_cli(self, text: str, lang: str, filename: str = "input.md") -> dict:
        """Run the CLI with --lang <lang> and return parsed output dict."""
        path = _write_temp(self._tmpdir.name, text, filename)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable,
             str(SCRIPTS_DIR / "slop_scanner.py"),
             path,
             "--lang", lang,
             "--lexicon-dir", str(LEXICON_DIR)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(0, result.returncode,
                         f"CLI exited non-zero.\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return json.loads(result.stdout)

    def test_lang_de_finds_de_patterns(self):
        """AC3: --lang de with DE text finds DE patterns."""
        out = self._run_cli(_DE_TIER1_TEXT, "de")
        findings = out["findings"]
        found_ids = {f["pattern_id"] for f in findings}
        self.assertTrue(found_ids & _DE_EXPECTED_IDS,
                        "Expected DE pattern IDs in findings")

    def test_lang_en_finds_en_patterns(self):
        """AC3: --lang en with EN text finds EN patterns."""
        out = self._run_cli(_EN_TIER1_TEXT, "en")
        findings = out["findings"]
        found_ids = {f["pattern_id"] for f in findings}
        self.assertTrue(found_ids & _EN_EXPECTED_IDS,
                        "Expected EN pattern IDs in findings")

    def test_lang_de_forced_on_en_text_no_de_hits(self):
        """AC3: --lang de forced on EN text → no DE hits (DE patterns not in EN text)."""
        out = self._run_cli(_EN_TIER1_TEXT, "de")
        findings = out["findings"]
        # EN text has no DE slop words, so findings should be empty
        self.assertEqual([], findings,
                         "DE lexicon should not fire on EN text")

    def test_lang_en_forced_on_de_text_no_en_hits(self):
        """AC3: --lang en forced on DE text → no EN hits (EN patterns not in DE text)."""
        out = self._run_cli(_DE_TIER1_TEXT, "en")
        findings = out["findings"]
        self.assertEqual([], findings,
                         "EN lexicon should not fire on DE text")

    def test_lang_auto_detects_de(self):
        """AC3: --lang auto correctly detects clear DE text."""
        out = self._run_cli(_DE_TIER1_TEXT, "auto")
        self.assertEqual("de", out["language"],
                         "auto should detect DE for umlaut-heavy DE text")
        findings = out["findings"]
        found_ids = {f["pattern_id"] for f in findings}
        self.assertTrue(found_ids & _DE_EXPECTED_IDS,
                        "auto-DE should find DE patterns")

    def test_lang_auto_detects_en(self):
        """AC3: --lang auto correctly detects clear EN text."""
        out = self._run_cli(_EN_TIER1_TEXT, "auto")
        self.assertEqual("en", out["language"],
                         "auto should detect EN for umlaut-free EN text")
        findings = out["findings"]
        found_ids = {f["pattern_id"] for f in findings}
        self.assertTrue(found_ids & _EN_EXPECTED_IDS,
                        "auto-EN should find EN patterns")


# ---------------------------------------------------------------------------
# AC4: detected/chosen language appears in output
# ---------------------------------------------------------------------------

class TestLanguageInOutput(unittest.TestCase):
    """AC4: the detected or chosen language appears in the CLI output."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_cli(self, text: str, lang: str) -> dict:
        path = _write_temp(self._tmpdir.name, text)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable,
             str(SCRIPTS_DIR / "slop_scanner.py"),
             path,
             "--lang", lang,
             "--lexicon-dir", str(LEXICON_DIR)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(0, result.returncode,
                         f"CLI failed.\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return json.loads(result.stdout)

    def test_output_has_language_key(self):
        """AC4: output object has a 'language' key."""
        out = self._run_cli("Some text.\n", "en")
        self.assertIn("language", out,
                      "Output must contain 'language' key")

    def test_output_has_findings_key(self):
        """AC4: output object has a 'findings' key (envelope change)."""
        out = self._run_cli("Some text.\n", "en")
        self.assertIn("findings", out,
                      "Output must contain 'findings' key")

    def test_lang_de_sets_language_de(self):
        """AC4: --lang de → language == 'de' in output."""
        out = self._run_cli(_DE_TIER1_TEXT, "de")
        self.assertEqual("de", out["language"])

    def test_lang_en_sets_language_en(self):
        """AC4: --lang en → language == 'en' in output."""
        out = self._run_cli(_EN_TIER1_TEXT, "en")
        self.assertEqual("en", out["language"])

    def test_lang_auto_output_language_is_de_or_en(self):
        """AC4: --lang auto → language in output is either 'de' or 'en'."""
        out = self._run_cli("Some plain text.\n", "auto")
        self.assertIn(out["language"], {"de", "en"},
                      f"language must be 'de' or 'en', got: {out['language']}")


# ---------------------------------------------------------------------------
# AC5: determinism preserved — sorted, byte-identical for EN
# ---------------------------------------------------------------------------

class TestENDeterminism(unittest.TestCase):
    """AC5: EN findings sorted by (file_path, line_number, pattern_id);
    two runs byte-identical."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._en_path = _write_temp(self._tmpdir.name, _EN_TIER1_TEXT, "en_golden.md")
        self._en_lexicon = _load_lexicon(LEXICON_EN)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_en_findings_sorted(self):
        """AC5: EN findings sorted by (file_path, line_number, pattern_id)."""
        findings = slop_scanner.scan_file(self._en_path, self._en_lexicon)
        keys = [(f["file_path"], f["line_number"], f["pattern_id"]) for f in findings]
        self.assertEqual(sorted(keys), keys,
                         "EN findings must be sorted by (file_path, line_number, pattern_id)")

    def test_en_byte_identical_two_runs(self):
        """AC5: two consecutive EN scan calls produce byte-identical JSON."""
        r1 = slop_scanner.scan_file(self._en_path, self._en_lexicon)
        r2 = slop_scanner.scan_file(self._en_path, self._en_lexicon)
        j1 = json.dumps(r1, ensure_ascii=False, indent=2, sort_keys=False)
        j2 = json.dumps(r2, ensure_ascii=False, indent=2, sort_keys=False)
        self.assertEqual(j1, j2)

    def test_en_findings_canonical_shape(self):
        """AC5: every EN finding has exactly the eight canonical keys."""
        canonical = {
            "file_path", "line_number", "match", "pattern_id",
            "type", "tier", "suggested_replacement", "rationale",
        }
        findings = slop_scanner.scan_file(self._en_path, self._en_lexicon)
        self.assertGreater(len(findings), 0)
        for f in findings:
            self.assertEqual(canonical, set(f.keys()),
                             f"Finding has wrong keys: {set(f.keys())}")

    def test_de_golden_fixture_still_works(self):
        """AC5: DE golden fixture still produces correct findings (slice-01 compat)."""
        de_path = _write_temp(self._tmpdir.name, _DE_TIER1_TEXT, "de_golden.md")
        de_lexicon = _load_lexicon(LEXICON_DE)
        findings = slop_scanner.scan_file(de_path, de_lexicon)
        found_ids = {f["pattern_id"] for f in findings}
        self.assertEqual(_DE_EXPECTED_IDS, found_ids)


if __name__ == "__main__":
    unittest.main(verbosity=2)
