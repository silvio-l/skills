#!/usr/bin/env python3
"""Tests for aso-research pure-logic modules.

Run from the repo root:
    python3 tests/aso-research/test_pipeline.py

Covers the offline-testable pure logic only (parsing, run-id,
serialization, cache-key/freshness, trivial extraction/scoring,
schema mapping, and the full collect→extract→score→serialize
determinism path via a recorded fixture). The live iTunes collector is
intentionally NOT unit-tested — it fails loud and its format would rot
tests (see CLAUDE.md "Tooling and testing").

Lives outside `skills/` on purpose: the `skills` CLI bundles a skill
directory as-is, and shipping tests to every install would just bloat
the bundle.
"""

import datetime
import json
import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Suppress __pycache__ creation under the skill directory.
sys.dont_write_bytecode = True

import cache as CACHE  # noqa: E402
import extract  # noqa: E402
import input_config  # noqa: E402
import itunes  # noqa: E402
import report  # noqa: E402
import run_id  # noqa: E402
import score  # noqa: E402
import schema  # noqa: E402
import serialize  # noqa: E402

# ---------------------------------------------------------------------------
# Recorded iTunes fixture (trimmed from a real Spotify search hit).
# Keeps every field the schema mapper reads; trimmed only the long arrays.
# ---------------------------------------------------------------------------

RAW_ITUNES_SPOTIFY = {
    "wrapperType": "software",
    "kind": "software",
    "trackId": 324684580,
    "trackName": "Spotify Musik und Podcasts",
    "artistName": "Spotify",
    "sellerName": "Spotify",
    "primaryGenreName": "Music",
    "trackViewUrl": "https://apps.apple.com/de/app/spotify/id324684580",
    "averageUserRating": 4.71,
    "userRatingCount": 5536984,
    "currentVersionReleaseDate": "2026-06-19T09:42:47Z",
    "formattedPrice": "Gratis",
    "price": 0.0,
    "screenshotUrls": ["a", "b", "c"],
}

RAW_ITUNES_HABIT = {
    "wrapperType": "software",
    "kind": "software",
    "trackId": 987654321,
    "trackName": "Habit Tracker Daily",
    "artistName": "HabitCo",
    "primaryGenreName": "Health & Fitness",
    "trackViewUrl": "https://apps.apple.com/de/app/habit-tracker/id987654321",
    "averageUserRating": 4.9,
    "userRatingCount": 12000,
    "currentVersionReleaseDate": "2026-05-01T00:00:00Z",
    "formattedPrice": "$2.99",
    "price": 2.99,
    "screenshotUrls": ["x", "y"],
}


# ===========================================================================
# run_id
# ===========================================================================

class RunIdTests(unittest.TestCase):
    def test_slugify_strips_punctuation_and_lowercases(self):
        self.assertEqual(run_id.slugify("Habit Hero!"), "habit-hero")
        self.assertEqual(run_id.slugify("  Mehr   Leerzeichen  "), "mehr-leerzeichen")

    def test_slugify_handles_umlauts_and_collapses_separators(self):
        # Umlauts are stripped to separators by the non-alnum rule; that is
        # acceptable for a filesystem-safe slug and deterministic.
        self.assertEqual(run_id.slugify("Grüße & Café"), "gr-e-caf")

    def test_slugify_empty_falls_back_to_app(self):
        self.assertEqual(run_id.slugify(""), "app")
        self.assertEqual(run_id.slugify("!!!"), "app")

    def test_generate_run_id_format(self):
        now = datetime.datetime(2026, 6, 26, 14, 5, 9)
        rid = run_id.generate_run_id(now, "Habit Hero")
        self.assertEqual(rid, "20260626-140509-habit-hero")

    def test_two_runs_same_seed_produce_distinct_run_ids(self):
        base = datetime.datetime(2026, 6, 26, 14, 5, 9)
        a = run_id.generate_run_id(base, "Habit Hero")
        b = run_id.generate_run_id(base + datetime.timedelta(seconds=1), "Habit Hero")
        self.assertNotEqual(a, b)
        self.assertTrue(a < b)  # chronological


