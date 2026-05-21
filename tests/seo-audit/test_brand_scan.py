#!/usr/bin/env python3
"""Tests for seo-audit/scripts/brand_scan.py.

The scanner reads a list of glossary entries and an HTML directory,
matches every term case-insensitively against every HTML file's text
content (excluding script/style tags), and emits one finding per match
shaped:

    {file_path, line_number, match, suggested_replacement, rationale}

Suppression rules:

* Files whose frontmatter contains `contrastiveVocabulary: true` are
  skipped entirely.
* Sections wrapped in `<!-- seo-audit:contrastive -->` …
  `<!-- /seo-audit:contrastive -->` (or terminated by EOF) are
  suppressed.

Run from the repo root:
    python3 tests/seo-audit/test_brand_scan.py
"""

import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import brand_scan as B  # noqa: E402


GLOSSARY = [
    {"term": "App", "replacement": "Web App", "rationale": "Marke ist Web-first"},
    {"term": "Tool", "replacement": "Helper", "rationale": "klingt zu klein"},
]


def write(path: str, content: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)


class ScanDist(unittest.TestCase):
    def test_finds_match_with_line_number(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = (
                "<html><body>\n"
                "<h1>Willkommen</h1>\n"
                "<p>Diese App ist super.</p>\n"
                "</body></html>\n"
            )
            f = os.path.join(tmp, "index.html")
            write(f, html)
            findings = B.scan_directory(tmp, GLOSSARY)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["file_path"], f)
            self.assertEqual(findings[0]["line_number"], 3)
            self.assertEqual(findings[0]["match"], "App")
            self.assertEqual(findings[0]["suggested_replacement"], "Web App")
            self.assertEqual(findings[0]["rationale"], "Marke ist Web-first")

    def test_case_insensitive_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "a.html"),
                  "<p>diese app ist klein</p>\n<p>oder APP groß</p>\n")
            findings = B.scan_directory(tmp, GLOSSARY)
            self.assertEqual(len(findings), 2)
            self.assertEqual(
                sorted([f["line_number"] for f in findings]), [1, 2]
            )

    def test_word_boundary_prevents_substring_matches(self):
        # "App" must not match inside "Apple" or "Happy".
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "a.html"),
                  "<p>Apple und Happy sind kein Match.</p>\n"
                  "<p>App alleine schon.</p>\n")
            findings = B.scan_directory(tmp, GLOSSARY)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["line_number"], 2)

    def test_skips_content_inside_script_and_style(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "a.html"),
                  "<script>var App = 1;</script>\n"
                  "<style>.App { color: red; }</style>\n"
                  "<p>App im Body</p>\n")
            findings = B.scan_directory(tmp, GLOSSARY)
            self.assertEqual(len(findings), 1)
            self.assertEqual(findings[0]["line_number"], 3)

    def test_contrastive_marker_suppresses_section(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "a.html"),
                  "<p>App vor dem Marker.</p>\n"
                  "<!-- seo-audit:contrastive -->\n"
                  "<p>App im kontrastiven Block.</p>\n"
                  "<!-- /seo-audit:contrastive -->\n"
                  "<p>App nach dem Marker.</p>\n")
            findings = B.scan_directory(tmp, GLOSSARY)
            self.assertEqual(len(findings), 2)
            self.assertEqual(
                sorted([f["line_number"] for f in findings]), [1, 5]
            )

    def test_frontmatter_flag_suppresses_whole_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "contrastive.html"),
                  "<!--\n"
                  "contrastiveVocabulary: true\n"
                  "-->\n"
                  "<p>App ist hier erwartet.</p>\n")
            write(os.path.join(tmp, "normal.html"),
                  "<p>App im normalen Doc.</p>\n")
            findings = B.scan_directory(tmp, GLOSSARY)
            self.assertEqual(len(findings), 1)
            self.assertTrue(findings[0]["file_path"].endswith("normal.html"))

    def test_recursive_directory_walk(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "a.html"), "<p>App eins</p>\n")
            write(os.path.join(tmp, "sub", "b.html"),
                  "<p>App zwei</p>\n")
            findings = B.scan_directory(tmp, GLOSSARY)
            self.assertEqual(len(findings), 2)

    def test_deterministic_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "z.html"), "<p>App</p>\n<p>Tool</p>\n")
            write(os.path.join(tmp, "a.html"), "<p>App</p>\n")
            findings_1 = B.scan_directory(tmp, GLOSSARY)
            findings_2 = B.scan_directory(tmp, GLOSSARY)
            self.assertEqual(findings_1, findings_2)
            # Sort key: (file_path, line_number, match)
            keys = [(f["file_path"], f["line_number"], f["match"])
                    for f in findings_1]
            self.assertEqual(keys, sorted(keys))

    def test_empty_directory_returns_empty_list(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(B.scan_directory(tmp, GLOSSARY), [])

    def test_empty_glossary_returns_empty_findings(self):
        with tempfile.TemporaryDirectory() as tmp:
            write(os.path.join(tmp, "a.html"), "<p>App</p>\n")
            self.assertEqual(B.scan_directory(tmp, []), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
