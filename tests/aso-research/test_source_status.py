#!/usr/bin/env python3
"""Tests for source-status transparency (P2 — slice 02 quality hardening).

Run from the repo root:
    python3 tests/aso-research/test_source_status.py

Covers ACs:
- AC1: Reason-bearing status (ModuleNotFoundError records the reason)
- AC2: ok_empty / result_count:0 for empty-but-reachable sources
- AC3: apple_similar false-OK closed (empty list from failed path -> unavailable)
- AC4: Non-JSON HTML drift in Apple Search-Suggest
- AC5: Per-source result counts in source-health board / summary
- AC6: EN-without-EN-market caveat
- AC7: Never-blocking preserved
- AC8: _source_split works with structured status entries
"""

import datetime
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import collect  # noqa: E402
import report  # noqa: E402
import schema  # noqa: E402


def _core(tid, title, rating_count=100):
    return schema.merge_apple_slots(
        schema.map_itunes_to_core(
            {
                "trackId": tid,
                "trackName": title,
                "primaryGenreName": "Health & Fitness",
                "userRatingCount": rating_count,
                "description": f"{title} description habit routine",
                "formattedPrice": "Gratis",
                "price": 0.0,
            }
        ),
        subtitle="",
    )


def _status_is_ok(entry):
    """Test helper: is a structured status entry ok?"""
    if isinstance(entry, dict):
        return entry.get("status") == "ok"
    return entry == "ok"


class ReasonBearingStatusTests(unittest.TestCase):
    """AC1: A collector raising ModuleNotFoundError records the reason."""

    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }
        self.competitors = [_core(1, "Habit Tracker", 5000)]

    def test_module_not_found_error_records_reason(self):
        def boom_subtitle(cid, **_k):
            raise ModuleNotFoundError("playwright")

        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=boom_subtitle,
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: [],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_subtitle"]
        self.assertIsInstance(entry, dict)
        self.assertEqual(entry["status"], "unavailable")
        self.assertIn("ModuleNotFoundError", entry.get("reason", ""))

    def test_arbitrary_exception_records_reason(self):
        def boom_charts(*a, **k):
            raise RuntimeError("connection refused")

        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=lambda *a, **k: [],
            chart_fn=boom_charts,
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_rss_charts"]
        self.assertIsInstance(entry, dict)
        self.assertEqual(entry["status"], "unavailable")
        self.assertIn("connection refused", entry.get("reason", ""))

    def test_reason_truncated_to_first_line(self):
        def boom(*a, **k):
            raise ValueError("line one\nline two\nline three")

        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: [],
            reddit_fn=boom,
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["reddit"]
        reason = entry.get("reason", "")
        self.assertNotIn("\n", reason)
        self.assertIn("line one", reason)


class EmptyResultSignalTests(unittest.TestCase):
    """AC2: A collector returning [] without raising records result_count:0."""

    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }
        self.competitors = [_core(1, "Habit Tracker", 5000)]

    def test_ok_source_with_results_has_count(self):
        def sub_fn(cid, **_k):
            return f"Subtitle for {cid}"

        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=sub_fn,
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: ["100", "101"],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_subtitle"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry.get("result_count"), 1)  # 1 competitor enriched

    def test_chart_source_has_result_count(self):
        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: ["100", "101", "102"],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_rss_charts"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["result_count"], 3)

    def test_suggest_source_with_zero_results_is_ok_with_zero(self):
        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: [],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],  # returns empty
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_search_suggest"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["result_count"], 0)

    def test_suggest_source_with_five_results_has_count_five(self):
        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: [],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: ["a", "b", "c", "d", "e"],
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_search_suggest"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["result_count"], 5)


class AppleSimilarHonestyTests(unittest.TestCase):
    """AC3: apple_similar false-OK closed."""

    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }
        self.competitors = [_core(1, "Strong App", 5000)]

    def test_similar_returning_empty_list_from_successful_browser_is_unavailable(self):
        def sim_fn(cid, **_k):
            return []  # browser succeeded but found no similar apps

        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=sim_fn,
            chart_fn=lambda *a, **k: [],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_similar"]
        self.assertEqual(entry["status"], "unavailable")
        self.assertIn("empty", entry.get("reason", "").lower())

    def test_similar_raising_exception_is_unavailable_with_reason(self):
        def boom_sim(cid, **_k):
            raise RuntimeError("browser timeout")

        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=boom_sim,
            chart_fn=lambda *a, **k: [],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_similar"]
        self.assertEqual(entry["status"], "unavailable")
        self.assertIn("browser timeout", entry.get("reason", ""))

    def test_similar_returning_at_least_one_id_is_ok(self):
        def sim_fn(cid, **_k):
            return {"1": ["91"]}.get(str(cid), [])

        def lookup_fn(sid, **_k):
            if sid == "91":
                return {
                    "trackId": 91,
                    "trackName": "Niche App",
                    "primaryGenreName": "Health & Fitness",
                    "userRatingCount": 50,
                    "description": "niche habit tool",
                    "formattedPrice": "Gratis",
                    "price": 0.0,
                }
            return {}

        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=sim_fn,
            chart_fn=lambda *a, **k: [],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lookup_fn,
        )
        entry = out["source_status"]["apple_similar"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["result_count"], 1)