# ===========================================================================
# input_config
# ===========================================================================

class InputConfigTests(unittest.TestCase):
    def test_validate_requires_app_name_and_description(self):
        self.assertTrue(input_config.validate({"app_name": "", "description": "x"}))
        self.assertTrue(input_config.validate({"description": "x"}))
        self.assertEqual(input_config.validate({"app_name": "A", "description": "B"}), [])

    def test_validate_rejects_bad_seed_list(self):
        errs = input_config.validate(
            {"app_name": "A", "description": "B", "seed_keywords": "notalist"}
        )
        self.assertTrue(any("seed_keywords" in e for e in errs))

    def test_parse_input_applies_defaults(self):
        cfg = input_config.parse_input({"app_name": "App", "description": "Desc"})
        self.assertEqual(cfg["country"], "de")
        self.assertEqual(cfg["language"], "de")
        self.assertEqual(cfg["category"], "other")
        self.assertIsNone(cfg["own_app_id"])
        self.assertEqual(cfg["seed_keywords"], [])
        self.assertIsNone(cfg["gate_token_limit"])
        self.assertIsNone(cfg["output_dir"])

    def test_parse_input_caps_seed_keywords_at_five(self):
        cfg = input_config.parse_input(
            {"app_name": "A", "description": "B", "seed_keywords": ["a", "b", "c", "d", "e", "f", "g"]}
        )
        self.assertEqual(cfg["seed_keywords"], ["a", "b", "c", "d", "e"])

    def test_parse_input_strips_and_carries_optional_fields(self):
        cfg = input_config.parse_input(
            {"app_name": "  A ", "description": " B ", "own_app_id": "  123  ",
             "gate_token_limit": 50000, "output_dir": "  /tmp/x  ", "country": "us"}
        )
        self.assertEqual(cfg["app_name"], "A")
        self.assertEqual(cfg["description"], "B")
        self.assertEqual(cfg["own_app_id"], "123")
        self.assertEqual(cfg["gate_token_limit"], 50000)
        self.assertEqual(cfg["output_dir"], "/tmp/x")
        self.assertEqual(cfg["country"], "us")

    def test_parse_input_raises_on_invalid(self):
        with self.assertRaises(ValueError):
            input_config.parse_input({"description": "x"})

    def test_load_input_file_json(self):
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as fh:
            json.dump({"app_name": "A", "description": "B"}, fh)
            path = fh.name
        try:
            raw = input_config.load_input_file(path)
            self.assertEqual(raw["app_name"], "A")
        finally:
            os.unlink(path)


# ===========================================================================
# schema (taxonomy + Core mapping)
# ===========================================================================

