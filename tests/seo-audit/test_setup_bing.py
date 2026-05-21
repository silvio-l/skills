#!/usr/bin/env python3
"""Tests for the Bing Webmaster setup wizard."""

import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from setup import setup_bing as B  # noqa: E402


class Plan(unittest.TestCase):
    def test_plan_lists_console_url(self):
        p = B.plan({})
        self.assertEqual(len(p["console_urls"]), 1)
        self.assertIn("bing.com/webmasters", p["console_urls"][0])

    def test_already_configured_when_env_set(self):
        self.assertTrue(B.plan({"BING_WEBMASTER_API_KEY": "k"})["already_configured"])


class Execute(unittest.TestCase):
    def test_opens_on_darwin(self):
        p = B.plan({})
        opened = []
        B.execute(p, platform="darwin", browser_opener=opened.append)
        self.assertEqual(opened, p["console_urls"])

    def test_does_not_open_on_linux(self):
        p = B.plan({})
        opened = []
        B.execute(p, platform="linux", browser_opener=opened.append)
        self.assertEqual(opened, [])


class Render(unittest.TestCase):
    def test_render_lists_steps(self):
        out = B.render(B.plan({}))
        self.assertIn("Settings", out)
        self.assertIn("BING_WEBMASTER_API_KEY", out)
        self.assertIn("BING_DAILY_LIMIT", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
