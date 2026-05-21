#!/usr/bin/env python3
"""Tests for the IndexNow push adapter.

The adapter must:
* verify the key file under <public_dir>/<key>.txt exists and matches the env key,
* offer a first-setup hint when the file is missing,
* be silent-skip when the env key is unset,
* POST a correctly-shaped body to api.indexnow.org when confirmed,
* not call the HTTP client when not confirmed,
* not call the client in dry-run mode.
"""

import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from push import indexnow as IN  # noqa: E402


def _setup_public_with_key(public: pathlib.Path, key: str) -> None:
    public.mkdir(parents=True, exist_ok=True)
    (public / f"{key}.txt").write_text(key, encoding="utf-8")


class IndexNowPlan(unittest.TestCase):
    def test_plan_reports_missing_env_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp) / "public"
            public.mkdir()
            plan = IN.plan(public, ["https://example.com/"], env={})
            self.assertFalse(plan["ready"])
            self.assertIn("INDEXNOW_KEY", plan["reason"])

    def test_plan_reports_missing_key_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp) / "public"
            public.mkdir()
            plan = IN.plan(
                public, ["https://example.com/"],
                env={"INDEXNOW_KEY": "abc123"},
            )
            self.assertFalse(plan["ready"])
            self.assertIn("first_setup_hint", plan)
            self.assertIn("abc123.txt", plan["first_setup_hint"])

    def test_plan_reports_key_file_content_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp) / "public"
            public.mkdir()
            (public / "abc123.txt").write_text("WRONG", encoding="utf-8")
            plan = IN.plan(
                public, ["https://example.com/"],
                env={"INDEXNOW_KEY": "abc123"},
            )
            self.assertFalse(plan["ready"])
            self.assertIn("mismatch", plan["reason"].lower())

    def test_plan_reports_ready_when_file_and_env_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp) / "public"
            _setup_public_with_key(public, "abc123")
            plan = IN.plan(
                public, ["https://example.com/a", "https://example.com/b"],
                env={"INDEXNOW_KEY": "abc123"},
            )
            self.assertTrue(plan["ready"])
            self.assertEqual(plan["module"], "indexnow")
            self.assertEqual(len(plan["items"]), 2)


class IndexNowExecute(unittest.TestCase):
    def test_execute_posts_url_list_when_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp) / "public"
            _setup_public_with_key(public, "abc123")
            plan = IN.plan(
                public, ["https://example.com/", "https://example.com/x"],
                env={"INDEXNOW_KEY": "abc123"},
            )
            calls = []

            def fake_client(method, url, headers, body):
                calls.append((method, url, headers, body))
                return (200, "OK")

            result = IN.execute(plan, client=fake_client, confirmed=True)
            self.assertTrue(result["submitted"])
            self.assertEqual(len(calls), 1)
            method, url, headers, body = calls[0]
            self.assertEqual(method, "POST")
            self.assertEqual(url, "https://api.indexnow.org/IndexNow")
            self.assertEqual(headers.get("Content-Type"), "application/json")
            import json
            payload = json.loads(body)
            self.assertEqual(payload["host"], "example.com")
            self.assertEqual(payload["key"], "abc123")
            self.assertIn("abc123.txt", payload["keyLocation"])
            self.assertEqual(
                set(payload["urlList"]),
                {"https://example.com/", "https://example.com/x"},
            )

    def test_execute_skipped_when_not_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp) / "public"
            _setup_public_with_key(public, "abc123")
            plan = IN.plan(
                public, ["https://example.com/"],
                env={"INDEXNOW_KEY": "abc123"},
            )
            calls = []

            def fake_client(method, url, headers, body):
                calls.append((method, url))
                return (200, "OK")

            result = IN.execute(plan, client=fake_client, confirmed=False)
            self.assertFalse(result["submitted"])
            self.assertEqual(calls, [])

    def test_execute_silent_when_plan_not_ready(self):
        # Plan not ready (no key) → execute should refuse, no HTTP.
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp) / "public"
            public.mkdir()
            plan = IN.plan(public, ["https://example.com/"], env={})
            calls = []

            def fake_client(method, url, headers, body):
                calls.append(url)
                return (200, "OK")

            result = IN.execute(plan, client=fake_client, confirmed=True)
            self.assertFalse(result["submitted"])
            self.assertEqual(calls, [])

    def test_execute_records_response_status(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp) / "public"
            _setup_public_with_key(public, "abc123")
            plan = IN.plan(
                public, ["https://example.com/"],
                env={"INDEXNOW_KEY": "abc123"},
            )

            def fake_client(method, url, headers, body):
                return (202, "")

            result = IN.execute(plan, client=fake_client, confirmed=True)
            self.assertTrue(result["submitted"])
            self.assertEqual(result["responses"][0]["status"], 202)


if __name__ == "__main__":
    unittest.main(verbosity=2)
