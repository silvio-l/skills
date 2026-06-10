#!/usr/bin/env python3
"""Tests for punctuation + structure tells — humanize-text slice 03.

Observable-behaviour only: tests drive the public API and CLI.
No internal helpers tested directly.

Acceptance criteria covered:
  AC1 — em-dash as type:punctuation finding with correct line_number
  AC2 — tricolon + negative parallelism as type:structure (DE and EN)
  AC3 — structure patterns in a data file, language-neutral
  AC4 — each finding has a non-empty rationale
  AC5 — determinism + golden fixtures (DE and EN)

Run from repo root:
    python3 tests/humanize-text/test_structure_tells.py
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
SKILL_DIR = REPO_ROOT / "skills" / "humanize-text"
STRUCTURE_PATTERNS_PATH = SKILL_DIR / "structure_patterns.json"

sys.path.insert(0, str(SCRIPTS_DIR))

import slop_scanner  # noqa: E402

_CANONICAL_KEYS = {
    "file_path", "line_number", "match", "pattern_id",
    "type", "tier", "suggested_replacement", "rationale",
}


def _write_temp(tmpdir: str, text: str, name: str = "input.md") -> str:
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


# ---------------------------------------------------------------------------
# AC3: structure_patterns.json data-file contract
# ---------------------------------------------------------------------------

class TestStructurePatternsDataFile(unittest.TestCase):
    """AC3: structure_patterns.json exists alongside lexica, has correct shape."""

    def test_file_exists(self):
        """AC3: structure_patterns.json must exist in the skill data dir."""
        self.assertTrue(
            STRUCTURE_PATTERNS_PATH.is_file(),
            f"Missing file: {STRUCTURE_PATTERNS_PATH}",
        )

    def test_file_is_valid_json_list(self):
        """AC3: structure_patterns.json is a valid non-empty JSON list."""
        with open(STRUCTURE_PATTERNS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        self.assertIsInstance(data, list)
        self.assertGreater(len(data), 0)

    def test_required_keys_present(self):
        """AC3: every entry has pattern_id, type, tier, rationale, pattern."""
        with open(STRUCTURE_PATTERNS_PATH, encoding="utf-8") as f:
            entries = json.load(f)
        required = {"pattern_id", "type", "tier", "rationale", "pattern"}
        for e in entries:
            missing = required - set(e.keys())
            self.assertEqual(set(), missing,
                             f"Entry missing keys {missing}: {e}")

    def test_type_values_valid(self):
        """AC3: type must be 'punctuation' or 'structure' for all entries."""
        with open(STRUCTURE_PATTERNS_PATH, encoding="utf-8") as f:
            entries = json.load(f)
        for e in entries:
            self.assertIn(e["type"], {"punctuation", "structure"},
                          f"Invalid type: {e}")

    def test_tier_is_integer(self):
        """AC3: tier must be a positive integer."""
        with open(STRUCTURE_PATTERNS_PATH, encoding="utf-8") as f:
            entries = json.load(f)
        for e in entries:
            self.assertIsInstance(e["tier"], int)
            self.assertGreater(e["tier"], 0,
                               f"tier must be > 0: {e}")

    def test_lang_field_neutral_or_both(self):
        """AC3: each entry has a lang field indicating language-neutrality."""
        with open(STRUCTURE_PATTERNS_PATH, encoding="utf-8") as f:
            entries = json.load(f)
        for e in entries:
            self.assertIn("lang", e,
                          f"Entry missing 'lang' field: {e}")
            self.assertIn(e["lang"], {"neutral", "de", "en"},
                          f"Invalid lang value: {e}")

    def test_em_dash_entry_exists(self):
        """AC3: structure_patterns.json must have at least one punctuation entry for em-dash."""
        with open(STRUCTURE_PATTERNS_PATH, encoding="utf-8") as f:
            entries = json.load(f)
        punct_entries = [e for e in entries if e["type"] == "punctuation"]
        self.assertGreater(len(punct_entries), 0,
                           "Must have at least one punctuation entry (em-dash)")

    def test_tricolon_entry_exists(self):
        """AC3: structure_patterns.json must have a tricolon/rule-of-three entry."""
        with open(STRUCTURE_PATTERNS_PATH, encoding="utf-8") as f:
            entries = json.load(f)
        ids = {e["pattern_id"] for e in entries}
        # At least one entry with 'tricolon' or 'rule_of_three' in the id
        tricolon_ids = {i for i in ids if "tricolon" in i or "rule_of_three" in i}
        self.assertGreater(len(tricolon_ids), 0,
                           f"No tricolon/rule_of_three entry found. IDs present: {ids}")

    def test_negative_parallelism_entry_exists(self):
        """AC3: structure_patterns.json must have a negative-parallelism entry."""
        with open(STRUCTURE_PATTERNS_PATH, encoding="utf-8") as f:
            entries = json.load(f)
        ids = {e["pattern_id"] for e in entries}
        neg_par_ids = {i for i in ids if "neg" in i and "parallel" in i}
        self.assertGreater(len(neg_par_ids), 0,
                           f"No negative_parallelism entry found. IDs present: {ids}")


# ---------------------------------------------------------------------------
# AC1: em-dash detection — type:punctuation, correct line_number
# ---------------------------------------------------------------------------

class TestEmDashDetection(unittest.TestCase):
    """AC1: em-dash detected as type:punctuation with correct line_number."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _scan_with_structure(self, text: str) -> list:
        """Scan text using scan_file_with_structure; returns findings list."""
        path = _write_temp(self._tmpdir.name, text)
        return slop_scanner.scan_file_with_structure(path)

    def test_em_dash_found_on_correct_line(self):
        """AC1: em-dash on line 2 is found with line_number == 2."""
        text = "No em dash here.\nThis sentence — has one — in it.\nAnother line.\n"
        findings = self._scan_with_structure(text)
        punct = [f for f in findings if f["type"] == "punctuation"]
        self.assertGreater(len(punct), 0, "Expected at least one punctuation finding")
        line_numbers = {f["line_number"] for f in punct}
        self.assertIn(2, line_numbers, f"Em-dash on line 2 not detected; got lines: {line_numbers}")

    def test_em_dash_not_found_when_absent(self):
        """AC1: no punctuation finding when text has no em-dash."""
        text = "A normal - hyphen does not trigger the em-dash check.\n"
        findings = self._scan_with_structure(text)
        punct = [f for f in findings if f["type"] == "punctuation"]
        self.assertEqual([], punct, f"No punctuation finding expected; got: {punct}")

    def test_em_dash_finding_has_canonical_keys(self):
        """AC1: em-dash finding has exactly the 8 canonical keys."""
        text = "Wichtig — und zwar wirklich.\n"
        findings = self._scan_with_structure(text)
        punct = [f for f in findings if f["type"] == "punctuation"]
        self.assertGreater(len(punct), 0)
        for f in punct:
            self.assertEqual(_CANONICAL_KEYS, set(f.keys()),
                             f"Wrong keys: {set(f.keys())}")

    def test_em_dash_tier_is_1(self):
        """AC1: em-dash finding has tier == 1."""
        text = "KI schreibt — weil es trainiert wurde.\n"
        findings = self._scan_with_structure(text)
        punct = [f for f in findings if f["type"] == "punctuation"]
        self.assertGreater(len(punct), 0)
        for f in punct:
            self.assertEqual(1, f["tier"])

    def test_em_dash_rationale_non_empty(self):
        """AC4: em-dash finding has a non-empty rationale."""
        text = "Das ist ein Satz — mit Em-Dash.\n"
        findings = self._scan_with_structure(text)
        punct = [f for f in findings if f["type"] == "punctuation"]
        self.assertGreater(len(punct), 0)
        for f in punct:
            self.assertIsInstance(f["rationale"], str)
            self.assertGreater(len(f["rationale"]), 0,
                               "rationale must be non-empty")

    def test_em_dash_multiple_occurrences_per_line(self):
        """AC1: two em-dashes on the same line produce two findings."""
        text = "Es war — sagen wir — anders.\n"
        findings = self._scan_with_structure(text)
        punct = [f for f in findings if f["type"] == "punctuation"]
        self.assertEqual(2, len(punct),
                         f"Expected 2 em-dash findings for line with 2 em-dashes; got {len(punct)}")

    def test_em_dash_match_value_is_em_dash_char(self):
        """AC1: the match field contains exactly the em-dash character."""
        text = "Something — else.\n"
        findings = self._scan_with_structure(text)
        punct = [f for f in findings if f["type"] == "punctuation"]
        self.assertGreater(len(punct), 0)
        for f in punct:
            self.assertEqual("—", f["match"],
                             f"match must be U+2014; got {f['match']!r}")

    def test_em_dash_independent_of_lexicon(self):
        """AC1: text with em-dash but no lexicon slop words still produces punctuation findings."""
        # This text has no words from de or en lexicons
        text = "Ganz normale Wörter — ohne Lexikon-Treffer.\n"
        findings = self._scan_with_structure(text)
        punct = [f for f in findings if f["type"] == "punctuation"]
        self.assertGreater(len(punct), 0,
                           "Em-dash must be detected independently of lexicon")


