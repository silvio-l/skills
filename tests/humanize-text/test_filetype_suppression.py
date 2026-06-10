#!/usr/bin/env python3
"""Tests for filetype strip strategies and suppression markers — slice 04.

Acceptance criteria (all must be covered):
  AC1 — filetype detection: .md/.astro/.ts/.html → correct strip strategy
  AC2 — HTML/Astro: <script>/<style> blocks blanked, line numbers stable
  AC3 — .ts/.astro: summary { de, en } string values extracted as scannable text
  AC4 — section suppression (humanize:ignore) + per-file suppression +
         missing close marker suppresses to EOF
  AC5 — suppression syntax does NOT collide with seo-audit markers
  AC6 — determinism + golden fixtures per file type and for suppression cases

Observable-behaviour only; no internal helpers tested directly.

Run from repo root:
    python3 tests/humanize-text/test_filetype_suppression.py
    python3 -m unittest discover -s tests/humanize-text -t . -p 'test_*.py'
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
SKILL_DIR = REPO_ROOT / "skills" / "humanize-text"

sys.path.insert(0, str(SCRIPTS_DIR))

import slop_scanner  # noqa: E402

_CANONICAL_KEYS = {
    "file_path", "line_number", "match", "pattern_id",
    "type", "tier", "suggested_replacement", "rationale",
}


def _write_temp(tmpdir: str, text: str, name: str) -> str:
    path = os.path.join(tmpdir, name)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def _load_lexicon(lang: str = "en") -> list:
    p = SKILL_DIR / f"lexicon.{lang}.json"
    with open(p, encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# AC1: filetype detection — prep_lines_for_scanning returns correct lines
# ---------------------------------------------------------------------------

class TestFiletypeDetection(unittest.TestCase):
    """AC1: each supported extension maps to the correct strip strategy."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._lexicon_en = _load_lexicon("en")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_md_file_scanned_as_plain_text(self):
        """AC1: .md file — tags NOT stripped, content treated as plain text."""
        # A slop word embedded in a tag attr: only the text node matters.
        # With .md extension no tag stripping happens, so the slop word in
        # visible text IS still found.
        text = "We should leverage this approach.\n"
        path = _write_temp(self._tmpdir.name, text, "doc.md")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        ids = {f["pattern_id"] for f in result["findings"]}
        self.assertIn("en_leverage", ids,
                      ".md file: 'leverage' should be found in plain text")

    def test_html_file_strips_script_style(self):
        """AC1: .html file uses HTML strip strategy (script/style blanked)."""
        text = (
            "<html>\n"
            "<script>\nvar leverage = 1;\n</script>\n"  # 'leverage' inside script — must NOT fire
            "<body>\nWe should leverage this.\n</body>\n"  # 'leverage' in body — MUST fire
            "</html>\n"
        )
        path = _write_temp(self._tmpdir.name, text, "page.html")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        findings = result["findings"]
        # Only body finding on line 6, NOT script finding on line 3
        leverage_lines = [f["line_number"] for f in findings
                          if f["pattern_id"] == "en_leverage"]
        self.assertIn(6, leverage_lines, "leverage in body should be found on line 6")
        self.assertNotIn(3, leverage_lines, "leverage in <script> must NOT be found on line 3")

    def test_astro_file_strips_script_style(self):
        """AC1: .astro file also uses HTML strip strategy."""
        text = (
            "---\nconst leverage = true;\n---\n"    # frontmatter — not HTML tags
            "<style>\n.leverage { color: red; }\n</style>\n"  # style block — must NOT fire
            "<p>We should leverage this.</p>\n"  # body — MUST fire (line 8)
        )
        path = _write_temp(self._tmpdir.name, text, "page.astro")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        leverage_lines = [f["line_number"] for f in result["findings"]
                          if f["pattern_id"] == "en_leverage"]
        # The <p> line is line 8
        self.assertGreater(len(leverage_lines), 0,
                           "leverage in <p> body must be found in .astro file")
        self.assertNotIn(5, leverage_lines,
                         "leverage in CSS selector in .astro <style> must NOT fire")

    def test_ts_file_extracts_summary_fields(self):
        """AC1/.astro+ts: summary { de, en } fields are extracted as text."""
        # The slop word 'delve' in a summary.en field should be found;
        # 'delve' in a variable name comment/code outside summary should not fire
        # because .ts strips everything except summary values.
        text = (
            "export const project = {\n"
            "  name: 'MyProject',\n"
            "  summary: {\n"
            "    de: 'Tolles Werkzeug für den Alltag.',\n"
            "    en: 'A tool to delve into the problem.',\n"
            "  },\n"
            "};\n"
        )
        path = _write_temp(self._tmpdir.name, text, "project.ts")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        ids = {f["pattern_id"] for f in result["findings"]}
        self.assertIn("en_delve", ids,
                      ".ts file: 'delve' in summary.en should be found")

    def test_ts_file_code_outside_summary_not_scanned(self):
        """AC1: .ts file — code tokens outside summary { } are not scanned as prose."""
        # 'leverage' appears as a variable name outside summary — should NOT fire
        text = (
            "const leverage = (x: number) => x * 2;\n"
            "export const project = {\n"
            "  summary: {\n"
            "    de: 'Normaler Text.',\n"
            "    en: 'Normal text content.',\n"
            "  },\n"
            "};\n"
        )
        path = _write_temp(self._tmpdir.name, text, "code.ts")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        ids = {f["pattern_id"] for f in result["findings"]}
        self.assertNotIn("en_leverage", ids,
                         ".ts file: variable name 'leverage' outside summary must not fire")


