#!/usr/bin/env python3
"""Tests for setup.verify — injected clients only, no network."""

import pathlib
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from setup import verify as V  # noqa: E402


def _client_returning(status, body=""):
    def client(method, url, headers, body_):
        return (status, body)
    return client


class StatusLabels(unittest.TestCase):
    def test_known_labels(self):
        cases = {
            200: "OK",
            204: "OK",
            401: "401 unauthorized",
            403: "403 forbidden",
            404: "404 not found",
            429: "429 rate-limited",
            500: "500 server error",
            503: "503 server error",
            0:   "network-error",
            418: "418 unexpected",
        }
        for status, label in cases.items():
            with self.subTest(status=status):
                self.assertEqual(V._status_label(status), label)


class Pagespeed(unittest.TestCase):
    def test_skipped_without_env(self):
        out = V.verify_pagespeed({})
        self.assertFalse(out["configured"])

    def test_calls_client_with_endpoint(self):
        calls = {}

        def fake(method, url, headers, body):
            calls["method"] = method
            calls["url"] = url
            return (200, '{"ok":true}')

        out = V.verify_pagespeed({"PAGESPEED_API_KEY": "k"}, client=fake)
        self.assertEqual(calls["method"], "GET")
        self.assertIn("runPagespeed", calls["url"])
        self.assertIn("strategy=mobile", calls["url"])
        self.assertEqual(out["status"], 200)
        self.assertEqual(out["label"], "OK")

    def test_diagnose_on_401(self):
        out = V.verify_pagespeed(
            {"PAGESPEED_API_KEY": "k"},
            client=_client_returning(401),
        )
        self.assertIn("API-Key", out["diagnose"])


class Bing(unittest.TestCase):
    def test_skipped_without_env(self):
        out = V.verify_bing({})
        self.assertFalse(out["configured"])

    def test_calls_client_with_geturlinfo(self):
        calls = {}

        def fake(method, url, headers, body):
            calls["url"] = url
            return (200, "OK")

        V.verify_bing({"BING_WEBMASTER_API_KEY": "k"}, client=fake)
        self.assertIn("GetUrlInfo", calls["url"])
        self.assertIn("apikey=k", calls["url"])

    def test_diagnose_on_403(self):
        out = V.verify_bing(
            {"BING_WEBMASTER_API_KEY": "k"},
            client=_client_returning(403),
        )
        self.assertIn("verifiziert", out["diagnose"].lower())


class IndexNow(unittest.TestCase):
    def test_skipped_without_env(self):
        out = V.verify_indexnow({})
        self.assertFalse(out["configured"])

    def test_skipped_without_host(self):
        out = V.verify_indexnow({"INDEXNOW_KEY": "k"}, public_host="")
        self.assertFalse(out["configured"])
        self.assertIn("public host", out["note"].lower())

    def test_does_not_submit_a_url(self):
        calls = []

        def fake(method, url, headers, body):
            calls.append((method, url))
            return (200, "")

        V.verify_indexnow(
            {"INDEXNOW_KEY": "abc"},
            public_host="example.com",
            client=fake,
        )
        self.assertEqual(calls[0][0], "HEAD")
        # Must hit the key file URL, NOT the IndexNow endpoint.
        self.assertEqual(calls[0][1], "https://example.com/abc.txt")
        # IndexNow submission endpoint must NEVER be called by verify.
        self.assertNotIn("api.indexnow.org", calls[0][1])

    def test_diagnose_on_404(self):
        out = V.verify_indexnow(
            {"INDEXNOW_KEY": "abc"},
            public_host="example.com",
            client=_client_returning(404),
        )
        self.assertIn("Key-Datei", out["diagnose"])


class Gsc(unittest.TestCase):
    def test_skipped_without_client(self):
        out = V.verify_gsc()
        self.assertFalse(out["configured"])

    def test_returns_status_from_mcp_client(self):
        def fake(name):
            return {"status": 200, "body": []}

        out = V.verify_gsc(mcp_client=fake)
        self.assertTrue(out["configured"])
        self.assertEqual(out["status"], 200)

    def test_diagnose_on_429(self):
        def fake(name):
            return {"status": 429}

        out = V.verify_gsc(mcp_client=fake)
        self.assertIn("Quote", out["diagnose"])


class RunAndRender(unittest.TestCase):
    def test_run_returns_one_result_per_tool_in_stable_order(self):
        results = V.run(env={}, public_host="example.com", clients={})
        tools = [r["tool"] for r in results]
        self.assertEqual(tools, ["indexnow", "pagespeed", "bing", "gsc"])

    def test_render_emits_markdown_table(self):
        results = V.run(env={}, public_host="", clients={})
        out = V.render(results)
        self.assertIn("seo-audit verify", out)
        self.assertIn("| Tool |", out)
        self.assertIn("indexnow", out)

    def test_render_shows_ok_lines_for_configured_tools(self):
        env = {
            "PAGESPEED_API_KEY": "k",
            "BING_WEBMASTER_API_KEY": "k",
            "INDEXNOW_KEY": "abc",
        }
        clients = {
            "pagespeed": _client_returning(200),
            "bing": _client_returning(200),
            "indexnow": _client_returning(200),
            "gsc": lambda n: {"status": 200, "body": []},
        }
        results = V.run(env=env, public_host="example.com", clients=clients)
        out = V.render(results)
        self.assertIn("OK · 200", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