# ---------------------------------------------------------------------------
# AC2: tricolon detection — type:structure, DE and EN
# ---------------------------------------------------------------------------

class TestTricolonNotSurfaced(unittest.TestCase):
    """AC2/Rework: tricolon/rule-of-three is a weak, tier-3 density hint and must
    NOT surface as an individual structure finding.

    Distinguishing a rhetorical rule-of-three from an ordinary three-item
    enumeration is fundamentally unreliable with regex heuristics. The scanner
    therefore emits ZERO per-occurrence tricolon findings, so ordinary human
    three-item lists are never flagged as a 'problem'. The tell is recorded in
    structure_patterns.json (tier 3) for a future density-based pass.
    """

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _scan_with_structure(self, text: str) -> list:
        path = _write_temp(self._tmpdir.name, text)
        return slop_scanner.scan_file_with_structure(path)

    def _tricolon_findings(self, text: str) -> list:
        return [f for f in self._scan_with_structure(text)
                if "tricolon" in f["pattern_id"]]

    # --- Reviewer's concrete false-positive examples must NOT surface ---

    def test_proper_noun_list_not_flagged(self):
        """Rework: 'Python, JavaScript and TypeScript' is a normal list — no finding."""
        text = "Python, JavaScript and TypeScript are popular.\n"
        self.assertEqual([], self._tricolon_findings(text),
                         "Ordinary proper-noun list must not surface a tricolon finding")

    def test_clause_list_not_flagged(self):
        """Rework: a narrative three-clause sentence is normal — no finding."""
        text = "I read the docs, checked the code and fixed the bug.\n"
        self.assertEqual([], self._tricolon_findings(text),
                         "Narrative three-clause list must not surface a tricolon finding")

    def test_four_item_list_not_flagged(self):
        """Rework: 'speed, quality, reliability and security' (4 items) — no finding."""
        text = "We care about speed, quality, reliability and security.\n"
        self.assertEqual([], self._tricolon_findings(text),
                         "Four-item list must not surface a tricolon finding")

    def test_de_three_item_list_not_flagged(self):
        """Rework: ordinary DE three-item list — no finding."""
        text = "Wir bieten Qualität, Verlässlichkeit und Innovation.\n"
        self.assertEqual([], self._tricolon_findings(text),
                         "Ordinary DE three-item list must not surface a tricolon finding")

    def test_en_three_item_list_not_flagged(self):
        """Rework: ordinary EN three-item list — no finding."""
        text = "We offer quality, reliability and innovation.\n"
        self.assertEqual([], self._tricolon_findings(text),
                         "Ordinary EN three-item list must not surface a tricolon finding")

    def test_no_structure_finding_is_tricolon(self):
        """Rework: across mixed prose, NO structure finding may be a tricolon."""
        text = (
            "Python, JavaScript and TypeScript are popular.\n"
            "We care about speed, quality, reliability and security.\n"
            "I read the docs, checked the code and fixed the bug.\n"
        )
        findings = self._scan_with_structure(text)
        tricolon = [f for f in findings if "tricolon" in f["pattern_id"]]
        self.assertEqual([], tricolon,
                         f"No tricolon finding may be surfaced; got: {tricolon}")


