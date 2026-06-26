#!/usr/bin/env python3
"""Tests for P1 — Data quality hardening (stop-words, YAKE, relevance scaling).

Run from the repo root:
    python3 tests/aso-research/test_data_quality.py
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import extract  # noqa: E402
import score  # noqa: E402


# ===========================================================================
# AC1: Known leak terms do not survive
# ===========================================================================

class LeakTermFilteringTests(unittest.TestCase):
    def test_known_leak_terms_are_filtered(self):
        docs = [
            {
                "title": ("sodass sondern verlassen läuft anbieter fenster "
                          "man jedem dort wollen damit obwohl während"),
                "subtitle": "weil sodass sondern obwohl während",
                "description": "man jedem dort wollen app tool",
            },
        ]
        cands = extract.extract_keywords(docs, min_freq=1)
        terms = {c["term"] for c in cands}
        for leak in [
            "sodass", "sondern", "verlassen", "läuft", "anbieter",
            "fenster", "man", "jedem", "dort", "wollen", "damit",
            "obwohl", "während", "weil",
        ]:
            with self.subTest(leak=leak):
                self.assertNotIn(leak, terms,
                                 f"Leak term '{leak}' survived extraction")


# ===========================================================================
# AC2: Phrase preservation — stop-word in the middle survives
# ===========================================================================

class PhrasePreservationTests(unittest.TestCase):
    def test_phrase_stopword_middle_survives(self):
        docs = [
            {
                "title": "sprache zu text app",
                "subtitle": "sprache zu text werkzeug",
                "description": "Eine sprache zu text lösung für jeden tag",
            },
        ]
        cands = extract.extract_keywords(docs, min_freq=1)
        phrase_terms = [c["term"] for c in cands if c["is_phrase"]]
        self.assertIn("sprache zu text", phrase_terms)


# ===========================================================================
# AC3: ASO-valuable terms kept (carve-out does not over-filter)
# ===========================================================================

class ASOValuableTermsTests(unittest.TestCase):
    def test_aso_valuable_terms_kept(self):
        docs = [
            {
                "title": "best free pro kostenlos neu new tool widget",
                "subtitle": "best free new pro app",
                "description": "kostenlos und neu für alle benutzer",
            },
        ]
        cands = extract.extract_keywords(docs, min_freq=1)
        terms = {c["term"] for c in cands}
        for valuable in ["best", "free", "pro", "kostenlos", "neu", "new"]:
            with self.subTest(valuable=valuable):
                self.assertIn(valuable, terms,
                              f"ASO-valuable '{valuable}' was wrongly filtered")


# ===========================================================================
# AC4: Domain-noise is filtered and extensible via generics
# ===========================================================================

class DomainNoiseTests(unittest.TestCase):
    def test_domain_noise_filtered(self):
        docs = [
            {
                "title": "anbieter fenster realtool",
                "subtitle": "anbieter",
                "description": "fenster tool",
            },
        ]
        cands = extract.extract_keywords(docs, min_freq=1)
        terms = {c["term"] for c in cands}
        self.assertNotIn("anbieter", terms)
        self.assertNotIn("fenster", terms)

    def test_domain_noise_extensible_via_generics(self):
        docs = [
            {
                "title": "corpjunk realtool",
                "subtitle": "corpjunk",
                "description": "realtool",
            },
        ]
        cands = extract.extract_keywords(docs, min_freq=1,
                                         generics=["corpjunk"])
        terms = {c["term"] for c in cands}
        self.assertNotIn("corpjunk", terms)
        self.assertIn("realtool", terms)


# ===========================================================================
# AC5: Relevance max-normalisation — top term ~100, Primary bucket non-empty
# ===========================================================================

class RelevanceMaxNormalisationTests(unittest.TestCase):
    def test_max_relevance_near_100(self):
        extracted = [
            {
                "term": "meditation", "title_hits": 2, "subtitle_hits": 1,
                "description_hits": 2, "doc_freq": 3, "occurrences": 5,
                "is_phrase": False, "suggest": True, "tf_weighted": 20,
            },
            {
                "term": "timer", "title_hits": 1, "subtitle_hits": 0,
                "description_hits": 1, "doc_freq": 1, "occurrences": 2,
                "is_phrase": False, "suggest": False, "tf_weighted": 5,
            },
        ]
        scored = score.score_keywords(
            extracted,
            seed_description="A guided meditation timer app",
            suggest_terms=["meditation"],
            n_docs=3,
        )
        max_rel = max(s["relevance"] for s in scored)
        self.assertGreaterEqual(max_rel, 90,
                                f"Expected max relevance >= 90, got {max_rel}")
        self.assertLessEqual(max_rel, 100)

    def test_primary_candidate_bucket_non_empty(self):
        extracted = [
            {
                "term": "meditation", "title_hits": 2, "subtitle_hits": 1,
                "description_hits": 2, "doc_freq": 3, "occurrences": 5,
                "is_phrase": False, "suggest": True, "tf_weighted": 20,
            },
            {
                "term": "timer", "title_hits": 1, "subtitle_hits": 0,
                "description_hits": 1, "doc_freq": 1, "occurrences": 2,
                "is_phrase": False, "suggest": False, "tf_weighted": 5,
            },
        ]
        scored = score.score_keywords(
            extracted,
            seed_description="A guided meditation timer app",
            suggest_terms=["meditation"],
            n_docs=3,
        )
        primary = [s for s in scored if s["split"] == "primary-candidate"]
        self.assertGreater(len(primary), 0,
                           "Expected at least one primary-candidate")


# ===========================================================================
# AC6: Determinism preserved with max-normalisation
# ===========================================================================

class DeterminismPreservedTests(unittest.TestCase):
    def test_byte_identical_across_two_runs(self):
        extracted = [
            {
                "term": "meditation", "title_hits": 2, "subtitle_hits": 1,
                "description_hits": 2, "doc_freq": 3, "occurrences": 5,
                "is_phrase": False, "suggest": True, "tf_weighted": 20,
            },
            {
                "term": "timer", "title_hits": 1, "subtitle_hits": 0,
                "description_hits": 1, "doc_freq": 1, "occurrences": 2,
                "is_phrase": False, "suggest": False, "tf_weighted": 5,
            },
        ]
        a = score.score_keywords(
            extracted,
            seed_description="A guided meditation timer app",
            suggest_terms=["meditation"],
            n_docs=3,
        )
        b = score.score_keywords(
            extracted,
            seed_description="A guided meditation timer app",
            suggest_terms=["meditation"],
            n_docs=3,
        )
        self.assertEqual(a, b)

    def test_extraction_deterministic(self):
        docs = [
            {
                "title": "sprache zu text app",
                "subtitle": "sprache zu text werkzeug",
                "description": "Eine sprache zu text lösung",
            },
        ]
        a = extract.extract_keywords(docs, min_freq=1)
        b = extract.extract_keywords(docs, min_freq=1)
        self.assertEqual(a, b)


# ===========================================================================
# AC7: EN stop-words covered
# ===========================================================================

class EnglishStopwordTests(unittest.TestCase):
    def test_english_stopwords_filtered(self):
        docs = [
            {
                "title": "the and for with your you all are now from get",
                "subtitle": "has have this that its our was will can",
                "description": "but not his her they them their who "
                               "when how what into over than then these "
                               "those out about use using used one two "
                               "make made more most very just like also "
                               "only any some",
            },
        ]
        cands = extract.extract_keywords(docs, min_freq=1)
        terms = {c["term"] for c in cands}
        # All these should be stopwords and filtered out
        en_stops = [
            "the", "and", "for", "with", "your", "you", "all", "are",
            "now", "from", "get", "has", "have", "this", "that", "its",
            "our", "was", "will", "can", "but", "not", "his", "her",
            "they", "them", "their", "who", "when", "how", "what", "into",
            "over", "than", "then", "these", "those", "out", "about",
            "use", "using", "used", "one", "two", "make", "made", "more",
            "most", "very", "just", "like", "also", "only", "any", "some",
        ]
        for sw in en_stops:
            with self.subTest(sw=sw):
                self.assertNotIn(sw, terms,
                                 f"EN stopword '{sw}' survived extraction")


# ===========================================================================
# AC8: Inline fallback set retained
# ===========================================================================

class FallbackStopwordTests(unittest.TestCase):
    def test_fallback_stopwords_accessible(self):
        sw = extract._FALLBACK_STOPWORDS
        self.assertIsInstance(sw, set)
        self.assertGreater(len(sw), 50)

    def test_effective_stopwords_superset_of_core_fallback(self):
        core_stops = {"der", "die", "das", "und", "mit", "the", "and", "with"}
        self.assertTrue(core_stops.issubset(extract.STOPWORDS),
                        "Core stopwords missing from effective set")

    def test_build_stopwords_never_empty(self):
        sw = extract._build_stopwords()
        self.assertIsInstance(sw, set)
        self.assertGreater(len(sw), 20)


if __name__ == "__main__":
    unittest.main()
