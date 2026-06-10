#!/usr/bin/env python3
"""Golden-fixture tests for humanize-text/scripts/slop_scanner.py.

Tests assert observable behaviour only (input file → JSON findings).
No internal helper functions are tested directly.

Run from the repo root:
    python3 tests/humanize-text/test_slop_scanner.py
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
LEXICON_PATH = REPO_ROOT / "skills" / "humanize-text" / "lexicon.de.json"
sys.path.insert(0, str(SCRIPTS_DIR))

import slop_scanner  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def load_lexicon() -> list:
    with open(LEXICON_PATH, encoding="utf-8") as f:
        return json.load(f)


def write_tempfile(text: str, suffix: str = ".md") -> str:
    """Write *text* to a named temp file and return its path.

    Caller is responsible for deleting it (use as context manager or
    explicitly unlink). Here we return the path; callers use a
    TemporaryDirectory so cleanup is automatic.
    """
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
    except Exception:
        os.close(fd)
        raise
    return path


# ---------------------------------------------------------------------------
# AC2 + AC5: Golden fixture — all five DE tier-1 patterns, canonical shape
# ---------------------------------------------------------------------------

# Inline fixture: one sentence per tier-1 pattern, each on its own line,
# deliberately placed so that pattern_id sort order differs from line order
# (line 1 = de_zudem, line 2 = de_darueber_hinaus, ...). Two occurrences of
# de_zudem appear on line 5 to exercise multi-match-per-line (AC3).
_DE_TIER1_TEXT = (
    "Zudem ist das ein wichtiger Punkt.\n"                              # line 1: de_zudem
    "Darüber hinaus gibt es weitere Aspekte.\n"                        # line 2: de_darueber_hinaus
    "Es ist wichtig zu beachten, dass wir aufpassen.\n"                # line 3: de_wichtig_zu_beachten
    "Im Hinblick auf die Zukunft müssen wir handeln.\n"                # line 4: de_im_hinblick_auf
    "In der heutigen Welt ist alles vernetzt.\n"                       # line 5: de_heutigen_welt
)

_EXPECTED_PATTERN_IDS = {
    "de_zudem",
    "de_darueber_hinaus",
    "de_wichtig_zu_beachten",
    "de_im_hinblick_auf",
    "de_heutigen_welt",
}

_CANONICAL_KEYS = {
    "file_path", "line_number", "match", "pattern_id",
    "type", "tier", "suggested_replacement", "rationale",
}


class TestDE_Tier1_GoldenFixture(unittest.TestCase):
    """AC2 + AC5: golden-fixture test (input → expected findings)."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._input_path = os.path.join(self._tmpdir.name, "de_tier1.md")
        with open(self._input_path, "w", encoding="utf-8") as f:
            f.write(_DE_TIER1_TEXT)
        self._lexicon = load_lexicon()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_all_five_patterns_found(self):
        """AC2: scanner finds at least one match for each of the five DE tier-1 patterns."""
        findings = slop_scanner.scan_file(self._input_path, self._lexicon)
        found_ids = {f["pattern_id"] for f in findings}
        missing = _EXPECTED_PATTERN_IDS - found_ids
        self.assertEqual(set(), missing, f"Missing patterns: {missing}")

    def test_canonical_finding_shape(self):
        """AC2: every finding has exactly the eight canonical keys."""
        findings = slop_scanner.scan_file(self._input_path, self._lexicon)
        self.assertTrue(len(findings) > 0, "Expected at least one finding")
        for f in findings:
            self.assertEqual(_CANONICAL_KEYS, set(f.keys()),
                             f"Finding has wrong keys: {set(f.keys())}")

    def test_file_path_matches_input(self):
        """AC2: file_path in every finding equals the scanned file path."""
        findings = slop_scanner.scan_file(self._input_path, self._lexicon)
        for f in findings:
            self.assertEqual(self._input_path, f["file_path"])

    def test_tier_is_integer_1(self):
        """AC2: tier field is integer 1 for all DE tier-1 lexicon entries."""
        findings = slop_scanner.scan_file(self._input_path, self._lexicon)
        for f in findings:
            self.assertIsInstance(f["tier"], int)
            self.assertEqual(1, f["tier"])

    def test_line_numbers_are_correct(self):
        """AC5: each pattern is found on the expected line."""
        findings = slop_scanner.scan_file(self._input_path, self._lexicon)
        by_id = {f["pattern_id"]: f["line_number"] for f in findings}
        self.assertEqual(1, by_id["de_zudem"])
        self.assertEqual(2, by_id["de_darueber_hinaus"])
        self.assertEqual(3, by_id["de_wichtig_zu_beachten"])
        self.assertEqual(4, by_id["de_im_hinblick_auf"])
        self.assertEqual(5, by_id["de_heutigen_welt"])