class NonJSONDriftTests(unittest.TestCase):
    """AC4: Non-JSON HTML body detected and raised in search_suggest."""

    HTML_FIXTURE = (
        b'<HTML><HEAD><TITLE>Connecting to the iTunes Store</TITLE></HEAD>'
        b'<BODY><P>Connecting to the iTunes Store</P></BODY></HTML>'
    )

    def test_html_body_not_valid_json(self):
        import json
        with self.assertRaises(json.JSONDecodeError):
            json.loads(self.HTML_FIXTURE.decode("utf-8"))

    def test_collect_with_fake_fetch_that_raises_on_html(self):
        """collect_apple: inject a suggest_fn that raises ValueError on HTML."""

        def suggest_raises(*a, **k):
            raise ValueError("non-JSON response")

        config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }
        competitors = [_core(1, "Habit Tracker", 5000)]

        out = collect.collect_apple(
            config, competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: [],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=suggest_raises,
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_search_suggest"]
        self.assertEqual(entry["status"], "unavailable")
        self.assertIn("non-JSON", entry.get("reason", ""))


class NeverBlockingPreservedTests(unittest.TestCase):
    """AC7: Never-blocking holds — no new source can crash the run."""

    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }
        self.competitors = [_core(1, "Habit Tracker", 5000)]

    def test_all_collectors_crash_but_run_completes(self):
        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            similar_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            chart_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            reddit_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            suggest_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            lookup_fn=lambda *a, **k: {},
        )
        self.assertIn("apple_subtitle", out["source_status"])
        self.assertIn("apple_similar", out["source_status"])
        self.assertIn("apple_rss_charts", out["source_status"])
        self.assertIn("reddit", out["source_status"])
        self.assertIn("apple_search_suggest", out["source_status"])
        self.assertTrue(out["competitors"])  # base competitors survive

    def test_play_collector_all_crash_but_run_completes(self):
        config = dict(self.config)
        config["seed_keywords"] = ["habit"]
        out = collect.collect_play(
            config,
            seed_terms=["habit"],
            search_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            chart_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            similar_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            suggest_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            lookup_fn=lambda *a, **k: {},
        )
        self.assertIn("play_search", out["source_status"])
        self.assertIn("play_charts", out["source_status"])
        self.assertIn("play_similar", out["source_status"])
        self.assertIn("play_search_suggest", out["source_status"])


class SourceSplitReportTests(unittest.TestCase):
    """AC8: _source_split works with structured status entries."""

    def test_source_split_partitions_correctly(self):
        status = {
            "apple_subtitle": {"status": "ok", "result_count": 2},
            "apple_similar": {"status": "unavailable", "reason": "RuntimeError: browser timeout"},
            "apple_rss_charts": {"status": "ok", "result_count": 5},
            "reddit": {"status": "unavailable", "reason": "ModuleNotFoundError: praw"},
        }
        ran, unavailable = report._source_split(status)
        self.assertTrue(any("apple_subtitle" in s for s in ran), f"apple_subtitle not found in {ran}")
        self.assertTrue(any("apple_rss_charts" in s for s in ran))
        self.assertTrue(any("apple_similar" in s for s in unavailable))
        self.assertTrue(any("reddit" in s for s in unavailable))
        self.assertFalse(any("reddit" in s for s in ran))

    def test_source_split_shows_counts_for_ok(self):
        status = {
            "apple_subtitle": {"status": "ok", "result_count": 3},
            "apple_rss_charts": {"status": "ok", "result_count": 0},
        }
        ran, unavailable = report._source_split(status)
        self.assertEqual(len(unavailable), 0)
        self.assertIn("apple_subtitle (3)", ran)
        self.assertIn("apple_rss_charts (0)", ran)

    def test_source_split_shows_reasons_for_unavailable(self):
        status = {
            "reddit": {"status": "unavailable", "reason": "ModuleNotFoundError: praw"},
        }
        ran, unavailable = report._source_split(status)
        self.assertEqual(len(ran), 0)
        self.assertIn("ModuleNotFoundError: praw", unavailable[0])


