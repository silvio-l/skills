#!/usr/bin/env python3
"""Tests for the GSC setup wizard."""

import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from setup import setup_gsc as G  # noqa: E402


def _mcp_ok(argv):
    return {
        "returncode": 0,
        "stdout": "mcp__gsc__list_properties\nmcp__supabase__list_tables\n",
        "stderr": "",
    }


def _mcp_no_gsc(argv):
    return {"returncode": 0, "stdout": "mcp__supabase__list_tables\n",
            "stderr": ""}


def _mcp_no_cli(argv):
    return {"returncode": 127, "stdout": "", "stderr": "claude: not found"}


class Plan(unittest.TestCase):
    def test_cli_present_with_gsc(self):
        p = G.plan({}, mcp_runner=_mcp_ok)
        self.assertTrue(p["cli_available"])
        self.assertTrue(p["gsc_registered"])
        self.assertIn("reauthenticate", p["next_step"])

    def test_cli_present_no_gsc(self):
        p = G.plan({}, mcp_runner=_mcp_no_gsc)
        self.assertTrue(p["cli_available"])
        self.assertFalse(p["gsc_registered"])
        self.assertIn("Install", p["next_step"])

    def test_cli_missing(self):
        p = G.plan({}, mcp_runner=_mcp_no_cli)
        self.assertFalse(p["cli_available"])
        self.assertFalse(p["gsc_registered"])


class Execute(unittest.TestCase):
    def test_opens_docs_on_darwin(self):
        p = G.plan({}, mcp_runner=_mcp_ok)
        opened = []
        G.execute(p, platform="darwin", browser_opener=opened.append)
        # GSC home + MCP repo
        self.assertEqual(len(opened), 2)

    def test_does_not_open_on_linux(self):
        p = G.plan({}, mcp_runner=_mcp_ok)
        opened = []
        G.execute(p, platform="linux", browser_opener=opened.append)
        self.assertEqual(opened, [])


class Render(unittest.TestCase):
    def test_render_includes_reauth_command(self):
        out = G.render(G.plan({}, mcp_runner=_mcp_ok))
        self.assertIn("claude mcp call mcp__gsc__reauthenticate", out)

    def test_render_when_cli_missing_says_install(self):
        out = G.render(G.plan({}, mcp_runner=_mcp_no_cli))
        self.assertIn("Install", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