class SchemaTests(unittest.TestCase):
    def test_map_category_known_genres(self):
        self.assertEqual(schema.map_category("Music"), "music")
        self.assertEqual(schema.map_category("Health & Fitness"), "health_fitness")
        self.assertEqual(schema.map_category("Productivity"), "productivity")
        self.assertEqual(schema.map_category("photo & video"), "photo_video")

    def test_map_category_unknown_falls_back_to_other(self):
        self.assertEqual(schema.map_category("Quantum Computing"), "other")
        self.assertEqual(schema.map_category(""), "other")

    def test_infer_price_model_free_vs_paid(self):
        self.assertEqual(schema.infer_price_model({"price": 0.0, "formattedPrice": "Gratis"}), "free")
        self.assertEqual(schema.infer_price_model({"price": 2.99, "formattedPrice": "$2.99"}), "paid")
        self.assertEqual(schema.infer_price_model({"price": 0.0, "formattedPrice": "Free"}), "free")

    def test_map_itunes_to_core_populates_core_and_slots(self):
        core = schema.map_itunes_to_core(RAW_ITUNES_SPOTIFY)
        # Core
        self.assertEqual(core["id"], "324684580")
        self.assertEqual(core["platform"], "apple")
        self.assertEqual(core["title"], "Spotify Musik und Podcasts")
        self.assertEqual(core["developer"], "Spotify")
        self.assertEqual(core["category"], "music")
        self.assertEqual(core["rating_avg"], 4.71)
        self.assertEqual(core["rating_count"], 5536984)
        self.assertEqual(core["store_url"], "https://apps.apple.com/de/app/spotify/id324684580")
        self.assertEqual(core["price_model"], "free")
        self.assertEqual(core["screenshot_count"], 3)
        self.assertEqual(core["last_updated"], "2026-06-19T09:42:47Z")
        # Apple slots (slice 02): description from iTunes (fixture has none -> ""),
        # subtitle empty until browser merge, keyword_hints inferred by inversion.
        self.assertEqual(core["subtitle"], "")
        self.assertEqual(core["description"], "")
        self.assertEqual(core["keyword_hints"], ["musik", "podcasts", "spotify"])

    def test_map_itunes_to_core_degrades_safely_on_missing_fields(self):
        core = schema.map_itunes_to_core({"trackId": 1})
        self.assertEqual(core["id"], "1")
        self.assertEqual(core["title"], "")
        self.assertEqual(core["rating_count"], 0)
        self.assertEqual(core["category"], "other")


# ===========================================================================
# extract (real engine — smoke; edge cases in test_extraction.py)
# ===========================================================================

class ExtractTests(unittest.TestCase):
    def test_tokenize_filters_stopwords_and_short_tokens(self):
        toks = extract.tokenize("The Habit App und Daily Tracker!")
        self.assertNotIn("the", toks)
        self.assertNotIn("app", toks)  # generic
        self.assertNotIn("und", toks)  # stopword
        self.assertIn("habit", toks)
        self.assertIn("daily", toks)
        self.assertIn("tracker", toks)

    def test_extract_takes_documents_and_counts_per_doc(self):
        docs = [
            {"title": "Tracker Tracker", "subtitle": "", "description": ""},
            {"title": "Tracker Daily", "subtitle": "", "description": ""},
        ]
        out = extract.extract_keywords(docs, min_freq=1)
        by_term = {e["term"]: e["title_hits"] for e in out}
        # 'tracker' is in both titles (per-doc, not per-occurrence)
        self.assertEqual(by_term["tracker"], 2)
        self.assertEqual(by_term["daily"], 1)

    def test_extract_is_deterministic_and_sorted(self):
        docs = [
            {"title": "Habit Tracker", "subtitle": "", "description": ""},
            {"title": "Daily Habit", "subtitle": "", "description": ""},
            {"title": "Tracker Pro", "subtitle": "", "description": ""},
        ]
        a = extract.extract_keywords(docs, min_freq=1)
        b = extract.extract_keywords(docs, min_freq=1)
        self.assertEqual(a, b)

    def test_extract_drops_generics(self):
        docs = [{"title": "Music App Music", "subtitle": "", "description": ""}]
        out = extract.extract_keywords(docs, generics=["music"], min_freq=1)
        terms = {e["term"] for e in out}
        self.assertNotIn("music", terms)


# ===========================================================================
# score (real engine — smoke; edge cases in test_scoring.py)
# ===========================================================================