# ---------------------------------------------------------------------------
# AC2: HTML/Astro — <script>/<style> blanked, line numbers stay stable
# ---------------------------------------------------------------------------

class TestHTMLScriptStyleBlanking(unittest.TestCase):
    """AC2: <script>/<style> content blanked to empty lines; line numbers correct."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self._lexicon_en = _load_lexicon("en")

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_script_block_blanked_line_count_preserved(self):
        """AC2: a slop word inside <script> produces no finding; body finding has correct lineno."""
        # Line layout:
        # 1: <html>
        # 2: <script>
        # 3: var leverage = "delve";
        # 4: </script>
        # 5: <body>
        # 6: We should leverage this.
        # 7: </body>
        # 8: </html>
        text = (
            "<html>\n"
            "<script>\n"
            'var leverage = "delve";\n'
            "</script>\n"
            "<body>\n"
            "We should leverage this.\n"
            "</body>\n"
            "</html>\n"
        )
        path = _write_temp(self._tmpdir.name, text, "test.html")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        leverage_findings = [f for f in result["findings"]
                             if f["pattern_id"] == "en_leverage"]
        delve_findings = [f for f in result["findings"]
                          if f["pattern_id"] == "en_delve"]
        # 'delve' in script must not fire
        self.assertEqual([], delve_findings,
                         "delve inside <script> must not produce a finding")
        # 'leverage' in body must fire, and on the CORRECT line (6)
        self.assertGreater(len(leverage_findings), 0,
                           "leverage in body must fire")
        self.assertIn(6, [f["line_number"] for f in leverage_findings],
                      "leverage in body must be found on line 6")

    def test_style_block_blanked_no_finding_inside(self):
        """AC2: CSS class names inside <style> do not produce findings."""
        text = (
            "<html>\n"
            "<style>\n"
            ".leverage { font-weight: bold; }\n"
            "</style>\n"
            "<body>Plain text.</body>\n"
            "</html>\n"
        )
        path = _write_temp(self._tmpdir.name, text, "style_test.html")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        leverage = [f for f in result["findings"] if f["pattern_id"] == "en_leverage"]
        self.assertEqual([], leverage,
                         "CSS class name in <style> must not produce a finding")

    def test_multiline_script_blanked_preserves_line_count(self):
        """AC2: multi-line <script> blanked to empty lines keeps line numbers stable."""
        # Script spans lines 2-5; slop word on line 7 must be found as line 7.
        text = (
            "<html>\n"
            "<script>\n"
            "function foo() {\n"
            "  return 1;\n"
            "}\n"
            "</script>\n"
            "<p>We should leverage this.</p>\n"
            "</html>\n"
        )
        path = _write_temp(self._tmpdir.name, text, "multi_script.html")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        leverage = [f for f in result["findings"] if f["pattern_id"] == "en_leverage"]
        self.assertGreater(len(leverage), 0, "leverage in <p> should be found")
        self.assertIn(7, [f["line_number"] for f in leverage],
                      f"leverage on line 7; got lines {[f['line_number'] for f in leverage]}")

    def test_findings_have_canonical_shape_html(self):
        """AC2: findings from .html file have the 8 canonical keys."""
        text = "<p>We should leverage this tool.</p>\n"
        path = _write_temp(self._tmpdir.name, text, "shape.html")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        for f in result["findings"]:
            self.assertEqual(_CANONICAL_KEYS, set(f.keys()))


# ---------------------------------------------------------------------------
# AC3: .ts/.astro — summary { de, en } extraction
# ---------------------------------------------------------------------------

class TestSummaryExtraction(unittest.TestCase):
    """AC3: summary { de, en } string values in .ts/.astro are scanned as text."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_ts_summary_de_field_scanned(self):
        """AC3: slop word in summary.de is found when scanning .ts with lang=de."""
        text = (
            "export const item = {\n"
            "  summary: {\n"
            "    de: 'Zudem ist das ein wichtiger Aspekt.',\n"
            "    en: 'Normal text here.',\n"
            "  },\n"
            "};\n"
        )
        path = _write_temp(self._tmpdir.name, text, "item.ts")
        result = slop_scanner.scan_file_with_language(path, "de", str(SKILL_DIR))
        ids = {f["pattern_id"] for f in result["findings"]}
        self.assertIn("de_zudem", ids,
                      "DE slop word in summary.de must be found in .ts file")

    def test_ts_summary_en_field_scanned(self):
        """AC3: slop word in summary.en is found when scanning .ts with lang=en."""
        text = (
            "export const item = {\n"
            "  summary: {\n"
            "    de: 'Normaler Text.',\n"
            "    en: 'You should leverage this approach.',\n"
            "  },\n"
            "};\n"
        )
        path = _write_temp(self._tmpdir.name, text, "item.ts")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        ids = {f["pattern_id"] for f in result["findings"]}
        self.assertIn("en_leverage", ids,
                      "EN slop word in summary.en must be found in .ts file")

    def test_astro_summary_field_scanned(self):
        """AC3: slop word in summary.en inside a .astro file's frontmatter is found."""
        text = (
            "---\n"
            "export const item = {\n"
            "  summary: {\n"
            "    de: 'Normaler Text.',\n"
            "    en: 'A chance to delve into this.',\n"
            "  },\n"
            "};\n"
            "---\n"
            "<p>Hello world.</p>\n"
        )
        path = _write_temp(self._tmpdir.name, text, "comp.astro")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        ids = {f["pattern_id"] for f in result["findings"]}
        self.assertIn("en_delve", ids,
                      "EN slop word in summary.en in .astro must be found")

    def test_ts_no_summary_no_findings_from_code(self):
        """AC3: .ts file with no summary block yields no word findings from raw code."""
        text = (
            "export function leverage(x: number): number {\n"
            "  return x * 2;\n"
            "}\n"
        )
        path = _write_temp(self._tmpdir.name, text, "nosummary.ts")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        word_findings = [f for f in result["findings"]
                         if f["type"] in ("word", "phrase")]
        self.assertEqual([], word_findings,
                         ".ts with no summary: code tokens must not produce word findings")

    def test_ts_summary_line_number_is_correct(self):
        """AC3: line_number in finding refers to the summary field line in the .ts file."""
        text = (
            "export const x = {\n"       # line 1
            "  summary: {\n"             # line 2
            "    de: 'Normaler Text.',\n"  # line 3
            "    en: 'You should leverage this.',\n"  # line 4
            "  },\n"                     # line 5
            "};\n"                       # line 6
        )
        path = _write_temp(self._tmpdir.name, text, "lineno.ts")
        result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        leverage = [f for f in result["findings"] if f["pattern_id"] == "en_leverage"]
        self.assertGreater(len(leverage), 0)
        self.assertEqual(4, leverage[0]["line_number"],
                         "summary.en 'leverage' should be on line 4")


