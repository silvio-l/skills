#!/usr/bin/env python3
"""Tests for seo-audit/scripts/glossary_parser.py.

The parser extracts an anti-vocabulary table from a domain document
(`CONTEXT.md`, `CLAUDE.md`, `README.md`) and returns a list of entries
shaped `{term, replacement, rationale}`. It must accept both the
GitHub-flavoured pipe table form (with leading/trailing pipes and a
separator row) and the bare three-column form without leading pipes.

Run from the repo root:
    python3 tests/seo-audit/test_glossary_parser.py
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import glossary_parser as G  # noqa: E402


class ParseTable(unittest.TestCase):
    def test_pipe_table_with_header_separator(self):
        md = (
            "# Anti-Vokabular\n"
            "\n"
            "| Begriff | Stattdessen | Grund |\n"
            "| ------- | ----------- | ----- |\n"
            "| App     | Web App     | Marke ist Web-first |\n"
            "| Tool    | Helper      | klingt zu klein |\n"
        )
        entries = G.parse_glossary(md)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["term"], "App")
        self.assertEqual(entries[0]["replacement"], "Web App")
        self.assertEqual(entries[0]["rationale"], "Marke ist Web-first")
        self.assertEqual(entries[1]["term"], "Tool")

    def test_bare_table_without_leading_pipes(self):
        md = (
            "Begriff   | Stattdessen | Grund\n"
            "App       | Web App     | Marke ist Web-first\n"
            "Tool      | Helper      | klingt zu klein\n"
        )
        entries = G.parse_glossary(md)
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["term"], "App")
        self.assertEqual(entries[1]["term"], "Tool")

    def test_inline_code_in_cells_is_unwrapped(self):
        md = (
            "| Begriff | Stattdessen | Grund |\n"
            "| ------- | ----------- | ----- |\n"
            "| `App`   | `Web App`   | wegen Marke |\n"
        )
        entries = G.parse_glossary(md)
        self.assertEqual(entries[0]["term"], "App")
        self.assertEqual(entries[0]["replacement"], "Web App")

    def test_skips_separator_row_only(self):
        md = (
            "| Begriff | Stattdessen | Grund |\n"
            "| :------ | :---------- | :---- |\n"
            "| App     | Web App     | x |\n"
        )
        entries = G.parse_glossary(md)
        self.assertEqual(len(entries), 1)

    def test_ignores_unrelated_two_column_tables(self):
        md = (
            "| Foo | Bar |\n"
            "| --- | --- |\n"
            "| 1   | 2   |\n"
        )
        entries = G.parse_glossary(md)
        self.assertEqual(entries, [])

    def test_blank_lines_inside_document_are_tolerated(self):
        md = (
            "Intro text.\n"
            "\n"
            "| Begriff | Stattdessen | Grund |\n"
            "| ------- | ----------- | ----- |\n"
            "| App     | Web App     | x |\n"
            "\n"
            "Trailing prose.\n"
        )
        entries = G.parse_glossary(md)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["term"], "App")

    def test_empty_or_missing_returns_empty(self):
        self.assertEqual(G.parse_glossary(""), [])
        self.assertEqual(G.parse_glossary("just prose, no tables here\n"), [])

    def test_picks_first_glossary_table_when_multiple_present(self):
        # If a doc has multiple 3-col tables, we take the first one whose
        # header matches the glossary shape (Begriff/Stattdessen/Grund).
        md = (
            "| A | B | C |\n"
            "| - | - | - |\n"
            "| x | y | z |\n"
            "\n"
            "| Begriff | Stattdessen | Grund |\n"
            "| ------- | ----------- | ----- |\n"
            "| App     | Web App     | x |\n"
        )
        entries = G.parse_glossary(md)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["term"], "App")

    def test_extra_whitespace_around_cells_is_stripped(self):
        md = (
            "|   Begriff   |   Stattdessen   |   Grund   |\n"
            "| --- | --- | --- |\n"
            "|   App   |   Web App   |   weil   |\n"
        )
        entries = G.parse_glossary(md)
        self.assertEqual(entries[0]["term"], "App")
        self.assertEqual(entries[0]["replacement"], "Web App")
        self.assertEqual(entries[0]["rationale"], "weil")


if __name__ == "__main__":
    unittest.main(verbosity=2)