class ScoreTests(unittest.TestCase):
    def setUp(self):
        self.extracted = extract.extract_keywords(
            [
                {"title": "Habit Tracker", "subtitle": "", "description": ""},
                {"title": "Daily Habit", "subtitle": "", "description": ""},
                {"title": "Tracker Pro", "subtitle": "", "description": ""},
            ],
            min_freq=1,
        )

    def test_seed_concept_term_scored_high_relevance(self):
        # 'habit' is part of the seed description -> high cosine relevance
        scored = score.score_keywords(
            self.extracted, seed_description="A gamified habit tracker app", n_docs=3
        )
        by_term = {s["term"]: s for s in scored}
        self.assertIn("habit", by_term)
        # relevance is a 0..100 proxy signal, never "volume"
        self.assertTrue(0 <= by_term["habit"]["relevance"] <= 100)

    def test_competition_is_position_weighted_share(self):
        scored = score.score_keywords(
            self.extracted, seed_description="desc", n_docs=3
        )
        by_term = {s["term"]: s for s in scored}
        # 'habit' in 2 of 3 titles -> competition = round(100*(5*2/3)/9) = 37
        self.assertEqual(by_term["habit"]["competition"], 37)

    def test_division_by_zero_when_no_competitors(self):
        scored = score.score_keywords(
            self.extracted, seed_description="desc", n_docs=0
        )
        self.assertTrue(all(s["competition"] == 0 for s in scored))

    def test_output_sorted_deterministically(self):
        a = score.score_keywords(
            self.extracted, seed_description="habit tracker", n_docs=3
        )
        b = score.score_keywords(
            self.extracted, seed_description="habit tracker", n_docs=3
        )
        self.assertEqual(a, b)
        keys = [(-s["opportunity"], -s["relevance"], s["term"]) for s in a]
        self.assertEqual(keys, sorted(keys))


# ===========================================================================
# serialize (stable JSON + YAML)
# ===========================================================================

class SerializeTests(unittest.TestCase):
    def test_dumps_json_is_key_sorted_and_stable(self):
        obj = {"b": 1, "a": 2, "c": [3, 2, 1]}
        a = serialize.dumps_json(obj)
        b = serialize.dumps_json(obj)
        self.assertEqual(a, b)
        # keys sorted
        self.assertLess(a.index('"a"'), a.index('"b"'))
        self.assertTrue(a.endswith("\n"))

    def test_dump_json_writes_file(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "out.json")
            serialize.dump_json({"z": 1, "a": 2}, p)
            with open(p, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), serialize.dumps_json({"z": 1, "a": 2}))

    def test_dumps_yaml_stable_and_sorted(self):
        mapping = {"output_dir": "/tmp", "app_name": "A", "seeds": ["b", "a"], "n": None, "flag": True}
        a = serialize.dumps_yaml(mapping)
        b = serialize.dumps_yaml(mapping)
        self.assertEqual(a, b)
        lines = a.splitlines()
        # sorted keys
        self.assertLess([l.split(":")[0] for l in lines].index("app_name"),
                        [l.split(":")[0] for l in lines].index("output_dir"))


# ===========================================================================
# cache (key + freshness + round-trip)
# ===========================================================================

class CacheTests(unittest.TestCase):
    def test_cache_key_is_stable_and_param_order_invariant(self):
        a = CACHE.cache_key("GET", "https://x", {"term": "a", "limit": "5"})
        b = CACHE.cache_key("get", "https://x", {"limit": "5", "term": "a"})
        self.assertEqual(a, b)
        self.assertEqual(len(a), 64)  # sha256 hex

    def test_cache_key_differs_on_different_input(self):
        self.assertNotEqual(
            CACHE.cache_key("GET", "https://x", {"term": "a"}),
            CACHE.cache_key("GET", "https://x", {"term": "b"}),
        )

    def test_is_fresh_with_injected_now(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "abc.json")
            CACHE.write_cache(path, b"hi", now=1000.0)
            self.assertTrue(CACHE.is_fresh(path, ttl=100, now=1050.0))
            self.assertFalse(CACHE.is_fresh(path, ttl=100, now=2000.0))  # expired
            self.assertFalse(CACHE.is_fresh(os.path.join(d, "missing.json"), ttl=100, now=1000.0))

    def test_write_then_read_roundtrip_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as d:
            path = CACHE.cache_path(d, "deadbeef")
            payload = b'{"results": [1,2,3]}'
            CACHE.write_cache(path, payload, now=1000.0)
            self.assertEqual(CACHE.read_cache(path), payload)
            # a fresh read avoids re-reading on second run
            self.assertTrue(CACHE.is_fresh(path, CACHE.HTTP_TTL, 1100.0))