class TestTricolonDataFileEntry(unittest.TestCase):
    """AC3/Rework: the tricolon tell is still documented in the data file as a
    tier-3 (weak, density-only) hint, even though it never surfaces a finding."""

    def test_tricolon_entry_is_tier_3(self):
        """Rework: struct_tricolon entry exists and is tier 3 (weak hint)."""
        with open(STRUCTURE_PATTERNS_PATH, encoding="utf-8") as f:
            entries = json.load(f)
        tricolon = [e for e in entries if "tricolon" in e["pattern_id"]]
        self.assertGreater(len(tricolon), 0,
                           "struct_tricolon entry must remain documented")
        for e in tricolon:
            self.assertEqual(3, e["tier"],
                             "tricolon must be tier 3 (weak density-only hint)")


# ---------------------------------------------------------------------------
# AC2: negative parallelism detection — type:structure, DE and EN
# ---------------------------------------------------------------------------

class TestNegativeParallelismDetection(unittest.TestCase):
    """AC2: negative parallelism detected as type:structure for DE and EN."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _scan_with_structure(self, text: str) -> list:
        path = _write_temp(self._tmpdir.name, text)
        return slop_scanner.scan_file_with_structure(path)

    def test_neg_parallelism_de(self):
        """AC2: DE 'nicht nur ... sondern auch ...' detected."""
        text = "Das ist nicht nur schnell, sondern auch zuverlässig.\n"
        findings = self._scan_with_structure(text)
        struct = [f for f in findings if f["type"] == "structure"
                  and "neg" in f["pattern_id"] and "parallel" in f["pattern_id"]]
        self.assertGreater(len(struct), 0,
                           "DE negative parallelism not detected")

    def test_neg_parallelism_en(self):
        """AC2: EN 'not just ... but ...' detected."""
        text = "This is not just fast, but also reliable.\n"
        findings = self._scan_with_structure(text)
        struct = [f for f in findings if f["type"] == "structure"
                  and "neg" in f["pattern_id"] and "parallel" in f["pattern_id"]]
        self.assertGreater(len(struct), 0,
                           "EN negative parallelism not detected")

    def test_neg_parallelism_en_variant(self):
        """AC2: EN 'not only ... but also ...' variant detected."""
        text = "It is not only fast but also reliable.\n"
        findings = self._scan_with_structure(text)
        struct = [f for f in findings if f["type"] == "structure"
                  and "neg" in f["pattern_id"] and "parallel" in f["pattern_id"]]
        self.assertGreater(len(struct), 0,
                           "EN 'not only ... but also ...' not detected")

    def test_neg_parallelism_canonical_keys(self):
        """AC2: negative parallelism finding has canonical 8 keys."""
        text = "Not just a tool, but a complete solution.\n"
        findings = self._scan_with_structure(text)
        struct = [f for f in findings if f["type"] == "structure"
                  and "neg" in f["pattern_id"] and "parallel" in f["pattern_id"]]
        self.assertGreater(len(struct), 0)
        for f in struct:
            self.assertEqual(_CANONICAL_KEYS, set(f.keys()))

    def test_neg_parallelism_rationale_non_empty(self):
        """AC4: negative parallelism finding has non-empty rationale."""
        text = "Das ist nicht nur schnell, sondern auch zuverlässig.\n"
        findings = self._scan_with_structure(text)
        struct = [f for f in findings if f["type"] == "structure"
                  and "neg" in f["pattern_id"] and "parallel" in f["pattern_id"]]
        self.assertGreater(len(struct), 0)
        for f in struct:
            self.assertGreater(len(f["rationale"]), 0)


# ---------------------------------------------------------------------------
# AC5: Determinism + golden fixtures
# ---------------------------------------------------------------------------

# DE golden fixture: ordinary list (must NOT flag) + negative parallelism + em-dash.
# Line 1 is a plain three-item enumeration kept here precisely to prove it stays
# unflagged in a golden run (no silent tricolon false positive).
_DE_STRUCTURE_TEXT = (
    "Wir bieten Qualität, Verlässlichkeit und Innovation.\n"      # line 1: ordinary list — NO finding
    "Das ist nicht nur schnell, sondern auch zuverlässig.\n"      # line 2: neg parallelism (DE)
    "KI schreibt gern — weil es trainiert wurde — so.\n"          # line 3: em-dash x2
)

# EN golden fixture: ordinary list (must NOT flag) + negative parallelism + em-dash.
# Line 2 is now a PURE negative-parallelism example (no trailing 'and' list), so
# there is no silent tricolon false positive to assert against.
_EN_STRUCTURE_TEXT = (
    "We offer quality, reliability and innovation.\n"             # line 1: ordinary list — NO finding
    "This is not just fast, but also reliable.\n"                 # line 2: neg parallelism (EN) only
    "The answer — if you look closely — is obvious.\n"            # line 3: em-dash x2
)


class TestStructureGoldenFixtures(unittest.TestCase):
    """AC5: golden fixtures for DE and EN structure/punctuation tells."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _scan(self, text: str) -> list:
        path = _write_temp(self._tmpdir.name, text)
        return slop_scanner.scan_file_with_structure(path)

    def test_de_golden_all_tell_types_present(self):
        """AC5 DE: golden fixture produces punctuation and structure findings."""
        findings = self._scan(_DE_STRUCTURE_TEXT)
        types = {f["type"] for f in findings}
        self.assertIn("punctuation", types,
                      "DE golden: expected punctuation findings")
        self.assertIn("structure", types,
                      "DE golden: expected structure findings")

    def test_de_golden_em_dash_on_line3(self):
        """AC5 DE: em-dash on line 3 detected with correct line_number."""
        findings = self._scan(_DE_STRUCTURE_TEXT)
        punct_lines = {f["line_number"] for f in findings if f["type"] == "punctuation"}
        self.assertIn(3, punct_lines,
                      f"Em-dash on line 3 not detected; punct lines: {punct_lines}")

    def test_de_golden_ordinary_list_line1_not_flagged(self):
        """AC5/Rework DE: the ordinary three-item list on line 1 must NOT surface a finding."""
        findings = self._scan(_DE_STRUCTURE_TEXT)
        line1 = [f for f in findings if f["line_number"] == 1]
        self.assertEqual([], line1,
                         f"Ordinary DE list on line 1 must not be flagged; got: {line1}")

    def test_de_golden_neg_parallelism_on_line2(self):
        """AC5 DE: negative parallelism on line 2 detected."""
        findings = self._scan(_DE_STRUCTURE_TEXT)
        neg_par = [f for f in findings
                   if "neg" in f["pattern_id"] and "parallel" in f["pattern_id"]
                   and f["line_number"] == 2]
        self.assertGreater(len(neg_par), 0,
                           "DE negative parallelism on line 2 not detected")

    def test_en_golden_all_tell_types_present(self):
        """AC5 EN: golden fixture produces punctuation and structure findings."""
        findings = self._scan(_EN_STRUCTURE_TEXT)
        types = {f["type"] for f in findings}
        self.assertIn("punctuation", types,
                      "EN golden: expected punctuation findings")
        self.assertIn("structure", types,
                      "EN golden: expected structure findings")

    def test_en_golden_em_dash_on_line3(self):
        """AC5 EN: em-dash on line 3 detected with correct line_number."""
        findings = self._scan(_EN_STRUCTURE_TEXT)
        punct_lines = {f["line_number"] for f in findings if f["type"] == "punctuation"}
        self.assertIn(3, punct_lines,
                      f"EN em-dash on line 3 not detected; punct lines: {punct_lines}")

    def test_en_golden_ordinary_list_line1_not_flagged(self):
        """AC5/Rework EN: the ordinary three-item list on line 1 must NOT surface a finding."""
        findings = self._scan(_EN_STRUCTURE_TEXT)
        line1 = [f for f in findings if f["line_number"] == 1]
        self.assertEqual([], line1,
                         f"Ordinary EN list on line 1 must not be flagged; got: {line1}")

    def test_en_golden_neg_parallelism_on_line2(self):
        """AC5 EN: negative parallelism on line 2 detected."""
        findings = self._scan(_EN_STRUCTURE_TEXT)
        neg_par = [f for f in findings
                   if "neg" in f["pattern_id"] and "parallel" in f["pattern_id"]
                   and f["line_number"] == 2]
        self.assertGreater(len(neg_par), 0,
                           "EN negative parallelism on line 2 not detected")

    def test_determinism_de(self):
        """AC5: two DE scans produce byte-identical output."""
        path = _write_temp(self._tmpdir.name, _DE_STRUCTURE_TEXT, "det_de.md")
        r1 = slop_scanner.scan_file_with_structure(path)
        r2 = slop_scanner.scan_file_with_structure(path)
        j1 = json.dumps(r1, ensure_ascii=False, indent=2, sort_keys=False)
        j2 = json.dumps(r2, ensure_ascii=False, indent=2, sort_keys=False)
        self.assertEqual(j1, j2)

    def test_determinism_en(self):
        """AC5: two EN scans produce byte-identical output."""
        path = _write_temp(self._tmpdir.name, _EN_STRUCTURE_TEXT, "det_en.md")
        r1 = slop_scanner.scan_file_with_structure(path)
        r2 = slop_scanner.scan_file_with_structure(path)
        j1 = json.dumps(r1, ensure_ascii=False, indent=2, sort_keys=False)
        j2 = json.dumps(r2, ensure_ascii=False, indent=2, sort_keys=False)
        self.assertEqual(j1, j2)

    def test_sorted_by_file_line_pattern_id(self):
        """AC5: structure+punctuation findings sorted by (file_path, line_number, pattern_id)."""
        path = _write_temp(self._tmpdir.name, _DE_STRUCTURE_TEXT + _EN_STRUCTURE_TEXT,
                           "sort_check.md")
        findings = slop_scanner.scan_file_with_structure(path)
        keys = [(f["file_path"], f["line_number"], f["pattern_id"]) for f in findings]
        self.assertEqual(sorted(keys), keys,
                         "Findings not sorted by (file_path, line_number, pattern_id)")

    def test_all_findings_have_non_empty_rationale(self):
        """AC4: all structure/punctuation findings have non-empty rationale."""
        findings = self._scan(_DE_STRUCTURE_TEXT + _EN_STRUCTURE_TEXT)
        for f in findings:
            self.assertIsInstance(f["rationale"], str)
            self.assertGreater(len(f["rationale"]), 0,
                               f"Empty rationale in finding: {f}")


