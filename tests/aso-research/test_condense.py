#!/usr/bin/env python3
"""Tests for the LLM-input preparation (slice 03) — condense.py.

Run from the repo root:
    python3 tests/aso-research/test_condense.py

Covers: H1 raw-profile preparation (clean per-app metadata), the S1
representation carrying NO raw descriptions (AC1), the Modus-A flagging
(own app is just another reference entry — AC7), and the score-table cap
that bounds the representation.
"""

import json
import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import condense  # noqa: E402


def _competitor(app_id, *, title="App", subtitle="", description="raw desc", rating_count=10):
    return {
        "id": app_id,
        "platform": "apple",
        "title": title,
        "subtitle": subtitle,
        "description": description,
        "keyword_hints": ["habit"],
        "category": "health_fitness",
        "developer": "Dev",
        "rating_avg": 4.5,
        "rating_count": rating_count,
        "price_model": "free",
    }


class PrepareH1InputTests(unittest.TestCase):
    def test_one_clean_record_per_competitor_with_raw_description(self):
        comps = [_competitor("1", title="Habit Hero", description="A long raw description.")]
        h1 = condense.prepare_h1_input(comps)
        self.assertEqual(len(h1), 1)
        rec = h1[0]
        self.assertEqual(rec["app_id"], "1")
        self.assertEqual(rec["title"], "Habit Hero")
        # H1 is allowed to see the raw description (it condenses it).
        self.assertEqual(rec["description"], "A long raw description.")
        self.assertFalse(rec["is_own_app"])

    def test_own_app_flagged_as_reference_entry_modus_a(self):
        comps = [_competitor("1"), _competitor("42", title="My Own App")]
        h1 = condense.prepare_h1_input(comps, own_app_id="42")
        flagged = [r for r in h1 if r["is_own_app"]]
        self.assertEqual(len(flagged), 1)
        self.assertEqual(flagged[0]["app_id"], "42")

    def test_no_own_app_id_means_no_flag(self):
        comps = [_competitor("1"), _competitor("2")]
        h1 = condense.prepare_h1_input(comps, own_app_id=None)
        self.assertFalse(any(r["is_own_app"] for r in h1))

    def test_play_description_falls_back_to_full_description(self):
        """Slice 04: Play competitors reach H1 with their rich text."""
        play = {
            "id": "com.a", "platform": "play", "title": "Habit Hero",
            "short_description": "daily habits", "full_description": "long rich text",
            "category": "health_fitness", "developer": "Dev",
            "rating_avg": 4.5, "rating_count": 10, "price_model": "free",
        }
        h1 = condense.prepare_h1_input([play])
        rec = h1[0]
        self.assertEqual(rec["description"], "long rich text")  # full_description fallback
        self.assertEqual(rec["subtitle"], "daily habits")        # short_description fallback
        self.assertEqual(rec["title"], "Habit Hero")


class BuildLlmInputTests(unittest.TestCase):
    def test_representation_contains_no_raw_description(self):
        """AC1: raw descriptions never reach the later LLM stages."""
        profiles = [
            {"app_id": "1", "title": "Habit Hero",
             "positioning": "A gamified habit tracker.", "top_keywords": ["habit"], "tag": "habit"}
        ]
        keywords = [{"term": "habit", "competition": 20, "relevance": 80, "opportunity": 64, "split": "primary-candidate", "is_gap": False}]
        config = {"app_name": "H", "category": "other", "seed_keywords": ["habit"], "own_app_id": None}
        rep = condense.build_llm_input(profiles, keywords, config=config)
        blob = json.dumps(rep)
        self.assertNotIn("raw desc", blob)
        self.assertNotIn("description", blob)  # no description key at all
        # the condensed profile carries only positioning/keywords/tag
        prof = rep["condensed_profiles"][0]
        self.assertEqual(set(prof.keys()), {"app_id", "title", "positioning", "top_keywords", "tag", "is_own_app"})

    def test_own_app_flagged_on_condensed_profile(self):
        profiles = [
            {"app_id": "1", "title": "A", "positioning": "p", "top_keywords": [], "tag": "t"},
            {"app_id": "9", "title": "Own", "positioning": "p", "top_keywords": [], "tag": "t"},
        ]
        config = {"app_name": "H", "category": "other", "seed_keywords": [], "own_app_id": "9"}
        rep = condense.build_llm_input(profiles, [], config=config)
        own = [p for p in rep["condensed_profiles"] if p["is_own_app"]]
        self.assertEqual(len(own), 1)
        self.assertEqual(own[0]["app_id"], "9")
        self.assertEqual(rep["own_app_id"], "9")

    def test_score_table_capped(self):
        profiles = [{"app_id": "1", "title": "A", "positioning": "p", "top_keywords": [], "tag": "t"}]
        keywords = [{"term": f"k{i}", "competition": 1, "relevance": 1, "opportunity": 1, "split": "long-tail-candidate", "is_gap": False} for i in range(200)]
        config = {"app_name": "H", "category": "other", "seed_keywords": [], "own_app_id": None}
        rep = condense.build_llm_input(profiles, keywords, config=config)
        self.assertEqual(len(rep["score_table"]), condense._SCORE_TABLE_CAP)

    def test_score_table_carries_proxy_fields_only(self):
        profiles = [{"app_id": "1", "title": "A", "positioning": "p", "top_keywords": [], "tag": "t"}]
        keywords = [{"term": "habit", "competition": 20, "relevance": 80, "opportunity": 64, "split": "primary-candidate", "is_gap": True, "suggest": True, "title_hits": 5, "subtitle_hits": 2}]
        config = {"app_name": "H", "category": "other", "seed_keywords": [], "own_app_id": None}
        rep = condense.build_llm_input(profiles, keywords, config=config)
        row = rep["score_table"][0]
        self.assertEqual(set(row.keys()), {"term", "competition", "relevance", "opportunity", "split", "is_gap", "suggest"})
        self.assertNotIn("title_hits", row)


class OwnAppReferencedTests(unittest.TestCase):
    def test_modus_a_when_own_app_in_profiles(self):
        profiles = [{"app_id": "1", "title": "A", "positioning": "p", "top_keywords": [], "tag": "t"}]
        config = {"app_name": "H", "category": "other", "seed_keywords": [], "own_app_id": "1"}
        rep = condense.build_llm_input(profiles, [], config=config)
        self.assertTrue(condense.own_app_is_referenced(rep))

    def test_modus_b_when_no_own_app(self):
        profiles = [{"app_id": "1", "title": "A", "positioning": "p", "top_keywords": [], "tag": "t"}]
        config = {"app_name": "H", "category": "other", "seed_keywords": [], "own_app_id": None}
        rep = condense.build_llm_input(profiles, [], config=config)
        self.assertFalse(condense.own_app_is_referenced(rep))


if __name__ == "__main__":
    unittest.main()
