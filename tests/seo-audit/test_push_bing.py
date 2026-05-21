#!/usr/bin/env python3
"""Tests for the Bing Webmaster push adapter.

The adapter must:
* skip silently with no findings when BING_WEBMASTER_API_KEY is unset,
* read a date-rolled counter from a state directory,
* clip the batch when today's count + planned URLs > limit,
* respect BING_DAILY_LIMIT override,
* POST one request per URL when confirmed and persist counter,
* not increment the counter in dry-run mode.
"""

import datetime
import json
import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from push import bing_webmaster as BW  # noqa: E402


def _today() -> str:
    return datetime.date.today().strftime("%Y-%m-%d")


class BingPlan(unittest.TestCase):
    def test_plan_skips_without_api_key(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = BW.plan(
                site_url="https://example.com/",
                urls=["https://example.com/x"],
                state_dir=pathlib.Path(tmp),
                env={},
            )
            self.assertFalse(plan["ready"])
            self.assertIn("BING_WEBMASTER_API_KEY", plan["reason"])

    def test_plan_reports_zero_quota_used_when_no_counter_yet(self):
        with tempfile.TemporaryDirectory() as tmp:
            plan = BW.plan(
                site_url="https://example.com/",
                urls=["https://example.com/x"],
                state_dir=pathlib.Path(tmp),
                env={"BING_WEBMASTER_API_KEY": "k"},
            )
            self.assertTrue(plan["ready"])
            self.assertEqual(plan["used_today"], 0)
            self.assertEqual(plan["daily_limit"], 10)

    def test_plan_clips_batch_to_remaining_budget(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = pathlib.Path(tmp)
            # Pre-write today's counter as 8.
            (state_dir / f"seo-audit-bing-counter-{_today()}.json").write_text(
                json.dumps({"count": 8}), encoding="utf-8"
            )
            urls = [f"https://example.com/p{i}" for i in range(15)]
            plan = BW.plan(
                site_url="https://example.com/",
                urls=urls,
                state_dir=state_dir,
                env={"BING_WEBMASTER_API_KEY": "k"},
            )
            self.assertTrue(plan["ready"])
            self.assertEqual(plan["used_today"], 8)
            self.assertEqual(len(plan["items"]), 2)  # 10 - 8
            self.assertEqual(len(plan["dropped"]), 13)
            self.assertTrue(any("quota" in w.lower() for w in plan["warnings"]))

    def test_plan_respects_configurable_limit(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = pathlib.Path(tmp)
            urls = [f"https://example.com/p{i}" for i in range(15)]
            plan = BW.plan(
                site_url="https://example.com/",
                urls=urls,
                state_dir=state_dir,
                env={
                    "BING_WEBMASTER_API_KEY": "k",
                    "BING_DAILY_LIMIT": "50",
                },
            )
            self.assertEqual(plan["daily_limit"], 50)
            self.assertEqual(len(plan["items"]), 15)
            self.assertEqual(plan["dropped"], [])

    def test_plan_ignores_stale_counter_from_yesterday(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = pathlib.Path(tmp)
            yesterday = (datetime.date.today() -
                         datetime.timedelta(days=1)).strftime("%Y-%m-%d")
            (state_dir / f"seo-audit-bing-counter-{yesterday}.json").write_text(
                json.dumps({"count": 9}), encoding="utf-8"
            )
            plan = BW.plan(
                site_url="https://example.com/",
                urls=["https://example.com/p1"],
                state_dir=state_dir,
                env={"BING_WEBMASTER_API_KEY": "k"},
            )
            self.assertEqual(plan["used_today"], 0)


class BingExecute(unittest.TestCase):
    def test_execute_posts_per_url_and_increments_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = pathlib.Path(tmp)
            urls = ["https://example.com/a", "https://example.com/b"]
            plan = BW.plan(
                site_url="https://example.com/",
                urls=urls,
                state_dir=state_dir,
                env={"BING_WEBMASTER_API_KEY": "k"},
            )

            calls = []

            def fake_client(method, url, headers, body):
                calls.append((method, url, body))
                return (200, "OK")

            result = BW.execute(plan, client=fake_client, confirmed=True)
            self.assertTrue(result["submitted"])
            self.assertEqual(len(calls), 2)
            for (method, url, body) in calls:
                self.assertEqual(method, "POST")
                self.assertIn("ssw.live.com", url)
                self.assertIn("apikey=k", url)

            counter_path = state_dir / f"seo-audit-bing-counter-{_today()}.json"
            self.assertTrue(counter_path.is_file())
            self.assertEqual(
                json.loads(counter_path.read_text(encoding="utf-8"))["count"],
                2,
            )

    def test_execute_skipped_when_not_confirmed(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = pathlib.Path(tmp)
            plan = BW.plan(
                site_url="https://example.com/",
                urls=["https://example.com/x"],
                state_dir=state_dir,
                env={"BING_WEBMASTER_API_KEY": "k"},
            )
            calls = []

            def fake_client(method, url, headers, body):
                calls.append(url)
                return (200, "OK")

            result = BW.execute(plan, client=fake_client, confirmed=False)
            self.assertFalse(result["submitted"])
            self.assertEqual(calls, [])
            counter_path = state_dir / f"seo-audit-bing-counter-{_today()}.json"
            self.assertFalse(counter_path.is_file())

    def test_execute_silent_when_plan_not_ready(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = pathlib.Path(tmp)
            plan = BW.plan(
                site_url="https://example.com/",
                urls=["https://example.com/x"],
                state_dir=state_dir,
                env={},
            )
            calls = []

            def fake_client(method, url, headers, body):
                calls.append(url)
                return (200, "OK")

            result = BW.execute(plan, client=fake_client, confirmed=True)
            self.assertFalse(result["submitted"])
            self.assertEqual(calls, [])

    def test_execute_appends_to_existing_counter(self):
        with tempfile.TemporaryDirectory() as tmp:
            state_dir = pathlib.Path(tmp)
            (state_dir / f"seo-audit-bing-counter-{_today()}.json").write_text(
                json.dumps({"count": 3}), encoding="utf-8"
            )
            plan = BW.plan(
                site_url="https://example.com/",
                urls=["https://example.com/x", "https://example.com/y"],
                state_dir=state_dir,
                env={"BING_WEBMASTER_API_KEY": "k"},
            )

            def fake_client(method, url, headers, body):
                return (200, "OK")

            BW.execute(plan, client=fake_client, confirmed=True)
            counter_path = state_dir / f"seo-audit-bing-counter-{_today()}.json"
            self.assertEqual(
                json.loads(counter_path.read_text(encoding="utf-8"))["count"],
                5,
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