# ---------------------------------------------------------------------------
# Integration: structure tells merge into scan_file_with_language output
# ---------------------------------------------------------------------------

class TestStructureIntegrationWithLanguageEnvelope(unittest.TestCase):
    """Structure/punctuation findings merge into the slice-02 envelope."""

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
             "--lexicon-dir", str(SKILL_DIR)],
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(0, result.returncode,
                         f"CLI failed.\nstdout: {result.stdout}\nstderr: {result.stderr}")
        return json.loads(result.stdout)

    def test_em_dash_in_cli_output_de(self):
        """Integration: em-dash appears in CLI envelope findings for DE text."""
        text = "Das ist ein Satz — mit Em-Dash.\n"
        out = self._run_cli(text, "de")
        self.assertIn("findings", out)
        punct = [f for f in out["findings"] if f["type"] == "punctuation"]
        self.assertGreater(len(punct), 0,
                           "Em-dash finding not in CLI envelope for DE")

    def test_em_dash_in_cli_output_en(self):
        """Integration: em-dash appears in CLI envelope findings for EN text."""
        text = "This is a sentence — with an em dash.\n"
        out = self._run_cli(text, "en")
        self.assertIn("findings", out)
        punct = [f for f in out["findings"] if f["type"] == "punctuation"]
        self.assertGreater(len(punct), 0,
                           "Em-dash finding not in CLI envelope for EN")

    def test_structure_findings_in_cli_envelope_de(self):
        """Integration: structure findings appear in CLI envelope for DE."""
        text = "Das ist nicht nur schnell, sondern auch zuverlässig.\n"
        out = self._run_cli(text, "de")
        struct = [f for f in out["findings"] if f["type"] == "structure"]
        self.assertGreater(len(struct), 0,
                           "Structure finding not in CLI envelope for DE")

    def test_mixed_findings_sorted_in_envelope(self):
        """Integration: mixed word+structure findings are sorted in the envelope."""
        # DE text: has a lexicon word AND em-dash AND structure
        text = (
            "Zudem ist das wichtig — wirklich.\n"
            "Wir bieten Qualität, Verlässlichkeit und Innovation.\n"
        )
        out = self._run_cli(text, "de")
        findings = out["findings"]
        keys = [(f["file_path"], f["line_number"], f["pattern_id"]) for f in findings]
        self.assertEqual(sorted(keys), keys,
                         "Mixed findings not sorted in CLI envelope")


if __name__ == "__main__":
    unittest.main(verbosity=2)
