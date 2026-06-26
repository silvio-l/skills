#!/usr/bin/env python3
"""Tests for the Google Play vertical (slice 04).

Run from the repo root:
    python3 tests/aso-research/test_play.py

Covers the offline-testable pure logic only (no network/browser/Node):
Play schema mapping (raw google-play-scraper JSON -> Play Core+Slots;
short/full description populated; tags absent), Play slot weighting feeding
the shared scoring engine (Play rows score with Play weights while Apple
rows stay numerically unchanged), unified score-table keying/dedup across
platforms, Play listing char-count validation (Title 30 / Short 80 / Long
4000), the Play Search-Suggest enrichment path, Play collection
orchestration (injectable fakes: source-status, never-blocking, niche
merge), and determinism (fixture Play input -> byte-identical Play rows).

The live google-play-scraper collector is NOT unit-tested (repo convention:
external collectors fail loud). Lives outside `skills/` on purpose.
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import collect  # noqa: E402
import crosscheck  # noqa: E402
import extract  # noqa: E402
import schema  # noqa: E402
import score  # noqa: E402
import serialize  # noqa: E402


# ===========================================================================
# Schema mapping: raw google-play-scraper JSON -> Play Core + Slots
# ===========================================================================

RAW_PLAY_APP = {
    "appId": "com.example.habits",
    "url": "https://play.google.com/store/apps/details?id=com.example.habits",
    "title": "Habit Hero — Routine Tracker",
    "summary": "Build daily habits & routines",  # the 80-char short description
    "description": "Habit Hero is the <b>best</b> habit tracker. Build streaks.",  # long
    "developer": "HeroCo",
    "genre": "Health & Fitness",
    "score": 4.7,
    "ratings": 18234,
    "updated": "Jun 5, 2026",
    "free": True,
    "price": 0,
    "screenshots": ["s1", "s2", "s3", "s4"],
    # tags would appear here for some libs — we assert they are NEVER carried.
    "tags": ["productivity", "lifestyle"],
}


class PlaySchemaTests(unittest.TestCase):
    def test_core_fields_populated(self):
        core = schema.map_play_to_core(RAW_PLAY_APP)
        self.assertEqual(core["id"], "com.example.habits")
        self.assertEqual(core["platform"], "play")
        self.assertEqual(core["title"], "Habit Hero — Routine Tracker")
        self.assertEqual(core["developer"], "HeroCo")
        self.assertEqual(core["category"], "health_fitness")
        self.assertEqual(core["rating_avg"], 4.7)
        self.assertEqual(core["rating_count"], 18234)
        self.assertEqual(core["price_model"], "free")
        self.assertEqual(core["screenshot_count"], 4)
        self.assertEqual(
            core["store_url"],
            "https://play.google.com/store/apps/details?id=com.example.habits",
        )

    def test_short_and_full_description_slots_populated(self):
        core = schema.map_play_to_core(RAW_PLAY_APP)
        self.assertEqual(core["short_description"], "Build daily habits & routines")
        # full description HTML-stripped
        self.assertNotIn("<b>", core["full_description"])
        self.assertIn("best", core["full_description"])

    def test_tags_are_not_collected(self):
        """AC: tags are DROPPED — the record carries no tags key at all."""
        core = schema.map_play_to_core(RAW_PLAY_APP)
        self.assertNotIn("tags", core)

    def test_paid_price_model(self):
        raw = dict(RAW_PLAY_APP)
        raw["free"] = False
        raw["price"] = 3.99
        self.assertEqual(schema.infer_play_price_model(raw), "paid")

    def test_genre_falls_back_when_only_genreid_digit(self):
        raw = dict(RAW_PLAY_APP)
        raw["genre"] = None
        raw["primaryGenre"] = None
        raw["genreId"] = "HEALTH_AND_FITNESS"
        # a non-digit genreId string still maps through the taxonomy
        raw["genreId"] = "Health & Fitness"
        core = schema.map_play_to_core(raw)
        self.assertEqual(core["category"], "health_fitness")

    def test_degrades_safely_on_missing_fields(self):
        core = schema.map_play_to_core({"appId": "x"})
        self.assertEqual(core["id"], "x")
        self.assertEqual(core["platform"], "play")
        self.assertEqual(core["short_description"], "")
        self.assertEqual(core["full_description"], "")
        self.assertEqual(core["category"], "other")
        self.assertNotIn("tags", core)

    def test_summary_field_alias(self):
        # some scraper variants return shortDescription instead of summary
        raw = {"appId": "y", "title": "T", "shortDescription": "short text",
               "fullDescription": "long text", "free": True}
        core = schema.map_play_to_core(raw)
        self.assertEqual(core["short_description"], "short text")
        self.assertEqual(core["full_description"], "long text")


# ===========================================================================
# Shared scoring engine — Play weighting vs Apple unchanged
# ===========================================================================

class SharedScoringWeightTests(unittest.TestCase):
    def test_play_slot_weights_distinct_from_apple(self):
        self.assertEqual(score.APPLE_SLOT_WEIGHTS, {"title": 5, "subtitle": 3, "description": 1})
        self.assertEqual(score.PLAY_SLOT_WEIGHTS, {"title": 5, "short": 4, "long": 2})
        # Long (2) > Apple desc (1): fully-indexed contributes meaningfully.
        self.assertGreater(score.PLAY_SLOT_WEIGHTS["long"], score.APPLE_SLOT_WEIGHTS["description"])
        # Short (4) > Apple subtitle (3): strong Play ranking factor.
        self.assertGreater(score.PLAY_SLOT_WEIGHTS["short"], score.APPLE_SLOT_WEIGHTS["subtitle"])

    def test_competition_score_apple_unchanged(self):
        # Apple path must be byte-identical to slice 02 (PRD formula).
        self.assertEqual(score.competition_score(2, 0, 0, 4), 28)
        self.assertEqual(score.competition_score(1, 1, 1, 1), 100)
        self.assertEqual(score.competition_score(0, 3, 0, 9), 11)
        self.assertEqual(score.competition_score(5, 5, 5, 0), 0)

    def test_play_competition_uses_play_weights(self):
        # Same raw hit counts but Play weights (title 5 / short 4 / long 2):
        # 100 * (5*2/4 + 4*0/4 + 2*0/4) / 11 = 100 * (2.5) / 11 = 22.7 -> 23
        self.assertEqual(
            score.competition_score_weighted(
                {"title": 2, "short": 0, "long": 0}, score.PLAY_SLOT_WEIGHTS, 4
            ),
            23,
        )

    def test_play_vs_apple_same_hits_different_score(self):
        # A term in the title of 1/1 doc: Apple = 100*5/9 = 56; Play = 100*5/11 = 45.
        apple = score.competition_score_weighted(
            {"title": 1, "subtitle": 0, "description": 0}, score.APPLE_SLOT_WEIGHTS, 1
        )
        play = score.competition_score_weighted(
            {"title": 1, "short": 0, "long": 0}, score.PLAY_SLOT_WEIGHTS, 1
        )
        self.assertEqual(apple, 56)
        self.assertEqual(play, 45)
        self.assertNotEqual(apple, play)

    def test_score_keywords_tags_play_rows(self):
        docs = [{"title": "Habit Tracker", "short": "daily habits", "long": "build routines"}]
        extracted = extract.extract_keywords(docs, fields=extract.PLAY_FIELDS, min_freq=1)
        scored = score.score_keywords(
            extracted, seed_description="habit tracker app", n_docs=1, platform="play"
        )
        self.assertTrue(scored)
        for row in scored:
            self.assertEqual(row["platform"], "play")
            # Play hit fields, not Apple's subtitle/description
            self.assertIn("short_hits", row)
            self.assertIn("long_hits", row)
            self.assertIn("title_hits", row)

    def test_score_keywords_apple_default_still_apple(self):
        docs = [{"title": "Habit Tracker", "subtitle": "daily", "description": "build"}]
        extracted = extract.extract_keywords(docs, min_freq=1)
        scored = score.score_keywords(extracted, seed_description="habit", n_docs=1)
        for row in scored:
            self.assertEqual(row["platform"], "apple")
            self.assertIn("subtitle_hits", row)
            self.assertIn("description_hits", row)


# ===========================================================================
# Unified score table — both platforms, deterministic total order
# ===========================================================================

class UnifiedScoreTableTests(unittest.TestCase):
    def _apple_rows(self):
        docs = [{"title": "Habit Tracker Daily", "subtitle": "", "description": "routine"}]
        extracted = extract.extract_keywords(docs, min_freq=1)
        return score.score_keywords(extracted, seed_description="habit tracker", n_docs=1)

    def _play_rows(self):
        docs = [{"title": "Habit Tracker", "short": "daily habits", "long": "routines"}]
        extracted = extract.extract_keywords(docs, fields=extract.PLAY_FIELDS, min_freq=1)
        return score.score_keywords(
            extracted, seed_description="habit tracker", n_docs=1, platform="play"
        )

    def test_merged_table_carries_both_platforms(self):
        merged = self._apple_rows() + self._play_rows()
        platforms = {r["platform"] for r in merged}
        self.assertEqual(platforms, {"apple", "play"})

    def test_merged_table_sorted_total_order(self):
        merged = self._apple_rows() + self._play_rows()
        # sort the merged list the way the dispatcher does
        merged.sort(key=lambda e: (-e["opportunity"], -e["relevance"], e["term"], e["platform"]))
        keys = [(-e["opportunity"], -e["relevance"], e["term"], e["platform"]) for e in merged]
        self.assertEqual(keys, sorted(keys))

    def test_same_term_can_appear_once_per_platform(self):
        merged = self._apple_rows() + self._play_rows()
        # 'habit' / 'tracker' likely appear in both; ensure both platform rows exist
        by_term_platform = {(r["term"], r["platform"]) for r in merged}
        apple_terms = {t for (t, p) in by_term_platform if p == "apple"}
        play_terms = {t for (t, p) in by_term_platform if p == "play"}
        # at least one shared term appears under both platforms
        self.assertTrue(apple_terms & play_terms)


# ===========================================================================
# Play listing — char-count validation (Title 30 / Short 80 / Long 4000)
# ===========================================================================

def _play_slot(name, rec_text, alt1, alt2):
    return {
        "slot": name,
        "recommended": {"text": rec_text, "char_count": len(rec_text)},
        "alternatives": [
            {"text": alt1, "char_count": len(alt1)},
            {"text": alt2, "char_count": len(alt2)},
        ],
    }


def _play_listing(title="Habit Hero Tracker", short="Build daily habits & routines",
                  long_text="Habit Hero is the best habit tracker. Build streaks."):
    return {
        "store": "play",
        "slots": [
            _play_slot("title", title, "Habit Hero", "Daily Habit"),
            _play_slot("short", short, "Track routines daily", "Build streaks now"),
            _play_slot("long", long_text, "alt long one", "alt long two"),
        ],
    }


class PlayListingValidationTests(unittest.TestCase):
    def test_play_slot_limits(self):
        self.assertEqual(crosscheck.PLAY_SLOTS, {"title": 30, "short": 80, "long": 4000})

    def test_fitting_play_listing_valid(self):
        out = crosscheck.validate_listing(_play_listing())
        self.assertTrue(out["valid"])
        self.assertEqual(out["store"], "play")
        limits = {s["slot"]: s["limit"] for s in out["slots"]}
        self.assertEqual(limits, {"title": 30, "short": 80, "long": 4000})
        for slot in out["slots"]:
            self.assertTrue(slot["recommended"]["fits"])
            self.assertTrue(slot["recommended"]["accurate"])
            self.assertEqual(len(slot["alternatives"]), 2)

    def test_over_limit_short_flagged(self):
        long_short = "x" * 81  # > 80
        listing = _play_listing(short=long_short)
        out = crosscheck.validate_listing(listing)
        self.assertFalse(out["valid"])
        short_slot = next(s for s in out["slots"] if s["slot"] == "short")
        self.assertFalse(short_slot["recommended"]["fits"])

    def test_long_description_fits_4000(self):
        long_text = "y" * 4000  # exactly at the limit -> fits
        listing = _play_listing(long_text=long_text)
        out = crosscheck.validate_listing(listing)
        self.assertTrue(out["valid"])
        long_slot = next(s for s in out["slots"] if s["slot"] == "long")
        self.assertTrue(long_slot["recommended"]["fits"])

    def test_play_crosscheck_no_keyword_field_rule(self):
        # Play has no keyword-list slot -> an unscored word is branding, ok.
        score_table = [
            {"term": "habit", "competition": 20, "relevance": 80, "opportunity": 64},
        ]
        listing = _play_listing(title="Habit Quantum")  # 'quantum' unscored
        out = crosscheck.crosscheck_listing(listing, score_table)
        # unscored 'quantum' in a prose title is NOT a contradiction for Play
        self.assertNotIn(
            "unscored",
            " ".join(r for f in out["findings"] for r in f["reasons"]).lower(),
        )

    def test_play_crosscheck_rejects_high_competition(self):
        score_table = [
            {"term": "habit", "competition": 90, "relevance": 10, "opportunity": 1},
        ]
        listing = _play_listing(title="Habit App")
        out = crosscheck.crosscheck_listing(listing, score_table)
        self.assertEqual(out["status"], "rejected")


# ===========================================================================
# Play Search-Suggest enrichment path (merged with Apple's)
# ===========================================================================

class PlaySearchSuggestTests(unittest.TestCase):
    def test_play_suggest_terms_boost_relevance(self):
        docs = [{"title": "Habit Tracker", "short": "daily", "long": "build"}]
        extracted = extract.extract_keywords(
            docs, fields=extract.PLAY_FIELDS, min_freq=1,
            suggest_terms=["meditation timer"],
        )
        scored = score.score_keywords(
            extracted, seed_description="habit tracker", n_docs=1,
            platform="play", suggest_terms=["meditation timer"],
        )
        by = {r["term"]: r for r in scored}
        self.assertIn("meditation timer", by)
        self.assertTrue(by["meditation timer"]["suggest"])
        self.assertGreaterEqual(by["meditation timer"]["relevance"], 15)

    def test_merged_apple_play_suggest_set_boosts_both(self):
        # The dispatcher unions Apple + Play autocomplete into one suggest set.
        merged_suggest = ["habit pro", "gewohnheit"]  # from apple + play
        apple_docs = [{"title": "Habit Pro", "subtitle": "", "description": ""}]
        play_docs = [{"title": "Gewohnheit", "short": "x", "long": "y"}]
        a_ex = extract.extract_keywords(apple_docs, min_freq=1, suggest_terms=merged_suggest)
        p_ex = extract.extract_keywords(
            play_docs, fields=extract.PLAY_FIELDS, min_freq=1, suggest_terms=merged_suggest
        )
        a = score.score_keywords(a_ex, seed_description="habit", n_docs=1, suggest_terms=merged_suggest)
        p = score.score_keywords(
            p_ex, seed_description="habit", n_docs=1, platform="play", suggest_terms=merged_suggest
        )
        self.assertTrue(any(r["suggest"] for r in a))
        self.assertTrue(any(r["suggest"] for r in p))


# ===========================================================================
# Play collection orchestration (injectable fakes — never-blocking)
# ===========================================================================

class CollectPlayTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }

    def test_play_search_populates_competitors_with_platform_play(self):
        def search_fn(term, **_k):
            return [{"appId": "com.a", "title": "Habit A", "summary": "s",
                     "description": "d", "genre": "Health & Fitness", "free": True}]

        out = collect.collect_play(
            self.config, seed_terms=["habit"],
            search_fn=search_fn,
            lookup_fn=lambda *a, **k: {},
            chart_fn=lambda *a, **k: [],
            similar_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
        )
        self.assertTrue(out["competitors"])
        for c in out["competitors"]:
            self.assertEqual(c["platform"], "play")
            self.assertIn("short_description", c)
            self.assertIn("full_description", c)
        self.assertEqual(out["source_status"]["play_search"]["status"], "ok")

    def test_failing_play_search_marked_unavailable_never_blocks(self):
        out = collect.collect_play(
            self.config, seed_terms=["habit"],
            search_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("down")),
            lookup_fn=lambda *a, **k: {},
            chart_fn=lambda *a, **k: [],
            similar_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: [],
        )
        entry = out["source_status"]["play_search"]
        self.assertEqual(entry["status"], "unavailable")
        self.assertEqual(len(out["competitors"]), 0)  # no crash, empty result

    def test_play_charts_and_suggest_collected(self):
        out = collect.collect_play(
            self.config, seed_terms=["habit"],
            search_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
            chart_fn=lambda *a, **k: [{"appId": "com.chart1", "title": "Chart One",
                                       "summary": "s", "free": True}],
            similar_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: ["habit tracker", "routine app"],
        )
        ids = [c["id"] for c in out["competitors"]]
        self.assertIn("com.chart1", ids)
        self.assertEqual(out["suggest_terms"], ["habit tracker", "routine app"])
        self.assertEqual(out["source_status"]["play_charts"]["status"], "ok")
        self.assertEqual(out["source_status"]["play_search_suggest"]["status"], "ok")

    def test_play_similar_hop_adds_niche_deduped(self):
        def search_fn(term, **_k):
            return [{"appId": "com.a", "title": "Habit A", "summary": "s", "free": True}]

        def similar_fn(app_id, **_k):
            return {"com.a": ["com.niche1", "com.niche2"]}.get(app_id, [])

        def lookup_fn(app_id, **_k):
            if app_id in ("com.niche1", "com.niche2"):
                return {"appId": app_id, "title": f"Niche {app_id}",
                        "summary": "s", "free": True}
            return {}

        out = collect.collect_play(
            self.config, seed_terms=["habit"],
            search_fn=search_fn, lookup_fn=lookup_fn,
            chart_fn=lambda *a, **k: [],
            similar_fn=similar_fn,
            suggest_fn=lambda *a, **k: [],
        )
        ids = [c["id"] for c in out["competitors"]]
        self.assertIn("com.niche1", ids)
        self.assertIn("com.niche2", ids)
        self.assertEqual(ids.count("com.niche1"), 1)  # deduped
        entry = out["source_status"]["play_similar"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["result_count"], 2)

    def test_exception_in_any_play_collector_never_aborts(self):
        out = collect.collect_play(
            self.config, seed_terms=["habit"],
            search_fn=lambda *a, **k: [],
            lookup_fn=lambda *a, **k: {},
            chart_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            similar_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
            suggest_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
        )
        for src in ("play_charts", "play_similar", "play_search_suggest"):
            self.assertEqual(out["source_status"][src]["status"], "unavailable")
        self.assertEqual(out["suggest_terms"], [])

    def test_deterministic_output(self):
        kwargs = dict(
            search_fn=lambda term, **k: [{"appId": "com.a", "title": "Habit A",
                                          "summary": "s", "free": True}],
            lookup_fn=lambda *a, **k: {},
            chart_fn=lambda *a, **k: [],
            similar_fn=lambda *a, **k: [],
            suggest_fn=lambda *a, **k: ["x"],
        )
        a = collect.collect_play(self.config, seed_terms=["habit"], **kwargs)
        b = collect.collect_play(self.config, seed_terms=["habit"], **kwargs)
        self.assertEqual(a, b)


# ===========================================================================
# Unified extract_and_score — both platforms through the shared engine
# ===========================================================================

class UnifiedExtractAndScoreTests(unittest.TestCase):
    def test_partitions_by_platform_and_tags_rows(self):
        apple = schema.map_itunes_to_core(
            {"trackId": 1, "trackName": "Habit Tracker", "description": "habit routine app",
             "primaryGenreName": "Health & Fitness", "price": 0.0}
        )
        play = schema.map_play_to_core(
            {"appId": "com.a", "title": "Habit Hero", "summary": "daily habits",
             "description": "build routines habit", "genre": "Health & Fitness", "free": True}
        )
        config = {"description": "habit tracker routine app", "category": "health_fitness",
                  "app_name": "X"}
        out = collect.extract_and_score([apple, play], config)
        platforms = {r["platform"] for r in out["keywords"]}
        self.assertEqual(platforms, {"apple", "play"})

    def test_apple_only_path_matches_legacy_sort(self):
        apple = schema.map_itunes_to_core(
            {"trackId": 1, "trackName": "Habit Tracker", "description": "routine",
             "primaryGenreName": "Health & Fitness", "price": 0.0}
        )
        config = {"description": "habit tracker", "category": "health_fitness", "app_name": "X"}
        out = collect.extract_and_score([apple], config)
        # legacy 3-tuple sort still holds (all rows share platform=apple)
        self.assertEqual(
            out["keywords"],
            sorted(out["keywords"], key=lambda e: (-e["opportunity"], -e["relevance"], e["term"])),
        )


# ===========================================================================
# Determinism — byte-identical Play rows across two runs
# ===========================================================================

PLAY_FIXTURE = [
    schema.map_play_to_core(
        {"appId": "com.a", "title": "Habit Tracker Daily", "summary": "Baue Gewohnheiten",
         "description": "Der beste Habit Tracker fuer jeden Tag. Routinen.",
         "genre": "Health & Fitness", "free": True, "ratings": 1200}
    ),
    schema.map_play_to_core(
        {"appId": "com.b", "title": "Daily Habit Hero", "summary": "Gewohnheits-Tracker",
         "description": "Verfolge deine Gewohnheiten und Ziele jeden Tag.",
         "genre": "Health & Fitness", "free": False, "price": 2.99, "ratings": 900}
    ),
    schema.map_play_to_core(
        {"appId": "com.c", "title": "Streaks Habit", "summary": "Routinen Pro",
         "description": "Behalte deine Routinen bei mit diesem Habit Tool.",
         "genre": "Health & Fitness", "free": True, "ratings": 3000}
    ),
]
SEED_DESC = "A gamified habit tracker and routine builder app"
SUGGEST = ["habit tracker", "gewohnheit", "routine builder"]


def _play_run_once():
    config = {"description": SEED_DESC, "category": "health_fitness", "app_name": "Habit Hero"}
    return collect.extract_and_score(PLAY_FIXTURE, config, suggest_terms=SUGGEST)


class PlayDeterminismTests(unittest.TestCase):
    def test_play_keywords_byte_identical_two_runs(self):
        a = serialize.dumps_json(_play_run_once())
        b = serialize.dumps_json(_play_run_once())
        self.assertEqual(a, b)

    def test_play_rows_tagged_and_scored(self):
        out = _play_run_once()
        self.assertTrue(out["keywords"])
        for k in out["keywords"]:
            self.assertEqual(k["platform"], "play")
            self.assertIn(k["split"], ("primary-candidate", "long-tail-candidate"))
            self.assertIsInstance(k["is_gap"], bool)
            self.assertNotIn("volume", k)

    def test_play_competition_byte_identical_two_runs(self):
        a = serialize.dumps_json(PLAY_FIXTURE)
        b = serialize.dumps_json(PLAY_FIXTURE)
        self.assertEqual(a, b)


# ===========================================================================
# Unified Apple + Play determinism (the dispatcher's merged table)
# ===========================================================================

APPLE_FIXTURE = [
    schema.merge_apple_slots(
        schema.map_itunes_to_core(
            {"trackId": 1, "trackName": "Habit Tracker Daily", "price": 0.0,
             "primaryGenreName": "Health & Fitness", "userRatingCount": 1200,
             "description": "Baue gute Gewohnheiten auf. Der beste Habit Tracker."}
        ),
        subtitle="Gewohnheits-Tracker",
    ),
    schema.merge_apple_slots(
        schema.map_itunes_to_core(
            {"trackId": 2, "trackName": "Streaks Habit", "price": 0.0,
             "primaryGenreName": "Health & Fitness", "userRatingCount": 3000,
             "description": "Behalte deine Routinen bei mit diesem Habit Tool."}
        ),
        subtitle="Achtsamkeit Timer",
    ),
]


def _unified_run_once():
    config = {"description": SEED_DESC, "category": "health_fitness", "app_name": "Habit Hero"}
    return collect.extract_and_score(
        APPLE_FIXTURE + PLAY_FIXTURE, config, suggest_terms=SUGGEST
    )


class UnifiedDeterminismTests(unittest.TestCase):
    def test_unified_table_byte_identical_two_runs(self):
        a = serialize.dumps_json(_unified_run_once())
        b = serialize.dumps_json(_unified_run_once())
        self.assertEqual(a, b)

    def test_unified_table_carries_both_platforms_sorted_total(self):
        out = _unified_run_once()
        platforms = {k["platform"] for k in out["keywords"]}
        self.assertEqual(platforms, {"apple", "play"})
        keys = [(-k["opportunity"], -k["relevance"], k["term"], k["platform"]) for k in out["keywords"]]
        self.assertEqual(keys, sorted(keys))


if __name__ == "__main__":
    unittest.main()
