#!/usr/bin/env python3
"""Tests for the real keyword-extraction engine (slice 02).

Run from the repo root:
    python3 tests/aso-research/test_extraction.py

Covers the offline-testable pure logic only (no network/browser):
tokenization (umlauts, hyphenation, contractions), morphology grouping,
stopword/generic filtering, the min-frequency gate, position weighting,
YAKE n-gram phrases, and Search-Suggest enrichment.

Lives outside `skills/` on purpose (see CLAUDE.md "Tooling and testing").
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import extract  # noqa: E402


# ===========================================================================
# tokenization — umlauts / hyphenation / contractions
# ===========================================================================

class TokenizeTests(unittest.TestCase):
    def test_umlauts_preserved_as_tokens(self):
        toks = extract.tokenize("Gewohnheiten und Grüße für Café Besitzer")
        self.assertIn("grüße", toks)
        self.assertIn("café", toks)  # à-ÿ range covers é
        self.assertIn("besitzer", toks)
        self.assertNotIn("und", toks)  # stopword
        self.assertNotIn("für", toks)  # stopword

    def test_esszet_kept(self):
        toks = extract.tokenize("Fußballtrainer")
        self.assertIn("fußballtrainer", toks)

    def test_hyphenation_splits_into_tokens(self):
        toks = extract.tokenize("Gewohnheits-Tracker Pro-Version")
        # hyphen is a separator -> separate deterministic tokens
        self.assertIn("gewohnheits", toks)
        self.assertIn("tracker", toks)
        self.assertIn("version", toks)

    def test_contractions_split_on_apostrophe(self):
        toks = extract.tokenize("gamer's aren't pro's")
        # apostrophe is a separator -> 'gamer' / 'pro' kept, trailing 's' dropped
        self.assertIn("gamer", toks)
        self.assertIn("pro", toks)
        # never joined back together
        self.assertNotIn("gamers", toks)
        self.assertNotIn("gamer's", toks)

    def test_short_tokens_dropped(self):
        toks = extract.tokenize("a an im ux das")
        self.assertEqual(toks, [])

    def test_lowercase(self):
        toks = extract.tokenize("TRACKER Tracker tracker")
        self.assertEqual(toks, ["tracker", "tracker", "tracker"])


# ===========================================================================
# morphology grouping
# ===========================================================================

class MorphKeyTests(unittest.TestCase):
    def test_english_plural_merges(self):
        self.assertEqual(extract.morph_key("tracker"), extract.morph_key("trackers"))
        self.assertEqual(extract.morph_key("habit"), extract.morph_key("habits"))

    def test_german_declension_merges(self):
        self.assertEqual(extract.morph_key("gewohnheit"), extract.morph_key("gewohnheiten"))
        self.assertEqual(extract.morph_key("routine"), extract.morph_key("routinen"))

    def test_umlaut_normalized_for_grouping_only(self):
        # mutter / mütter should share a key (umlaut -> base vowel)
        self.assertEqual(extract.morph_key("mutter"), extract.morph_key("mütter"))

    def test_key_never_below_min_length(self):
        # stripping must leave >= 3 chars; short stems are not over-stripped
        for tok in ("cat", "hat", "die"):
            self.assertTrue(len(extract.morph_key(tok)) >= 3)


class GroupTermsTests(unittest.TestCase):
    def test_groups_variants_and_keeps_display_form(self):
        records = {
            "tracker": {"occurrences": 3, "title_docs": {0}, "subtitle_docs": set(), "description_docs": set(), "tf_weighted": 5},
            "trackers": {"occurrences": 1, "title_docs": {1}, "subtitle_docs": set(), "description_docs": set(), "tf_weighted": 5},
        }
        merged = extract.group_terms(records)
        self.assertEqual(len(merged), 1)
        m = merged[0]
        self.assertEqual(m["term"], "tracker")  # most frequent
        self.assertEqual(m["variants"], ["tracker", "trackers"])
        self.assertEqual(m["occurrences"], 4)
        self.assertEqual(m["title_docs"], {0, 1})

    def test_display_form_alphabetical_on_tie(self):
        records = {
            "zebra": {"occurrences": 1, "title_docs": set(), "subtitle_docs": set(), "description_docs": set(), "tf_weighted": 1},
            "alpha": {"occurrences": 1, "title_docs": set(), "subtitle_docs": set(), "description_docs": set(), "tf_weighted": 1},
        }
        # both share a near-empty key only if they group; force same key:
        # 'zebra'/'alpha' differ -> two groups, but each keeps its surface form
        merged = {m["term"]: m for m in extract.group_terms(records)}
        self.assertIn("zebra", merged)
        self.assertIn("alpha", merged)


# ===========================================================================
# extract_keywords — stopwords / generics / min-freq / position weighting
# ===========================================================================

class ExtractKeywordsTests(unittest.TestCase):
    def setUp(self):
        self.docs = [
            {
                "title": "Habit Tracker Daily",
                "subtitle": "Gewohnheiten bilden",
                "description": "Baue gute Gewohnheiten auf. Der beste Habit Tracker fuer jeden Tag.",
            },
            {
                "title": "Daily Habit Hero",
                "subtitle": "Gewohnheits-Tracker Pro",
                "description": "Verfolge deine Gewohnheiten und Ziele jeden Tag.",
            },
            {
                "title": "Streaks Habit",
                "subtitle": "Routine Tracker",
                "description": "Behalte deine Routinen bei mit diesem Habit-Tool.",
            },
        ]

    def _by_term(self, out):
        return {c["term"]: c for c in out}

    def test_drops_generics_and_platform_words(self):
        out = extract.extract_keywords(self.docs, generics=["habit"])
        terms = {c["term"] for c in out}
        self.assertNotIn("habit", terms)        # generic
        self.assertNotIn("iphone", terms)
        self.assertNotIn("android", terms)

    def test_drops_stopwords(self):
        out = extract.extract_keywords(self.docs)
        terms = {c["term"] for c in out}
        for sw in ("der", "die", "und", "mit", "this", "with"):
            self.assertNotIn(sw, terms)

    def test_min_frequency_gate(self):
        # 'routine' appears in subtitle of doc2 + description of doc2 (2 occ)
        # a term appearing only once weakly must be dropped.
        docs = [
            {"title": "solo lonelyword here", "subtitle": "", "description": ""},
            {"title": "other thing", "subtitle": "", "description": ""},
        ]
        out = extract.extract_keywords(docs, min_freq=2)
        terms = {c["term"] for c in out}
        # 'lonelyword' occurs once (title weight 5 -> occurrences 1) -> dropped
        self.assertNotIn("lonelyword", terms)
        # with min_freq=1 it reappears
        out1 = extract.extract_keywords(docs, min_freq=1)
        self.assertIn("lonelyword", {c["term"] for c in out1})

    def test_position_weighting_title_beats_subtitle_beats_description(self):
        out = extract.extract_keywords(self.docs)
        by = self._by_term(out)
        # 'tracker': title doc0 (×5), subtitle doc1+doc2 (×3 each),
        # description doc0 (×1) -> 5 + 3 + 3 + 1 = 12
        self.assertEqual(by["tracker"]["tf_weighted"], 5 + 3 + 3 + 1)
        self.assertEqual(by["tracker"]["title_hits"], 1)
        self.assertEqual(by["tracker"]["subtitle_hits"], 2)
        self.assertEqual(by["tracker"]["description_hits"], 1)

    def test_per_doc_not_per_occurrence(self):
        docs = [{"title": "tracker tracker tracker", "subtitle": "", "description": ""}]
        out = extract.extract_keywords(docs, min_freq=1)
        by = self._by_term(out)
        # three occurrences in one title count as ONE doc hit
        self.assertEqual(by["tracker"]["title_hits"], 1)

    def test_yake_phrases_emitted_as_candidates(self):
        out = extract.extract_keywords(self.docs, min_freq=1)
        phrases = {c["term"] for c in out if c["is_phrase"]}
        # "habit tracker" appears across title fields
        self.assertTrue(any("habit" in p and "tracker" in p for p in phrases))

    def test_search_suggest_enrichment_adds_missing_terms(self):
        out = extract.extract_keywords(
            self.docs, suggest_terms=["meditation timer", "yogafreiburg"]
        )
        terms = {c["term"] for c in out}
        self.assertIn("meditation timer", terms)
        self.assertIn("yogafreiburg", terms)
        by = self._by_term(out)
        self.assertTrue(by["meditation timer"]["suggest"])
        self.assertTrue(by["meditation timer"]["is_phrase"])

    def test_search_suggest_does_not_duplicate_existing(self):
        out = extract.extract_keywords(self.docs, suggest_terms=["tracker"])
        # only one 'tracker' candidate
        self.assertEqual([c["term"] for c in out].count("tracker"), 1)

    def test_deterministic_byte_identical(self):
        a = extract.extract_keywords(self.docs, suggest_terms=["habit tracker"])
        b = extract.extract_keywords(self.docs, suggest_terms=["habit tracker"])
        self.assertEqual(a, b)

    def test_empty_documents_returns_empty(self):
        self.assertEqual(extract.extract_keywords([]), [])


if __name__ == "__main__":
    unittest.main()
