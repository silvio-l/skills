#!/usr/bin/env python3
"""Tests for the deep Apple collection orchestration (slice 02).

Run from the repo root:
    python3 tests/aso-research/test_collect.py

The live collectors are NOT unit-tested (they fail loud, formats rot).
This tests the **orchestration logic** with injectable fake collectors:
source-status tracking (a failing source -> "unavailable"), never-blocking
(an exception in one collector never aborts the run), niche-competitor
merge + de-dup from the similar-apps hop, and subtitle enrichment.

Lives outside `skills/` on purpose (see CLAUDE.md "Tooling and testing").
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import collect  # noqa: E402
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


class CollectAppleTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }
        self.competitors = [_core(1, "Habit Tracker", 5000), _core(2, "Daily Habit", 3000)]

    def test_subtitle_enrichment_fills_slot(self):
        def sub_fn(cid, **_k):
            return f"Subtitle for {cid}"

        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=sub_fn,
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
        )
        by_id = {c["id"]: c for c in out["competitors"]}
        self.assertEqual(by_id["1"]["subtitle"], "Subtitle for 1")
        entry = out["source_status"]["apple_subtitle"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["result_count"], 2)

    def test_failing_subtitle_marked_unavailable_and_never_blocks(self):
        def boom(cid, **_k):
            raise RuntimeError("browser down")

        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=boom,
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
        )
        entry = out["source_status"]["apple_subtitle"]
        self.assertEqual(entry["status"], "unavailable")
        self.assertIn("browser down", entry["reason"])
        # pipeline still produced competitors
        self.assertTrue(out["competitors"])

    def test_similar_hop_adds_niche_competitors_deduped(self):
        # competitor id=1 similar to niche ids 91,92 ; id=2 similar to 91 (dup)
        def sim_fn(cid, **_k):
            return {"1": ["91", "92"], "2": ["91"]}.get(str(cid), [])

        def lookup_fn(sid, **_k):
            if sid in ("91", "92"):
                return {
                    "trackId": int(sid),
                    "trackName": f"Niche App {sid}",
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
            suggest_fn=lambda *a, **k: [],
            lookup_fn=lookup_fn,
        )
        ids = [c["id"] for c in out["competitors"]]
        self.assertIn("91", ids)
        self.assertIn("92", ids)
        # deduped: 91 appears once even though two sources listed it
        self.assertEqual(ids.count("91"), 1)
        entry = out["source_status"]["apple_similar"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["result_count"], 3)

    def test_suggest_and_chart_collected(self):
        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: ["100", "101"],
            suggest_fn=lambda *a, **k: ["habit tracker", "routine"],
            lookup_fn=lambda *a, **k: {},
        )
        self.assertEqual(out["chart_ids"], ["100", "101"])
        self.assertEqual(out["suggest_terms"], ["habit tracker", "routine"])
        for src in ("apple_rss_charts", "apple_search_suggest"):
            self.assertEqual(out["source_status"][src]["status"], "ok")

    def test_exception_in_any_collector_never_aborts(self):
        out = collect.collect_apple(
            self.config, self.competitors,
            subtitle_fn=lambda *a, **k: "",
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            suggest_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            lookup_fn=lambda *a, **k: {},
        )
        self.assertEqual(out["source_status"]["apple_rss_charts"]["status"], "unavailable")
        self.assertEqual(out["source_status"]["apple_search_suggest"]["status"], "unavailable")
        self.assertEqual(out["chart_ids"], [])
        self.assertEqual(out["suggest_terms"], [])

    def test_deterministic_output(self):
        kwargs = dict(
            subtitle_fn=lambda cid, **k: f"S{cid}",
            similar_fn=lambda *a, **k: [],
            chart_fn=lambda *a, **k: ["1"],
            suggest_fn=lambda *a, **k: ["x"],
            lookup_fn=lambda *a, **k: {},
        )
        a = collect.collect_apple(self.config, self.competitors, **kwargs)
        b = collect.collect_apple(self.config, self.competitors, **kwargs)
        self.assertEqual(a, b)


class ExtractAndScoreTests(unittest.TestCase):
    def test_runs_engine_over_corpus(self):
        comps = [_core(1, "Habit Tracker"), _core(2, "Daily Habit")]
        config = {"description": "habit tracker", "category": "health_fitness", "app_name": "X"}
        out = collect.extract_and_score(comps, config, suggest_terms=["habit tracker"])
        self.assertTrue(out["keywords"])
        self.assertEqual(out["keywords"], sorted(out["keywords"], key=lambda e: (-e["opportunity"], -e["relevance"], e["term"])))


if __name__ == "__main__":
    unittest.main()