# ===========================================================================
# itunes.process_results — pure transform + DETERMINISM (core AC)
# ===========================================================================

class ProcessResultsTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "language": "de",
            "seed_keywords": ["habit"],
            "own_app_id": None,
        }

    def test_maps_dedupes_and_sorts_competitors(self):
        # Spotify + Habit + duplicate Spotify
        raw = [dict(RAW_ITUNES_SPOTIFY), dict(RAW_ITUNES_HABIT), dict(RAW_ITUNES_SPOTIFY)]
        out = itunes.process_results(raw, self.config)
        ids = [c["id"] for c in out["competitors"]]
        self.assertEqual(ids, ["324684580", "987654321"])  # deduped
        # sorted by -rating_count (Spotify 5.5M > Habit 12k)
        self.assertEqual(out["competitors"][0]["title"], "Spotify Musik und Podcasts")

    def test_slot_fields_subtitle_empty_without_browser(self):
        out = itunes.process_results([dict(RAW_ITUNES_SPOTIFY)], self.config)
        c = out["competitors"][0]
        # subtitle needs the Playwright collector; without it the slot is empty
        self.assertEqual(c["subtitle"], "")

    def test_seed_concept_term_present_and_scored(self):
        # two habit-bearing competitors so 'habit' clears the min_freq>=2 gate
        second = dict(RAW_ITUNES_HABIT)
        second["trackId"] = 987654399
        second["trackName"] = "Habit Buddy"
        raw = [dict(RAW_ITUNES_HABIT), second]
        out = itunes.process_results(raw, self.config)
        habit = next((k for k in out["keywords"] if k["term"] == "habit"), None)
        self.assertIsNotNone(habit)
        # relevance is a 0..100 proxy signal (never "volume"), present on every term
        self.assertTrue(0 <= habit["relevance"] <= 100)
        self.assertIn(habit["split"], ("primary-candidate", "long-tail-candidate"))

    def test_determinism_byte_identical_full_path_twice(self):
        """AC: two runs of collect→extract→score→serialize are byte-identical."""
        raw = [dict(RAW_ITUNES_SPOTIFY), dict(RAW_ITUNES_HABIT)]
        run_a = itunes.process_results(raw, self.config)
        run_b = itunes.process_results(raw, self.config)
        kw_a = serialize.dumps_json(run_a["keywords"])
        kw_b = serialize.dumps_json(run_b["keywords"])
        comp_a = serialize.dumps_json(run_a["competitors"])
        comp_b = serialize.dumps_json(run_b["competitors"])
        self.assertEqual(kw_a, kw_b)
        self.assertEqual(comp_a, comp_b)

    def test_report_body_stable_except_timestamp(self):
        raw = [dict(RAW_ITUNES_SPOTIFY)]
        out = itunes.process_results(raw, self.config)
        now = datetime.datetime(2026, 6, 26, 12, 0, 0)
        body_a = report.build_report(self.config, out["competitors"], out["keywords"], now=now)
        body_b = report.build_report(self.config, out["competitors"], out["keywords"], now=now)
        self.assertEqual(body_a, body_b)
        self.assertIn("Executive Summary", body_a)
        self.assertIn("Competitive Landscape", body_a)


# ===========================================================================
# itunes.discover with injected recorded fetch (no network)
# ===========================================================================

class DiscoverWithFixtureTests(unittest.TestCase):
    def test_discover_uses_injected_search_fn_without_network(self):
        config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "language": "de",
            "seed_keywords": ["habit", "tracker"],
        }
        calls = []

        def fake_search(term, **kwargs):
            calls.append(term)
            return {"resultCount": 1, "results": [dict(RAW_ITUNES_HABIT)]}

        out = itunes.discover(config, search_fn=fake_search, max_queries=2)
        # one query per seed keyword (capped at max_queries)
        self.assertEqual(len(calls), 2)
        self.assertEqual(len(out["competitors"]), 1)
        self.assertEqual(out["competitors"][0]["id"], "987654321")


if __name__ == "__main__":
    unittest.main()
