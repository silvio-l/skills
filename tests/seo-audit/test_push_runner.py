#!/usr/bin/env python3
"""Tests for the push orchestrator.

`push.plan_all(...)` aggregates the three module plans.
`push.execute_all(plans, ...)` runs only the confirmed operations.
`push.render_dry_run(plans)` renders a Markdown checklist.
"""

import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from push import push as PUSH  # noqa: E402


SAMPLE_CONTEXT_MD = "# Sample\n\n> Short blurb.\n\n## More\n\nProse.\n"


def _setup(tmp: pathlib.Path):
    """Create a minimal repo layout for the orchestrator."""
    public = tmp / "public"
    public.mkdir()
    (public / "abc123.txt").write_text("abc123", encoding="utf-8")
    ctx = tmp / "CONTEXT.md"
    ctx.write_text(SAMPLE_CONTEXT_MD, encoding="utf-8")
    state_dir = tmp / ".scratch"
    state_dir.mkdir()
    return public, ctx, state_dir


class PlanAll(unittest.TestCase):
    def test_plan_aggregates_all_three_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            public, ctx, state_dir = _setup(tmp)
            plans = PUSH.plan_all(
                public_dir=public,
                urls=["https://example.com/a"],
                site_url="https://example.com/",
                context_path=ctx,
                state_dir=state_dir,
                env={
                    "INDEXNOW_KEY": "abc123",
                    "BING_WEBMASTER_API_KEY": "k",
                },
            )
            modules = {p["module"] for p in plans}
            self.assertEqual(modules, {"indexnow", "bing", "llms"})


class ExecuteAll(unittest.TestCase):
    def test_execute_only_runs_confirmed_operations(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            public, ctx, state_dir = _setup(tmp)
            plans = PUSH.plan_all(
                public_dir=public,
                urls=["https://example.com/a"],
                site_url="https://example.com/",
                context_path=ctx,
                state_dir=state_dir,
                env={
                    "INDEXNOW_KEY": "abc123",
                    "BING_WEBMASTER_API_KEY": "k",
                },
            )

            calls = {"indexnow": 0, "bing": 0}

            def fake_indexnow_client(method, url, headers, body):
                calls["indexnow"] += 1
                return (200, "OK")

            def fake_bing_client(method, url, headers, body):
                calls["bing"] += 1
                return (200, "OK")

            results = PUSH.execute_all(
                plans,
                clients={
                    "indexnow": fake_indexnow_client,
                    "bing": fake_bing_client,
                },
                confirmations={
                    "indexnow": True,
                    "bing": False,
                    "llms": True,
                },
            )
            # indexnow ran, bing did not, llms wrote a file.
            self.assertEqual(calls["indexnow"], 1)
            self.assertEqual(calls["bing"], 0)
            self.assertTrue((public / "llms.txt").is_file())
            by_mod = {r["module"]: r for r in results}
            self.assertTrue(by_mod["indexnow"]["submitted"])
            self.assertFalse(by_mod["bing"]["submitted"])
            self.assertTrue(by_mod["llms"]["submitted"])

    def test_execute_all_skips_modules_without_confirmation_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            public, ctx, state_dir = _setup(tmp)
            plans = PUSH.plan_all(
                public_dir=public,
                urls=["https://example.com/a"],
                site_url="https://example.com/",
                context_path=ctx,
                state_dir=state_dir,
                env={
                    "INDEXNOW_KEY": "abc123",
                    "BING_WEBMASTER_API_KEY": "k",
                },
            )

            results = PUSH.execute_all(
                plans,
                clients={
                    "indexnow": lambda *a, **kw: (200, "OK"),
                    "bing": lambda *a, **kw: (200, "OK"),
                },
                confirmations={},  # no confirmations
            )
            for r in results:
                self.assertFalse(r["submitted"])


class DryRun(unittest.TestCase):
    def test_dry_run_flag_renders_markdown_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            public, ctx, state_dir = _setup(tmp)
            plans = PUSH.plan_all(
                public_dir=public,
                urls=["https://example.com/a", "https://example.com/b"],
                site_url="https://example.com/",
                context_path=ctx,
                state_dir=state_dir,
                env={
                    "INDEXNOW_KEY": "abc123",
                    "BING_WEBMASTER_API_KEY": "k",
                },
            )
            rendered = PUSH.render_dry_run(plans)
            self.assertIn("IndexNow", rendered)
            self.assertIn("Bing", rendered)
            self.assertIn("llms", rendered.lower())
            # Markdown checklist marker.
            self.assertIn("- [ ]", rendered)
            # No HTTP was performed — counter file must not exist.
            today_glob = list(state_dir.glob("seo-audit-bing-counter-*.json"))
            self.assertEqual(today_glob, [])

    def test_dry_run_does_not_write_llms_file(self):
        # render_dry_run must be side-effect-free even for llms.
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            public, ctx, state_dir = _setup(tmp)
            plans = PUSH.plan_all(
                public_dir=public,
                urls=["https://example.com/a"],
                site_url="https://example.com/",
                context_path=ctx,
                state_dir=state_dir,
                env={
                    "INDEXNOW_KEY": "abc123",
                    "BING_WEBMASTER_API_KEY": "k",
                },
            )
            PUSH.render_dry_run(plans)
            self.assertFalse((public / "llms.txt").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
