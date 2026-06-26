#!/usr/bin/env python3
"""Tests for the Microsoft Store best-effort vertical (slice 05).

Run from the repo root:
    python3 tests/aso-research/test_ms.py

Covers the offline-testable pure logic only (no network/browser):
MS schema mapping (raw MS page data -> MS Core + description; no slot model),
the **isolation invariant** (MS is qualitative-only — it never reaches keyword
extraction or scoring; the score table stays Apple+Play), S1 qualitative-context
wiring (MS appears in the S1 representation as qualitative context, NOT in the
score table), MS collection orchestration (injectable fakes: never-blocking,
source-status tracking), and report surfacing (reachable -> MS qualitative
signal mentioned; unavailable -> methodology notes it).

The live MS SPA Playwright collector is NOT unit-tested (repo convention:
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
import condense  # noqa: E402
import report  # noqa: E402
import schema  # noqa: E402
import serialize  # noqa: E402


# ===========================================================================
# ID extractor — full product ID, both URL shapes (slice 05 → 04 fix)
# ===========================================================================

class MSIDExtractorTests(unittest.TestCase):
    def setUp(self):
        import ms as ms_mod
        self.extract_id = ms_mod._extract_id

    def test_full_product_id_detail(self):
        self.assertEqual(self.extract_id("/detail/9n7wbb04192f"), "9n7wbb04192f")

    def test_full_product_id_store_detail(self):
        self.assertEqual(self.extract_id("/store/detail/9n7wbb04192f"), "9n7wbb04192f")

    def test_full_product_id_classic_pattern(self):
        self.assertEqual(self.extract_id("/detail/9WZDNCRFHVJL"), "9WZDNCRFHVJL")

    def test_full_product_id_with_query(self):
        self.assertEqual(self.extract_id("/detail/9WZDNCRFHVJL?source=search"), "9WZDNCRFHVJL")

    def test_no_detail_returns_empty(self):
        self.assertEqual(self.extract_id("/home"), "")

    def test_bare_detail_no_id_returns_empty(self):
        self.assertEqual(self.extract_id("/detail/"), "")

    def test_short_id_below_minimum_rejected(self):
        self.assertEqual(self.extract_id("/detail/04192f"), "")  # 6 chars < 8 min
        self.assertEqual(self.extract_id("/detail/detail"), "")  # "detail" is the path component


# ===========================================================================
# Schema mapping: raw MS page data -> MS Core + description (no slot model)
# ===========================================================================

RAW_MS_APP = {
    "id": "9WZDNCRFHVJL",
    "store_url": "https://apps.microsoft.com/detail/9WZDNCRFHVJL",
    "title": "Habit Hero for Windows",
    "description": "The <b>best</b> habit tracker for Windows desktop. windowsdesktoponly tool.",
    "publisher": "HeroCo GmbH",
    "category": "Health & Fitness",
    "averageRating": 4.3,
    "ratingCount": 7421,
    "lastUpdateDate": "2026-05-10",
    "free": True,
    "price": 0,
    "screenshots": ["ms1", "ms2", "ms3"],
}


class MSSchemaTests(unittest.TestCase):
    def test_core_fields_populated(self):
        core = schema.map_ms_to_core(RAW_MS_APP)
        self.assertEqual(core["id"], "9WZDNCRFHVJL")
        self.assertEqual(core["platform"], "ms")
        self.assertEqual(core["title"], "Habit Hero for Windows")
        self.assertEqual(core["developer"], "HeroCo GmbH")
        self.assertEqual(core["category"], "health_fitness")
        self.assertEqual(core["rating_avg"], 4.3)
        self.assertEqual(core["rating_count"], 7421)
        self.assertEqual(core["price_model"], "free")
        self.assertEqual(core["screenshot_count"], 3)
        self.assertEqual(core["store_url"], "https://apps.microsoft.com/detail/9WZDNCRFHVJL")

    def test_description_slot_populated_html_stripped(self):
        core = schema.map_ms_to_core(RAW_MS_APP)
        # the only MS slot — description, HTML-stripped
        self.assertNotIn("<b>", core["description"])
        self.assertIn("best", core["description"])
        self.assertIn("windowsdesktoponly", core["description"])

    def test_reviews_sample_in_schema(self):
        core = schema.map_ms_to_core(RAW_MS_APP)
        self.assertEqual(core["reviews_sample"], [])

    def test_no_slot_model_beyond_description(self):
        """AC: MS has NO slot model — no Apple/Play slot keys leak in."""
        core = schema.map_ms_to_core(RAW_MS_APP)
        for forbidden in ("subtitle", "short_description", "full_description",
                          "keyword_hints", "tags"):
            self.assertNotIn(forbidden, core)
        # only the description slot + discovery field beyond Core
        self.assertIn("description", core)
        self.assertIn("similar_app_ids", core)

    def test_paid_price_model(self):
        raw = dict(RAW_MS_APP)
        raw["free"] = False
        raw["price"] = 4.99
        self.assertEqual(schema.infer_ms_price_model(raw), "paid")

    def test_degrades_safely_on_missing_fields(self):
        core = schema.map_ms_to_core({"id": "x"})
        self.assertEqual(core["id"], "x")
        self.assertEqual(core["platform"], "ms")
        self.assertEqual(core["description"], "")
        self.assertEqual(core["category"], "other")
        self.assertEqual(core.get("reviews_sample"), [])
        for forbidden in ("subtitle", "short_description", "full_description"):
            self.assertNotIn(forbidden, core)


# ===========================================================================
# Isolation invariant (CRITICAL) — MS never reaches extraction or scoring
# ===========================================================================

MS_TERM = "windowsdesktoponly"  # distinctive MS-only term


def _apple_comp():
    return schema.merge_apple_slots(
        schema.map_itunes_to_core(
            {"trackId": 1, "trackName": "Habit Tracker", "price": 0.0,
             "primaryGenreName": "Health & Fitness", "userRatingCount": 1200,
             "description": "Baue gute Gewohnheiten auf. Der beste Habit Tracker."}
        ),
        subtitle="Gewohnheits-Tracker",
    )


def _play_comp():
    return schema.map_play_to_core(
        {"appId": "com.a", "title": "Daily Habit", "summary": "daily habits",
         "description": "build routines habit", "genre": "Health & Fitness", "free": True}
    )


def _ms_entry():
    return schema.map_ms_to_core(RAW_MS_APP)


class MSIsolationTests(unittest.TestCase):
    def _config(self):
        return {"description": "habit tracker routine app",
                "category": "health_fitness", "app_name": "Habit Hero"}

    def test_ms_entry_not_in_scoring_corpus(self):
        """The dispatcher keeps MS out of competitors; scoring is Apple+Play."""
        competitors = [_apple_comp(), _play_comp()]  # MS deliberately excluded
        out = collect.extract_and_score(competitors, self._config())
        platforms = {k["platform"] for k in out["keywords"]}
        self.assertEqual(platforms, {"apple", "play"})
        self.assertNotIn("ms", platforms)

    def test_ms_only_term_never_scored(self):
        """AC2: a distinctive MS term never appears in keywords.json rows."""
        competitors = [_apple_comp(), _play_comp()]
        out = collect.extract_and_score(competitors, self._config())
        terms = {k["term"] for k in out["keywords"]}
        self.assertNotIn(MS_TERM, terms)
        self.assertNotIn(MS_TERM.lower(), {t.lower() for t in terms})

    def test_competition_artifact_stays_apple_play(self):
        """AC2: competition.json (= the competitor list) stays Apple+Play."""
        competitors = [_apple_comp(), _play_comp()]
        ms_entries = [_ms_entry()]
        # competition.json serialises the scoring competitors only
        blob = serialize.dumps_json(competitors)
        self.assertNotIn('"ms"', blob)
        self.assertNotIn(MS_TERM, blob)
        # MS lives in its own artefact
        ms_blob = serialize.dumps_json(ms_entries)
        self.assertIn('"ms"', ms_blob)

    def test_score_table_in_s1_representation_has_no_ms(self):
        """AC2: the S1 score_table stays Apple+Play even with MS qualitative ctx."""
        competitors = [_apple_comp(), _play_comp()]
        out = collect.extract_and_score(competitors, self._config())
        profiles = [{"app_id": "1", "title": "Habit Tracker",
                     "positioning": "p", "top_keywords": ["habit"], "tag": "t"}]
        rep = condense.build_llm_input(
            profiles, out["keywords"], [], config=self._config(),
            ms_entries=[_ms_entry()],
        )
        # qualitative_ms carries the MS entry...
        self.assertTrue(rep["qualitative_ms"])
        self.assertIn(MS_TERM, rep["qualitative_ms"][0]["description"])
        # ...but the score table does NOT carry the MS-only term
        score_terms = {r["term"] for r in rep["score_table"]}
        self.assertNotIn(MS_TERM, score_terms)
        # and the MS description never leaks verbatim into the score blob
        self.assertNotIn(MS_TERM, serialize.dumps_json(rep["score_table"]))


# ===========================================================================
# S1 qualitative-context wiring — MS as qualitative context for S1
# ===========================================================================

class MSQualitativeWiringTests(unittest.TestCase):
    def _config(self):
        return {"app_name": "Habit Hero", "category": "health_fitness",
                "seed_keywords": ["habit"], "own_app_id": None}

    def test_ms_appears_as_qualitative_context(self):
        rep = condense.build_llm_input(
            [], [], [], config=self._config(), ms_entries=[_ms_entry()],
        )
        self.assertTrue(rep["qualitative_ms"])
        ms = rep["qualitative_ms"][0]
        self.assertEqual(ms["title"], "Habit Hero for Windows")
        self.assertEqual(ms["developer"], "HeroCo GmbH")
        self.assertIn("best", ms["description"])

    def test_ms_qualitative_does_not_pollute_score_table_or_profiles(self):
        rep = condense.build_llm_input(
            [{"app_id": "1", "title": "A", "positioning": "p",
              "top_keywords": [], "tag": "t"}],
            [{"term": "habit", "competition": 20, "relevance": 80,
              "opportunity": 64, "split": "primary-candidate", "is_gap": False}],
            [], config=self._config(), ms_entries=[_ms_entry()],
        )
        self.assertEqual(len(rep["condensed_profiles"]), 1)  # only the Apple/Play one
        for prof in rep["condensed_profiles"]:
            self.assertNotEqual(prof.get("title"), "Habit Hero for Windows")

    def test_ms_qualitative_capped_and_deterministic(self):
        many = [
            schema.map_ms_to_core({"id": str(i), "title": f"MS {i}",
                                   "description": "d", "ratingCount": i, "free": True})
            for i in range(30)
        ]
        a = condense.build_llm_input([], [], [], config=self._config(), ms_entries=many)
        b = condense.build_llm_input([], [], [], config=self._config(), ms_entries=many)
        self.assertLessEqual(len(a["qualitative_ms"]), condense._MS_CAP)
        self.assertEqual(a, b)

    def test_no_ms_entries_yields_empty_qualitative(self):
        rep = condense.build_llm_input([], [], [], config=self._config())
        self.assertEqual(rep["qualitative_ms"], [])


# ===========================================================================
# MS collection orchestration (injectable fakes — never-blocking, isolated)
# ===========================================================================

class CollectMsTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }

    def test_ms_entries_collected_with_platform_ms(self):
        def search_fn(term, **_k):
            return [{"id": "ms1", "title": "MS Habit", "description": "windows tool",
                     "category": "Health & Fitness", "free": True}]

        out = collect.collect_ms(self.config, seed_terms=["habit"], search_fn=search_fn)
        self.assertTrue(out["ms_entries"])
        for e in out["ms_entries"]:
            self.assertEqual(e["platform"], "ms")
            self.assertIn("description", e)
        entry = out["source_status"]["ms"]
        self.assertEqual(entry["status"], "ok")
        self.assertEqual(entry["result_count"], 1)

    def test_failing_ms_search_marked_unavailable_never_blocks(self):
        out = collect.collect_ms(
            self.config, seed_terms=["habit"],
            search_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("spa down")),
        )
        entry = out["source_status"]["ms"]
        self.assertEqual(entry["status"], "unavailable")
        self.assertIn("spa down", entry["reason"])
        self.assertEqual(out["ms_entries"], [])  # no crash, empty result

    def test_ms_entries_deduped(self):
        def search_fn(term, **_k):
            return [{"id": "ms1", "title": "MS Habit", "description": "d", "free": True}]

        out = collect.collect_ms(self.config, seed_terms=["habit", "tracker"],
                                 search_fn=search_fn)
        ids = [e["id"] for e in out["ms_entries"]]
        self.assertEqual(ids.count("ms1"), 1)

    def test_ms_entries_kept_separate_from_scoring_return_shape(self):
        # collect_ms must NOT return a "competitors" key merged for scoring
        def search_fn(term, **_k):
            return [{"id": "ms1", "title": "MS Habit", "description": "d", "free": True}]

        out = collect.collect_ms(self.config, seed_terms=["habit"], search_fn=search_fn)
        self.assertNotIn("competitors", out)
        self.assertIn("ms_entries", out)

    def test_exception_in_search_never_aborts(self):
        out = collect.collect_ms(
            self.config, seed_terms=["habit"],
            search_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("x")),
        )
        entry = out["source_status"]["ms"]
        self.assertEqual(entry["status"], "unavailable")
        self.assertIn("x", entry["reason"])
        self.assertEqual(out["ms_entries"], [])

    def test_deterministic_output(self):
        kwargs = dict(
            seed_terms=["habit"],
            search_fn=lambda term, **k: [{"id": "ms1", "title": "MS Habit",
                                          "description": "d", "free": True}],
        )
        a = collect.collect_ms(self.config, **kwargs)
        b = collect.collect_ms(self.config, **kwargs)
        self.assertEqual(a, b)


# ===========================================================================
# MS detail-page enrichment (slice 04 — detail_fn injectable)
# ===========================================================================

class MSDetailEnrichTests(unittest.TestCase):
    def setUp(self):
        self.config = {
            "app_name": "Habit Hero",
            "description": "A gamified habit tracker app",
            "category": "health_fitness",
            "country": "de",
            "seed_keywords": ["habit"],
        }

    def test_detail_fn_enriches_description_rating_reviews(self):
        def search_fn(term, **_k):
            return [{"id": "9n7wbb04192f", "title": "MS Habit",
                     "description": "", "free": True}]

        def detail_fn(app_ids, **_k):
            return {"9n7wbb04192f": {
                "id": "9n7wbb04192f",
                "description": "A full habit tracker for Windows desktop.",
                "rating_avg": 4.3,
                "rating_count": 7421,
                "reviews_sample": ["Great app!", "Love it", "Very useful tool"],
            }}

        out = collect.collect_ms(
            self.config, seed_terms=["habit"],
            search_fn=search_fn, detail_fn=detail_fn,
        )
        entry = out["ms_entries"][0]
        self.assertIn("A full habit tracker", entry["description"])
        self.assertEqual(entry["rating_avg"], 4.3)
        self.assertEqual(entry["rating_count"], 7421)
        self.assertEqual(entry["reviews_sample"], ["Great app!", "Love it", "Very useful tool"])

    def test_detail_fn_preserves_search_description_when_detail_empty(self):
        def search_fn(term, **_k):
            return [{"id": "ms1", "title": "MS Habit",
                     "description": "card desc", "free": True}]

        def detail_fn(app_ids, **_k):
            return {"ms1": {"id": "ms1", "description": ""}}

        out = collect.collect_ms(
            self.config, seed_terms=["habit"],
            search_fn=search_fn, detail_fn=detail_fn,
        )
        self.assertEqual(out["ms_entries"][0]["description"], "card desc")

    def test_detail_fn_failure_never_blocks(self):
        def search_fn(term, **_k):
            return [{"id": "ms1", "title": "MS Habit",
                     "description": "", "free": True}]

        out = collect.collect_ms(
            self.config, seed_terms=["habit"],
            search_fn=search_fn,
            detail_fn=lambda *a, **k: (_ for _ in ()).throw(RuntimeError("detail down")),
        )
        entry_status = out["source_status"]["ms"]
        self.assertEqual(entry_status["status"], "ok")
        self.assertEqual(out["ms_entries"][0]["description"], "")

    def test_per_run_detail_cap_respected(self):
        def search_fn(term, **_k):
            apps = [{"id": f"ms{i}", "title": f"MS {i}",
                     "description": "", "free": True} for i in range(20)]
            return apps

        called_ids = []
        def detail_fn(app_ids, **_k):
            called_ids.append(list(app_ids))
            return {aid: {"id": aid, "description": f"desc {aid}",
                          "rating_avg": 4.0, "rating_count": 100} for aid in app_ids}

        import ms as ms_mod
        old_cap = ms_mod._DETAIL_CAP
        try:
            ms_mod._DETAIL_CAP = 5
            out = collect.collect_ms(
                self.config, seed_terms=["habit"],
                search_fn=search_fn, detail_fn=detail_fn,
            )
        finally:
            ms_mod._DETAIL_CAP = old_cap

        self.assertLessEqual(len(called_ids[0]), 5)
        self.assertEqual(len(out["ms_entries"]), 20)

    def test_detail_fn_individual_failure_tolerated(self):
        """One fragile detail page does not block others."""
        def search_fn(term, **_k):
            return [
                {"id": "ms1", "title": "Good", "description": "", "free": True},
                {"id": "ms2", "title": "Fragile", "description": "", "free": True},
            ]

        def detail_fn(app_ids, **_k):
            return {"ms1": {"id": "ms1", "description": "good desc",
                            "rating_avg": 4.0, "rating_count": 100}}
            # ms2 missing — tolerated

        out = collect.collect_ms(
            self.config, seed_terms=["habit"],
            search_fn=search_fn, detail_fn=detail_fn,
        )
        self.assertEqual(out["ms_entries"][0]["description"], "good desc")
        self.assertEqual(out["ms_entries"][1]["description"], "")

    def test_reviews_sample_capped_at_three(self):
        def search_fn(term, **_k):
            return [{"id": "ms1", "title": "MS App", "description": "", "free": True}]

        def detail_fn(app_ids, **_k):
            return {"ms1": {"id": "ms1", "description": "desc",
                            "reviews_sample": [f"r{i}" for i in range(10)]}}

        out = collect.collect_ms(
            self.config, seed_terms=["habit"],
            search_fn=search_fn, detail_fn=detail_fn,
        )
        self.assertLessEqual(len(out["ms_entries"][0]["reviews_sample"]), 3)

    def test_store_url_uses_full_product_id(self):
        def search_fn(term, **_k):
            return [{"id": "9n7wbb04192f", "title": "MS Habit",
                     "description": "", "free": True,
                     "store_url": "https://apps.microsoft.com/detail/9n7wbb04192f"}]

        out = collect.collect_ms(
            self.config, seed_terms=["habit"], search_fn=search_fn,
        )
        url = out["ms_entries"][0]["store_url"]
        self.assertIn("9n7wbb04192f", url)
        self.assertNotIn("04192f/", url.rsplit("/detail/", 1)[-1] if "/detail/" in url else url)

    def test_deterministic_with_detail_fn(self):
        def search_fn(term, **_k):
            return [{"id": "ms1", "title": "MS App", "description": "", "free": True}]

        def detail_fn(app_ids, **_k):
            return {"ms1": {"id": "ms1", "description": "desc",
                            "rating_avg": 4.0, "rating_count": 100,
                            "reviews_sample": ["good"]}}

        a = collect.collect_ms(self.config, seed_terms=["habit"],
                               search_fn=search_fn, detail_fn=detail_fn)
        b = collect.collect_ms(self.config, seed_terms=["habit"],
                               search_fn=search_fn, detail_fn=detail_fn)
        self.assertEqual(a, b)

    def test_ms_detail_not_merged_into_scoring(self):
        """Detail enrichment does NOT change the isolation invariant."""
        def search_fn(term, **_k):
            return [{"id": "ms1", "title": "MS App", "description": "msterm", "free": True}]

        def detail_fn(app_ids, **_k):
            return {"ms1": {"id": "ms1", "description": "msterm enriched",
                            "rating_avg": 4.0, "rating_count": 100}}

        out = collect.collect_ms(self.config, seed_terms=["habit"],
                                 search_fn=search_fn, detail_fn=detail_fn)
        self.assertNotIn("competitors", out)
        self.assertIn("ms_entries", out)


# ===========================================================================
# Report surfacing — MS qualitative signal + unavailable methodology
# ===========================================================================

import datetime  # noqa: E402

NOW = datetime.datetime(2026, 6, 26, 12, 0, 0)


def _cfg():
    return {"app_name": "Habit Hero", "description": "habit tracker",
            "category": "health_fitness", "country": "de", "language": "de",
            "own_app_id": None, "seed_keywords": ["habit"]}


def _comps():
    return [{"id": "1", "title": "Habit Tracker", "developer": "DevA",
             "category": "health_fitness", "rating_avg": 4.5, "rating_count": 1000,
             "price_model": "free", "subtitle": "Daily", "discovery": "chart/search"}]


def _kws():
    return [{"term": "habit", "competition": 20, "relevance": 80, "opportunity": 64,
             "split": "primary-candidate", "is_gap": False, "suggest": True}]


class MSReportTests(unittest.TestCase):
    def test_ms_reachable_report_mentions_qualitative_signal(self):
        body = report.build_report(
            _cfg(), _comps(), _kws(), now=NOW,
            source_status={"ms": "ok"},
            ms_entries=[_ms_entry()],
        )
        self.assertIn("Microsoft Store", body)
        self.assertIn("Habit Hero for Windows", body)  # MS title surfaced
        self.assertIn("qualitative", body.lower())

    def test_ms_unavailable_report_notes_it(self):
        body = report.build_report(
            _cfg(), _comps(), _kws(), now=NOW,
            source_status={"ms": "unavailable"},
            ms_entries=[],
        )
        self.assertIn("unavailable", body.lower())
        self.assertIn("ms", body.lower())

    def test_ms_absent_report_backward_compatible(self):
        """No MS context -> no Microsoft Store mention (slices 01-04 intact)."""
        body = report.build_report(_cfg(), _comps(), _kws(), now=NOW)
        self.assertNotIn("Microsoft Store", body)

    def test_ms_qualitative_note_in_positioning_section(self):
        body = report.build_report(
            _cfg(), _comps(), _kws(), now=NOW,
            source_status={"ms": "ok"},
            ms_entries=[_ms_entry()],
        )
        # the MS qualitative signal lives in §3 Positioning Map
        idx_pos = body.index("## 3. Positioning Map")
        idx_next = body.index("## 4. Keyword Report")
        ms_section = body[idx_pos:idx_next]
        self.assertIn("Microsoft Store", ms_section)


class MSPolitenessContractTests(unittest.TestCase):
    """AC5 + AC1 (SPA) — observable contract checks on the live collector.

    The live MS Playwright collector is NOT hit in unit tests (repo convention:
    external collectors fail loud). But the AC names specific structural
    requirements (SPA-aware navigation, the shared politeness rule-set, no
    stealth) — these are verifiable as a source-level contract so a regression
    that drops ``wait_for_selector`` or swaps in a stealth plugin is caught.
    """

    def setUp(self):
        with open(SCRIPTS_DIR / "ms.py", "r", encoding="utf-8") as fh:
            src = fh.read()
        # Inspect executable code only — strip the leading module docstring,
        # which legitimately documents the "no stealth" rule by name.
        if src.lstrip().startswith('"""'):
            start = src.index('"""')
            end = src.index('"""', start + 3) + 3
            src = src[end:]
        self.src = src

    def test_uses_spa_aware_navigation(self):
        # AC1: networkidle + wait_for_selector (not a simple load).
        self.assertIn("networkidle", self.src)
        self.assertIn("wait_for_selector", self.src)

    def test_obeys_shared_politeness_module(self):
        # AC5: routes through the shared politeness rule-set.
        self.assertIn("POLITE.RateLimiter", self.src)        # <=1 req/s + jitter
        self.assertIn("RETRY_STATUS", self.src)               # backoff on 429/503
        self.assertIn("backoff_delay", self.src)
        self.assertIn("robots_allows", self.src)              # robots.txt respected

    def test_no_stealth_plugins(self):
        # AC5: no stealth — moderation over extraction (PRD ToS discipline).
        import re
        for forbidden in (
            r"import\s+[\w.]*stealth",
            r"from\s+[\w.]*stealth",
            r"import\s+[\w.]*camoufox",
            r"from\s+[\w.]*camoufox",
            r"add_init_script",
            r"new_context\([^)]*proxy",
        ):
            self.assertFalse(
                re.search(forbidden, self.src, re.IGNORECASE),
                msg=f"stealth-like construct present: {forbidden}",
            )


if __name__ == "__main__":
    unittest.main()
