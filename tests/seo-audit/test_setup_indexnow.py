#!/usr/bin/env python3
"""Tests for the IndexNow setup wizard — idempotency + --force."""

import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from setup import setup_indexnow as IDX  # noqa: E402


def _fixed_uuid_gen():
    return "deadbeef" * 4


class Plan(unittest.TestCase):
    def test_plan_not_ready_without_public_dir(self):
        p = IDX.plan({}, public_dir=None)
        self.assertFalse(p["ready"])
        self.assertIn("Public directory", p["reason"])

    def test_plan_generates_new_key_when_env_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = IDX.plan({}, public_dir=pathlib.Path(tmp),
                         uuid_gen=_fixed_uuid_gen)
            self.assertTrue(p["ready"])
            self.assertEqual(p["key"], "deadbeef" * 4)
            self.assertFalse(p["already_configured"])

    def test_plan_reuses_existing_env_key_when_file_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp)
            (public / "abc123.txt").write_text("abc123", encoding="utf-8")
            p = IDX.plan(
                {"INDEXNOW_KEY": "abc123"},
                public_dir=public,
                uuid_gen=_fixed_uuid_gen,
            )
            self.assertTrue(p["already_configured"])
            self.assertEqual(p["key"], "abc123")

    def test_plan_with_force_regenerates_even_if_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp)
            (public / "abc123.txt").write_text("abc123", encoding="utf-8")
            p = IDX.plan(
                {"INDEXNOW_KEY": "abc123"},
                public_dir=public,
                force=True,
                uuid_gen=_fixed_uuid_gen,
            )
            self.assertFalse(p["already_configured"])
            self.assertEqual(p["key"], "deadbeef" * 4)

    def test_plan_warns_on_content_mismatch(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp)
            (public / "abc123.txt").write_text("WRONG", encoding="utf-8")
            p = IDX.plan(
                {"INDEXNOW_KEY": "abc123"},
                public_dir=public,
                uuid_gen=_fixed_uuid_gen,
            )
            self.assertTrue(p["ready"])
            self.assertFalse(p["already_configured"])
            self.assertTrue(any("mismatch" in w for w in p["warnings"]))


class Execute(unittest.TestCase):
    def test_execute_writes_key_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = IDX.plan({}, public_dir=pathlib.Path(tmp),
                         uuid_gen=_fixed_uuid_gen)
            result = IDX.execute(p)
            self.assertTrue(result["applied"])
            written = pathlib.Path(p["key_file"])
            self.assertTrue(written.is_file())
            self.assertEqual(written.read_text(encoding="utf-8"),
                             "deadbeef" * 4)

    def test_execute_idempotent_when_already_configured(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp)
            (public / "abc123.txt").write_text("abc123", encoding="utf-8")
            p = IDX.plan({"INDEXNOW_KEY": "abc123"}, public_dir=public)
            calls = []

            def fail_writer(*a, **kw):
                calls.append(a)

            result = IDX.execute(p, file_writer=fail_writer)
            self.assertFalse(result["applied"])
            self.assertEqual(calls, [])

    def test_execute_uses_injected_writer(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = IDX.plan({}, public_dir=pathlib.Path(tmp),
                         uuid_gen=_fixed_uuid_gen)
            received = {}

            def writer(path, content):
                received["path"] = path
                received["content"] = content

            result = IDX.execute(p, file_writer=writer)
            self.assertTrue(result["applied"])
            self.assertEqual(received["content"], "deadbeef" * 4)


class Render(unittest.TestCase):
    def test_render_emits_env_export(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = IDX.plan({}, public_dir=pathlib.Path(tmp),
                         uuid_gen=_fixed_uuid_gen)
            out = IDX.render(p)
            self.assertIn("export INDEXNOW_KEY=", out)
            self.assertIn("deadbeef", out)

    def test_render_says_already_configured_on_idempotent_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp)
            (public / "abc123.txt").write_text("abc123", encoding="utf-8")
            p = IDX.plan({"INDEXNOW_KEY": "abc123"}, public_dir=public)
            out = IDX.render(p)
            self.assertIn("already configured", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
