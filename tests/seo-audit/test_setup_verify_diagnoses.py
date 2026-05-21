#!/usr/bin/env python3
"""Frozen-mapping test for verify-mode diagnose strings."""

import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from setup import diagnoses as DIAG  # noqa: E402


TOOLS = ("pagespeed", "bing", "indexnow", "gsc")
COMMON_CODES = (401, 403, 404, 429)


class FrozenMapping(unittest.TestCase):
    def test_every_documented_pair_has_diagnose(self):
        for tool in TOOLS:
            for code in COMMON_CODES:
                with self.subTest(tool=tool, code=code):
                    self.assertIn((tool, code), DIAG.DIAGNOSES,
                                  msg=f"missing diagnose for {tool}/{code}")

    def test_diagnose_strings_are_non_empty(self):
        for key, value in DIAG.DIAGNOSES.items():
            with self.subTest(key=key):
                self.assertIsInstance(value, str)
                self.assertGreater(len(value), 20,
                                   msg=f"diagnose for {key} is too short")

    def test_diagnose_strings_mention_tool_name(self):
        # Each curated string starts with the tool noun so users
        # see who is failing without needing the status line context.
        for (tool, _code), value in DIAG.DIAGNOSES.items():
            with self.subTest(tool=tool):
                self.assertIn(
                    {
                        "pagespeed": "PageSpeed",
                        "bing": "Bing",
                        "indexnow": "IndexNow",
                        "gsc": "GSC",
                    }[tool],
                    value,
                )


class DiagnoseFunction(unittest.TestCase):
    def test_known_pair_returns_curated_string(self):
        self.assertIn("PageSpeed-Insights-API",
                      DIAG.diagnose("pagespeed", 403))

    def test_unknown_pair_falls_back_for_5xx(self):
        out = DIAG.diagnose("bing", 503)
        self.assertIn("Server-Fehler", out)
        self.assertIn("503", out)

    def test_unknown_pair_falls_back_for_network_error(self):
        out = DIAG.diagnose("gsc", 0)
        self.assertIn("Netzwerk-Fehler", out)

    def test_2xx_returns_ok(self):
        out = DIAG.diagnose("pagespeed", 200)
        self.assertIn("OK", out)

    def test_tool_name_lowercased(self):
        # Case-insensitive lookup.
        a = DIAG.diagnose("PageSpeed", 401)
        b = DIAG.diagnose("pagespeed", 401)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main(verbosity=2)