# ---------------------------------------------------------------------------
# AC4: suppression markers — section and per-file
# ---------------------------------------------------------------------------

class TestSuppressionMarkers(unittest.TestCase):
    """AC4: humanize:ignore section suppression + per-file suppression + EOF fallback."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _scan(self, text: str, suffix: str = ".md", lang: str = "en") -> list:
        path = _write_temp(self._tmpdir.name, text, f"test{suffix}")
        result = slop_scanner.scan_file_with_language(path, lang, str(SKILL_DIR))
        return result["findings"]

    def test_section_suppression_ignores_block(self):
        """AC4: lines between <!-- humanize:ignore --> and <!-- /humanize:ignore --> suppressed."""
        text = (
            "Normal line with leverage.\n"                      # line 1 — MUST fire
            "<!-- humanize:ignore -->\n"                        # line 2
            "Suppressed leverage line.\n"                       # line 3 — must NOT fire
            "<!-- /humanize:ignore -->\n"                       # line 4
            "Another leverage line.\n"                          # line 5 — MUST fire
        )
        findings = self._scan(text)
        leverage_lines = [f["line_number"] for f in findings
                          if f["pattern_id"] == "en_leverage"]
        self.assertIn(1, leverage_lines, "line 1 leverage must fire")
        self.assertNotIn(3, leverage_lines, "line 3 leverage inside suppress block must not fire")
        self.assertIn(5, leverage_lines, "line 5 leverage after end-suppress must fire")

    def test_missing_close_marker_suppresses_to_eof(self):
        """AC4: opening marker without closing marker suppresses to end of file."""
        text = (
            "Normal leverage line.\n"                          # line 1 — MUST fire
            "<!-- humanize:ignore -->\n"                       # line 2
            "Suppressed leverage here.\n"                      # line 3 — must NOT fire
            "Also leverage here.\n"                            # line 4 — must NOT fire
        )
        findings = self._scan(text)
        leverage_lines = [f["line_number"] for f in findings
                          if f["pattern_id"] == "en_leverage"]
        self.assertIn(1, leverage_lines, "line 1 must fire before suppression")
        self.assertNotIn(3, leverage_lines, "line 3 must be suppressed (no closing marker)")
        self.assertNotIn(4, leverage_lines, "line 4 must be suppressed (no closing marker)")

    def test_per_file_suppression_skips_whole_file(self):
        """AC4: <!-- humanize:ignore-file --> anywhere in the file skips the whole file."""
        text = (
            "We should leverage this tool.\n"
            "<!-- humanize:ignore-file -->\n"
            "Another leverage line.\n"
        )
        findings = self._scan(text)
        self.assertEqual([], findings,
                         "Per-file marker should suppress all findings in the file")

    def test_per_file_suppression_in_frontmatter(self):
        """AC4: per-file marker in first line still skips whole file."""
        text = (
            "<!-- humanize:ignore-file -->\n"
            "We should leverage this.\n"
        )
        findings = self._scan(text)
        self.assertEqual([], findings,
                         "Per-file marker at start must suppress all findings")

    def test_no_suppression_outside_block(self):
        """AC4: lines outside suppression blocks are still scanned normally."""
        text = (
            "<!-- humanize:ignore -->\n"
            "Inside ignore block — leverage here.\n"
            "<!-- /humanize:ignore -->\n"
            "Leverage outside block.\n"
        )
        findings = self._scan(text)
        leverage_lines = [f["line_number"] for f in findings
                          if f["pattern_id"] == "en_leverage"]
        self.assertNotIn(2, leverage_lines, "leverage inside block must not fire")
        self.assertIn(4, leverage_lines, "leverage outside block must fire")

    def test_suppression_in_html_file(self):
        """AC4: suppression markers work in .html files too."""
        text = (
            "<html>\n"
            "<!-- humanize:ignore -->\n"
            "<p>We should leverage this.</p>\n"
            "<!-- /humanize:ignore -->\n"
            "<p>We should leverage that.</p>\n"
            "</html>\n"
        )
        findings = self._scan(text, suffix=".html")
        leverage_lines = [f["line_number"] for f in findings
                          if f["pattern_id"] == "en_leverage"]
        self.assertNotIn(3, leverage_lines, "leverage on line 3 is suppressed")
        self.assertIn(5, leverage_lines, "leverage on line 5 must fire")

    def test_section_suppression_resumption_after_close(self):
        """AC4: two suppressed blocks with normal content in between work correctly."""
        text = (
            "<!-- humanize:ignore -->\n"
            "Leverage ignored here.\n"
            "<!-- /humanize:ignore -->\n"
            "Leverage fires here.\n"
            "<!-- humanize:ignore -->\n"
            "Leverage ignored again.\n"
            "<!-- /humanize:ignore -->\n"
        )
        findings = self._scan(text)
        leverage_lines = [f["line_number"] for f in findings
                          if f["pattern_id"] == "en_leverage"]
        self.assertNotIn(2, leverage_lines, "line 2 suppressed")
        self.assertIn(4, leverage_lines, "line 4 must fire")
        self.assertNotIn(6, leverage_lines, "line 6 suppressed")


# ---------------------------------------------------------------------------
# AC5: suppression syntax does NOT collide with seo-audit markers
# ---------------------------------------------------------------------------

class TestSuppressionSyntaxNoCollision(unittest.TestCase):
    """AC5: humanize suppression markers are distinct from seo-audit's markers."""

    def test_seo_audit_contrastive_marker_not_honoured(self):
        """AC5: <!-- seo-audit:contrastive --> does NOT suppress humanize findings."""
        text = (
            "<!-- seo-audit:contrastive -->\n"
            "We should leverage this.\n"
            "<!-- /seo-audit:contrastive -->\n"
        )
        path = _write_temp(tempfile.gettempdir(), text, "seo_marker_test.md")
        try:
            result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
            findings = result["findings"]
            leverage = [f for f in findings if f["pattern_id"] == "en_leverage"]
            self.assertGreater(len(leverage), 0,
                               "seo-audit marker must NOT suppress humanize findings")
        finally:
            os.unlink(path)

    def test_humanize_marker_prefix_is_humanize(self):
        """AC5: the suppression marker prefix is 'humanize:' not 'seo-audit:'."""
        # Just check that the open/close marker strings contain 'humanize:', not 'seo-audit:'
        # We verify this by testing that the documented humanize markers work as expected
        text = (
            "<!-- humanize:ignore -->\n"
            "Leverage suppressed.\n"
            "<!-- /humanize:ignore -->\n"
        )
        path = _write_temp(tempfile.gettempdir(), text, "humanize_marker_test.md")
        try:
            result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
            findings = result["findings"]
            self.assertEqual([], [f for f in findings if f["pattern_id"] == "en_leverage"],
                             "humanize:ignore must suppress leverage finding")
        finally:
            os.unlink(path)

    def test_contrastive_vocabulary_flag_not_honoured(self):
        """AC5: 'contrastiveVocabulary: true' (seo-audit per-file flag) does NOT suppress humanize."""
        text = (
            "<!-- contrastiveVocabulary: true -->\n"
            "We should leverage this.\n"
        )
        path = _write_temp(tempfile.gettempdir(), text, "contrast_flag_test.md")
        try:
            result = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
            leverage = [f for f in result["findings"] if f["pattern_id"] == "en_leverage"]
            self.assertGreater(len(leverage), 0,
                               "seo-audit contrastiveVocabulary flag must NOT suppress humanize")
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# AC6: determinism + golden fixtures per file type and suppression cases
# ---------------------------------------------------------------------------