class ENWithoutENMarketTests(unittest.TestCase):
    """AC6: EN-without-EN-market caveat in report."""

    NOW = datetime.datetime(2026, 6, 26, 12, 0, 0)

    def _config(self, **overrides):
        base = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "language": "de",
            "seed_keywords": ["habit", "tracker"],
        }
        base.update(overrides)
        return base

    def _competitors(self):
        return [
            {"id": "1", "title": "Habit Tracker", "developer": "DevA",
             "category": "health_fitness", "rating_avg": 4.5, "rating_count": 1000,
             "price_model": "free", "subtitle": "Daily Routine", "discovery": "chart/search"},
        ]

    def _keywords(self):
        return [
            {"term": "habit", "competition": 20, "relevance": 80, "opportunity": 64,
             "split": "primary-candidate", "is_gap": False, "suggest": True},
        ]

    def test_caveat_when_en_language_with_non_us_country(self):
        body = report.build_report(
            self._config(country="de", language="en"),
            self._competitors(), self._keywords(), now=self.NOW,
        )
        self.assertIn("EN", body)
        caveat = "Language is EN but country is not US"
        self.assertIn(caveat, body)

    def test_no_caveat_when_us_country_with_en_language(self):
        body = report.build_report(
            self._config(country="us", language="en"),
            self._competitors(), self._keywords(), now=self.NOW,
        )
        caveat = "Language is EN but country is not US"
        self.assertNotIn(caveat, body)

    def test_no_caveat_when_de_country_with_de_language(self):
        body = report.build_report(
            self._config(country="de", language="de"),
            self._competitors(), self._keywords(), now=self.NOW,
        )
        caveat = "Language is EN but country is not US"
        self.assertNotIn(caveat, body)

    def test_caveat_also_appears_in_executive_summary(self):
        body = report.build_report(
            self._config(country="de", language="en"),
            self._competitors(), self._keywords(), now=self.NOW,
        )
        exec_start = body.index("## 1. Executive Summary")
        exec_end = body.index("## 2. Competitive Landscape")
        exec_section = body[exec_start:exec_end]
        caveat = "Language is EN but country is not US"
        self.assertIn(caveat, exec_section)


class SourceHealthBoardTests(unittest.TestCase):
    """AC5: Per-source result counts in summary / source-health board."""

    NOW = datetime.datetime(2026, 6, 26, 12, 0, 0)

    def _config(self):
        return {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "language": "de",
            "seed_keywords": ["habit"],
        }

    def _competitors(self):
        return [
            {"id": "1", "title": "Habit Tracker", "developer": "DevA",
             "category": "health_fitness", "rating_avg": 4.5, "rating_count": 1000,
             "price_model": "free", "subtitle": "", "discovery": "chart/search"},
        ]

    def _keywords(self):
        return [
            {"term": "habit", "competition": 20, "relevance": 80, "opportunity": 64,
             "split": "primary-candidate", "is_gap": False, "suggest": True},
        ]

    def test_source_health_board_in_methodology_section(self):
        status = {
            "apple_subtitle": {"status": "ok", "result_count": 3},
            "apple_similar": {"status": "unavailable",
                              "reason": "RuntimeError: browser timeout"},
            "apple_rss_charts": {"status": "ok", "result_count": 5},
        }
        body = report.build_report(
            self._config(), self._competitors(), self._keywords(),
            now=self.NOW, source_status=status,
        )
        self.assertIn("Source Health", body)
        self.assertIn("ok (3)", body)
        self.assertIn("ok (5)", body)
        self.assertIn("unavailable", body)
        self.assertIn("browser timeout", body)


class DeterminismAfterStatusChangeTests(unittest.TestCase):
    """Determinism: same input, same output — even with structured status."""

    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }
        self.competitors = [_core(1, "Habit Tracker", 5000), _core(2, "Daily Habit", 3000)]

    def test_deterministic_output_with_structured_status(self):
        kwargs = dict(
            subtitle_fn=lambda cid, **k: f"S{cid}",
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: ["1"],
            reddit_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: ["x"],
            lookup_fn=lambda *a, **k: {},
        )
        a = collect.collect_apple(self.config, self.competitors, **kwargs)
        b = collect.collect_apple(self.config, self.competitors, **kwargs)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