# ---------------------------------------------------------------------------
# AC3: word-boundary + case-insensitive; multi-match per line
# ---------------------------------------------------------------------------

class TestWordBoundaryAndCaseInsensitive(unittest.TestCase):
    """AC3: word-boundary, case-insensitive, multi-match."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._lexicon = load_lexicon()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _scan_text(self, text: str) -> list:
        path = os.path.join(self._tmpdir.name, "input.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        return slop_scanner.scan_file(path, self._lexicon)

    def test_no_partial_word_match(self):
        """AC3: 'Zudem' must NOT match inside a longer token like 'Zudemfall'."""
        findings = self._scan_text("Zudemfall ist kein Treffer.\n")
        ids = [f["pattern_id"] for f in findings]
        self.assertNotIn("de_zudem", ids,
                         "'Zudem' must not match inside 'Zudemfall'")

    def test_case_insensitive_lowercase(self):
        """AC3: lowercase 'zudem' is matched (case-insensitive)."""
        findings = self._scan_text("zudem ist es so.\n")
        ids = [f["pattern_id"] for f in findings]
        self.assertIn("de_zudem", ids)

    def test_case_insensitive_uppercase(self):
        """AC3: ALL-CAPS 'ZUDEM' is matched (case-insensitive)."""
        findings = self._scan_text("ZUDEM sei es wie es sei.\n")
        ids = [f["pattern_id"] for f in findings]
        self.assertIn("de_zudem", ids)

    def test_multi_match_same_line_same_pattern(self):
        """AC3: two occurrences of the same pattern on one line → two findings, same line_number."""
        findings = self._scan_text("Zudem und nochmals Zudem.\n")
        zudem = [f for f in findings if f["pattern_id"] == "de_zudem"]
        self.assertEqual(2, len(zudem))
        self.assertEqual(zudem[0]["line_number"], zudem[1]["line_number"])

    def test_multi_match_same_line_different_patterns(self):
        """AC3: two different patterns on one line → two findings, same line_number."""
        findings = self._scan_text("Zudem, darüber hinaus noch mehr.\n")
        ids = {f["pattern_id"] for f in findings}
        self.assertIn("de_zudem", ids)
        self.assertIn("de_darueber_hinaus", ids)
        line_numbers = {f["line_number"] for f in findings}
        self.assertEqual(1, len(line_numbers),
                         "Both findings must share the same line_number")

    def test_phrase_matched_across_spaces(self):
        """AC3: multi-word phrase 'Im Hinblick auf' matched at natural word boundary."""
        findings = self._scan_text("Im Hinblick auf die Zukunft.\n")
        ids = [f["pattern_id"] for f in findings]
        self.assertIn("de_im_hinblick_auf", ids)

    def test_phrase_not_matched_as_substring_of_longer_phrase(self):
        """AC3: 'Zudem' at the start of a compounded German word must not match."""
        # Constructed token that starts with 'Zudem' but has no word break after.
        findings = self._scan_text("Zudemstrategien sind ein Konzept.\n")
        ids = [f["pattern_id"] for f in findings]
        self.assertNotIn("de_zudem", ids)


# ---------------------------------------------------------------------------
# AC4: deterministic sort; byte-identical two runs
# ---------------------------------------------------------------------------

class TestDeterministicSort(unittest.TestCase):
    """AC4: sorted by (file_path, line_number, pattern_id); byte-identical runs."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._input_path = os.path.join(self._tmpdir.name, "de_tier1.md")
        with open(self._input_path, "w", encoding="utf-8") as f:
            f.write(_DE_TIER1_TEXT)
        self._lexicon = load_lexicon()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_sorted_by_file_line_pattern_id(self):
        """AC4: findings sorted by (file_path, line_number, pattern_id)."""
        findings = slop_scanner.scan_file(self._input_path, self._lexicon)
        keys = [(f["file_path"], f["line_number"], f["pattern_id"]) for f in findings]
        self.assertEqual(sorted(keys), keys,
                         "Findings must be sorted by (file_path, line_number, pattern_id)")

    def test_byte_identical_two_runs(self):
        """AC4: two consecutive calls produce byte-identical JSON."""
        findings1 = slop_scanner.scan_file(self._input_path, self._lexicon)
        findings2 = slop_scanner.scan_file(self._input_path, self._lexicon)
        j1 = json.dumps(findings1, ensure_ascii=False, indent=2, sort_keys=False)
        j2 = json.dumps(findings2, ensure_ascii=False, indent=2, sort_keys=False)
        self.assertEqual(j1, j2)

    def test_empty_file_returns_empty_list(self):
        """Edge case: empty input file → empty findings list."""
        path = os.path.join(self._tmpdir.name, "empty.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("")
        findings = slop_scanner.scan_file(path, self._lexicon)
        self.assertEqual([], findings)

    def test_empty_lexicon_returns_empty_list(self):
        """Edge case: empty lexicon → no findings regardless of content."""
        findings = slop_scanner.scan_file(self._input_path, [])
        self.assertEqual([], findings)


# ---------------------------------------------------------------------------
# AC1 + AC6: CLI entry point; stdlib only / offline
# ---------------------------------------------------------------------------

class TestCLI(unittest.TestCase):
    """AC1 + AC6: standalone CLI + offline/stdlib-only."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._input_path = os.path.join(self._tmpdir.name, "de_tier1.md")
        with open(self._input_path, "w", encoding="utf-8") as f:
            f.write(_DE_TIER1_TEXT)

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_cli_returns_valid_json_array(self):
        """AC1: CLI exits 0 and prints a non-empty JSON array."""
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable,
             str(SCRIPTS_DIR / "slop_scanner.py"),
             self._input_path,
             str(LEXICON_PATH)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(0, result.returncode,
                         f"CLI failed with stderr:\n{result.stderr}")
        data = json.loads(result.stdout)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_cli_findings_have_canonical_shape(self):
        """AC1: every finding from CLI output has the canonical 8-key shape."""
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(
            [sys.executable,
             str(SCRIPTS_DIR / "slop_scanner.py"),
             self._input_path,
             str(LEXICON_PATH)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(0, result.returncode)
        findings = json.loads(result.stdout)
        for f in findings:
            self.assertEqual(_CANONICAL_KEYS, set(f.keys()))

    def test_cli_no_third_party_imports(self):
        """AC6: slop_scanner.py imports only stdlib modules."""
        import ast
        scanner_src = SCRIPTS_DIR / "slop_scanner.py"
        with open(scanner_src, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        third_party = {
            "requests", "httpx", "urllib3", "aiohttp", "numpy",
            "pandas", "pytest", "flask", "django",
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    top = (name or "").split(".")[0]
                    self.assertNotIn(
                        top, third_party,
                        f"Third-party import '{top}' found in slop_scanner.py",
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