# Golden fixture for .html file type
_HTML_GOLDEN_TEXT = """\
<html>
<head>
<script>
var leverage = "delve";
var tapestry = true;
</script>
<style>
.leverage { color: red; }
</style>
</head>
<body>
<p>We should leverage this approach.</p>
<p>This will delve into the subject.</p>
</body>
</html>
"""
# Expected: 'leverage' on line 12, 'delve' on line 13 — script/style suppressed

# Golden fixture for .ts summary extraction
_TS_GOLDEN_TEXT = """\
export const project = {
  name: 'Test',
  summary: {
    de: 'Normaler Text.',
    en: 'You should leverage this approach to delve deeper.',
  },
};
"""
# Expected: 'leverage' and 'delve' in summary.en (line 5)

# Golden fixture for section suppression
_SUPPRESSION_GOLDEN_TEXT = """\
We should leverage this approach.
<!-- humanize:ignore -->
Another leverage line (suppressed).
<!-- /humanize:ignore -->
One more leverage mention.
"""
# Expected: leverage on lines 1 and 5; NOT on line 3


class TestGoldenFixtures(unittest.TestCase):
    """AC6: golden fixtures for filetype strip strategies and suppression."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _scan(self, text: str, name: str, lang: str = "en") -> list:
        path = _write_temp(self._tmpdir.name, text, name)
        result = slop_scanner.scan_file_with_language(path, lang, str(SKILL_DIR))
        return result["findings"]

    def test_html_golden_script_style_suppressed(self):
        """AC6 HTML: slop words in <script>/<style> produce no findings."""
        findings = self._scan(_HTML_GOLDEN_TEXT, "golden.html")
        leverage_lines = [f["line_number"] for f in findings if f["pattern_id"] == "en_leverage"]
        delve_lines = [f["line_number"] for f in findings if f["pattern_id"] == "en_delve"]
        # Script is on lines 3-6, style lines 7-9 → those must be blank
        self.assertNotIn(4, leverage_lines, "leverage in <script> must not fire")
        self.assertNotIn(8, leverage_lines, "leverage in <style> must not fire")
        # Body findings on lines 12, 13 must fire
        self.assertIn(12, leverage_lines, "leverage in body (line 12) must fire")
        self.assertIn(13, delve_lines, "delve in body (line 13) must fire")

    def test_ts_golden_summary_fields_found(self):
        """AC6 TS: slop words in summary fields are found, code tokens not."""
        findings = self._scan(_TS_GOLDEN_TEXT, "golden.ts")
        word_ids = {f["pattern_id"] for f in findings if f["type"] in ("word", "phrase")}
        self.assertIn("en_leverage", word_ids, "leverage in summary.en must be found")
        self.assertIn("en_delve", word_ids, "delve in summary.en must be found")

    def test_suppression_golden_lines_correct(self):
        """AC6 suppression: lines 1+5 fire, line 3 suppressed."""
        findings = self._scan(_SUPPRESSION_GOLDEN_TEXT, "golden_suppress.md")
        leverage_lines = sorted([f["line_number"] for f in findings
                                  if f["pattern_id"] == "en_leverage"])
        self.assertIn(1, leverage_lines, "line 1 must fire")
        self.assertNotIn(3, leverage_lines, "line 3 must be suppressed")
        self.assertIn(5, leverage_lines, "line 5 must fire")

    def test_html_determinism(self):
        """AC6: two HTML scans produce byte-identical JSON."""
        path = _write_temp(self._tmpdir.name, _HTML_GOLDEN_TEXT, "det.html")
        r1 = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        r2 = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        j1 = json.dumps(r1, ensure_ascii=False, indent=2, sort_keys=False)
        j2 = json.dumps(r2, ensure_ascii=False, indent=2, sort_keys=False)
        self.assertEqual(j1, j2)

    def test_ts_determinism(self):
        """AC6: two TS scans produce byte-identical JSON."""
        path = _write_temp(self._tmpdir.name, _TS_GOLDEN_TEXT, "det.ts")
        r1 = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        r2 = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        j1 = json.dumps(r1, ensure_ascii=False, indent=2, sort_keys=False)
        j2 = json.dumps(r2, ensure_ascii=False, indent=2, sort_keys=False)
        self.assertEqual(j1, j2)

    def test_suppression_determinism(self):
        """AC6: two suppression scans produce byte-identical JSON."""
        path = _write_temp(self._tmpdir.name, _SUPPRESSION_GOLDEN_TEXT, "det_sup.md")
        r1 = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        r2 = slop_scanner.scan_file_with_language(path, "en", str(SKILL_DIR))
        j1 = json.dumps(r1, ensure_ascii=False, indent=2, sort_keys=False)
        j2 = json.dumps(r2, ensure_ascii=False, indent=2, sort_keys=False)
        self.assertEqual(j1, j2)

    def test_md_file_golden_scanned_as_plain(self):
        """AC6 MD: plain .md file still scanned as before (backward compat)."""
        text = "Zudem ist das wichtig zu beachten.\n"
        findings = self._scan(text, "golden.md", lang="de")
        ids = {f["pattern_id"] for f in findings}
        self.assertIn("de_zudem", ids,
                      ".md golden: de_zudem must be found in plain markdown")

    def test_findings_sorted_in_all_file_types(self):
        """AC6: findings from all file types are sorted by (file_path, line_number, pattern_id)."""
        for text, name in [
            (_HTML_GOLDEN_TEXT, "sort.html"),
            (_TS_GOLDEN_TEXT, "sort.ts"),
            (_SUPPRESSION_GOLDEN_TEXT, "sort_sup.md"),
        ]:
            findings = self._scan(text, name)
            keys = [(f["file_path"], f["line_number"], f["pattern_id"]) for f in findings]
            self.assertEqual(sorted(keys), keys,
                             f"Findings not sorted for {name}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
