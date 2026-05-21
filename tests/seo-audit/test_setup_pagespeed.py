#!/usr/bin/env python3
"""Tests for the PageSpeed setup wizard."""

import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from setup import setup_pagespeed as PS  # noqa: E402


class Plan(unittest.TestCase):
    def test_plan_mentions_both_console_urls(self):
        p = PS.plan({})
        self.assertEqual(len(p["console_urls"]), 2)

    def test_plan_marks_already_configured_when_env_set(self):
        self.assertTrue(PS.plan({"PAGESPEED_API_KEY": "k"})["already_configured"])
        self.assertFalse(PS.plan({})["already_configured"])


class Execute(unittest.TestCase):
    def test_execute_opens_urls_on_darwin(self):
        p = PS.plan({})
        opened = []
        result = PS.execute(p, platform="darwin",
                            browser_opener=opened.append)
        self.assertEqual(set(opened), set(p["console_urls"]))
        self.assertEqual(set(result["opened"]), set(p["console_urls"]))

    def test_execute_does_not_open_on_linux(self):
        p = PS.plan({})
        opened = []
        PS.execute(p, platform="linux", browser_opener=opened.append)
        self.assertEqual(opened, [])

    def test_execute_does_not_open_on_windows(self):
        p = PS.plan({})
        opened = []
        PS.execute(p, platform="win32", browser_opener=opened.append)
        self.assertEqual(opened, [])

    def test_execute_no_opener_returns_empty(self):
        p = PS.plan({})
        # On darwin without an opener, nothing should crash.
        result = PS.execute(p, platform="darwin", browser_opener=None)
        self.assertEqual(result["opened"], [])


class Render(unittest.TestCase):
    def test_render_lists_steps(self):
        out = PS.render(PS.plan({}))
        self.assertIn("Create credentials", out)
        self.assertIn("PAGESPEED_API_KEY", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
