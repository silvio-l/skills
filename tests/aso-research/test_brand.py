#!/usr/bin/env python3
"""Tests for P3 — Brand-conflict detection (resolver, parser, conflict detector).

Run from the repo root:
    python3 -m unittest discover -s tests/aso-research -q
"""

import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
FIXTURES_DIR = pathlib.Path(__file__).resolve().parent / "fixtures" / "brand"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import brand  # noqa: E402

# ===========================================================================
# AC1: Convention discovery
# ===========================================================================


class GlossarDiscoveryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmp.name

    def tearDown(self):
        self._tmp.cleanup()

    def test_resolve_finds_brand_glossary_ts_by_convention(self):
        (pathlib.Path(self.tmpdir) / "brand-glossary.ts").write_text(
            'export const x = "y" as const;'
        )
        found = brand.resolve_glossar(self.tmpdir)
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith("brand-glossary.ts"))

    def test_resolve_finds_dot_brandignore_by_convention(self):
        (pathlib.Path(self.tmpdir) / ".brandignore").write_text("Diktieren\n")
        found = brand.resolve_glossar(self.tmpdir)
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith(".brandignore"))

    def test_resolve_finds_brand_words_md_by_convention(self):
        (pathlib.Path(self.tmpdir) / "BRAND_WORDS.md").write_text("# Words\n")
        found = brand.resolve_glossar(self.tmpdir)
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith("BRAND_WORDS.md"))

    def test_resolve_finds_docs_brand_glossary_ts(self):
        docs_dir = pathlib.Path(self.tmpdir) / "docs"
        docs_dir.mkdir()
        (docs_dir / "brand-glossary.ts").write_text(
            'export const x = "y" as const;'
        )
        found = brand.resolve_glossar(self.tmpdir)
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith("docs/brand-glossary.ts"))

    def test_resolve_finds_docs_brandignore(self):
        docs_dir = pathlib.Path(self.tmpdir) / "docs"
        docs_dir.mkdir()
        (docs_dir / ".brandignore").write_text("Diktieren\n")
        found = brand.resolve_glossar(self.tmpdir)
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith("docs/.brandignore"))

    def test_flag_overrides_convention(self):
        (pathlib.Path(self.tmpdir) / "brand-glossary.ts").write_text(
            'export const x = "y" as const;'
        )
        custom = pathlib.Path(self.tmpdir) / "custom.ts"
        custom.write_text('export const z = "w" as const;')
        found = brand.resolve_glossar(self.tmpdir, flag_path=str(custom))
        self.assertIsNotNone(found)
        self.assertEqual(pathlib.Path(found).name, "custom.ts")

    def test_flag_nonexistent_file_returns_none(self):
        found = brand.resolve_glossar(
            self.tmpdir, flag_path="/nonexistent/brand.ts"
        )
        self.assertIsNone(found)

    def test_silent_skip_when_nothing_found(self):
        found = brand.resolve_glossar(self.tmpdir)
        self.assertIsNone(found)

    def test_resolve_finds_brand_glossary_js_by_convention(self):
        (pathlib.Path(self.tmpdir) / "brand-glossary.js").write_text("// js\n")
        found = brand.resolve_glossar(self.tmpdir)
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith("brand-glossary.js"))

    def test_resolve_finds_glossar_in_parent_dir(self):
        (pathlib.Path(self.tmpdir) / "brand-glossary.ts").write_text(
            'export const x = "y" as const;'
        )
        sub = pathlib.Path(self.tmpdir) / "sub"
        sub.mkdir()
        found = brand.resolve_glossar(str(sub))
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith("brand-glossary.ts"))

    def test_resolve_finds_glossar_multiple_levels_up(self):
        (pathlib.Path(self.tmpdir) / ".brandignore").write_text("Diktieren\n")
        sub = pathlib.Path(self.tmpdir) / "a" / "b"
        sub.mkdir(parents=True)
        found = brand.resolve_glossar(str(sub))
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith(".brandignore"))

    def test_resolve_prefers_closer_ancestor(self):
        (pathlib.Path(self.tmpdir) / ".brandignore").write_text("root\n")
        sub = pathlib.Path(self.tmpdir) / "sub"
        sub.mkdir()
        (sub / ".brandignore").write_text("sub\n")
        found = brand.resolve_glossar(str(sub))
        self.assertIsNotNone(found)
        self.assertEqual(pathlib.Path(found).resolve(), (sub / ".brandignore").resolve())

    def test_resolve_returns_none_when_ancestors_have_no_glossar(self):
        sub = pathlib.Path(self.tmpdir) / "deep" / "nested"
        sub.mkdir(parents=True)
        found = brand.resolve_glossar(str(sub))
        self.assertIsNone(found)

    def test_first_match_wins_among_conventions(self):
        (pathlib.Path(self.tmpdir) / "brand-glossary.ts").write_text(
            'export const x = "y" as const;'
        )
        (pathlib.Path(self.tmpdir) / ".brandignore").write_text("Diktieren\n")
        found = brand.resolve_glossar(self.tmpdir)
        self.assertIsNotNone(found)
        # brand-glossary.ts comes first in the convention list
        self.assertTrue(found.endswith("brand-glossary.ts"))


# ===========================================================================
# AC2: Parser — brand-glossary.ts and .brandignore
# ===========================================================================


class TsGlossarParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.glossar = brand.parse_glossar(
            str(FIXTURES_DIR / "whispaste-glossary.ts")
        )

    def test_forbidden_contains_expected_terms(self):
        forbidden = self.glossar["forbidden"]
        for term in ["diktieren", "dictate", "dictation", "diktat",
                      "voice assistant", "dictations"]:
            with self.subTest(term=term):
                self.assertIn(term, forbidden)

    def test_canonical_maps_diktieren_to_spracheingabe(self):
        self.assertEqual(
            self.glossar["canonical"]["diktieren"], "Spracheingabe"
        )

    def test_canonical_maps_dictate_to_speak(self):
        self.assertEqual(self.glossar["canonical"]["dictate"], "speak")

    def test_canonical_maps_diktat_to_transkript(self):
        self.assertEqual(self.glossar["canonical"]["diktat"], "Transkript")

    def test_canonical_maps_dictation_to_voice_input_tool(self):
        self.assertEqual(
            self.glossar["canonical"]["dictation"], "voice-input tool"
        )

    def test_empty_replacement_for_voice_assistant(self):
        self.assertEqual(self.glossar["canonical"]["voice assistant"], "")

    def test_template_literal_resolved(self):
        self.assertEqual(self.glossar["canonical"]["dictations"], "transcripts")

    def test_forbidden_is_deterministic(self):
        a = brand.parse_glossar(
            str(FIXTURES_DIR / "whispaste-glossary.ts")
        )
        b = brand.parse_glossar(
            str(FIXTURES_DIR / "whispaste-glossary.ts")
        )
        self.assertEqual(a, b)

    def test_canonical_keys_are_lowercase(self):
        for key in self.glossar["canonical"]:
            self.assertEqual(key, key.lower())


class BrandignoreParserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.glossar = brand.parse_glossar(
            str(FIXTURES_DIR / "simple.brandignore")
        )

    def test_forbidden_contains_diktieren(self):
        self.assertIn("diktieren", self.glossar["forbidden"])

    def test_forbidden_contains_diktat(self):
        self.assertIn("diktat", self.glossar["forbidden"])

    def test_forbidden_contains_voice_assistant(self):
        self.assertIn("voice assistant", self.glossar["forbidden"])

    def test_forbidden_contains_diktat_verlauf(self):
        self.assertIn("diktat-verlauf", self.glossar["forbidden"])

    def test_forbidden_contains_sprachassistent(self):
        self.assertIn("sprachassistent", self.glossar["forbidden"])

    def test_comment_lines_skipped(self):
        self.assertNotIn("# this is a comment", self.glossar["forbidden"])

    def test_all_replacements_are_empty_strings(self):
        for forbidden_term in self.glossar["forbidden"]:
            self.assertEqual(
                self.glossar["canonical"].get(forbidden_term), ""
            )

    def test_brandignore_is_deterministic(self):
        a = brand.parse_glossar(
            str(FIXTURES_DIR / "simple.brandignore")
        )
        b = brand.parse_glossar(
            str(FIXTURES_DIR / "simple.brandignore")
        )
        self.assertEqual(a, b)


# ===========================================================================
# AC3: Conflict detector
# ===========================================================================


class ConflictDetectorTests(unittest.TestCase):
    def setUp(self):
        self.glossar = {
            "forbidden": ["diktieren", "diktat", "dictate"],
            "canonical": {
                "diktieren": "Spracheingabe",
                "diktat": "Transkript",
                "dictate": "speak",
            },
        }

    def test_substring_match_detects_conflict(self):
        keywords = [
            {"term": "diktieren zu text", "opportunity": 80, "relevance": 70}
        ]
        conflicts = brand.detect_conflicts(keywords, self.glossar)
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["term"], "diktieren zu text")
        self.assertEqual(conflicts[0]["forbidden_match"], "diktieren")
        self.assertEqual(conflicts[0]["replacement"], "Spracheingabe")

    def test_case_insensitive_matching(self):
        keywords = [
            {"term": "DIKTIEREN App", "opportunity": 60, "relevance": 50},
            {"term": "DikTat Software", "opportunity": 55, "relevance": 45},
        ]
        conflicts = brand.detect_conflicts(keywords, self.glossar)
        self.assertEqual(len(conflicts), 2)

    def test_diktieren_zu_text_with_full_strategy_set(self):
        keywords = [
            {"term": "diktieren zu text", "opportunity": 80, "relevance": 70}
        ]
        conflicts = brand.detect_conflicts(keywords, self.glossar)
        self.assertEqual(len(conflicts), 1)
        expected_strategies = list(brand.STRATEGIES.keys())
        self.assertEqual(conflicts[0]["strategies"], expected_strategies)

    def test_no_conflict_when_no_match(self):
        keywords = [{"term": "spracheingabe app"}]
        conflicts = brand.detect_conflicts(keywords, self.glossar)
        self.assertEqual(len(conflicts), 0)

    def test_empty_keywords_returns_empty(self):
        conflicts = brand.detect_conflicts([], self.glossar)
        self.assertEqual(conflicts, [])

    def test_empty_glossar_returns_empty(self):
        keywords = [{"term": "diktieren app"}]
        conflicts = brand.detect_conflicts(
            keywords, {"forbidden": [], "canonical": {}}
        )
        self.assertEqual(conflicts, [])

    def test_missing_glossar_keys_returns_empty(self):
        keywords = [{"term": "diktieren app"}]
        self.assertEqual(brand.detect_conflicts(keywords, {}), [])

    def test_conflict_carries_keyword_scores(self):
        keywords = [
            {
                "term": "diktieren app",
                "opportunity": 85,
                "relevance": 72,
                "platform": "apple",
                "competition": 30,
            }
        ]
        conflicts = brand.detect_conflicts(keywords, self.glossar)
        self.assertEqual(conflicts[0]["opportunity"], 85)
        self.assertEqual(conflicts[0]["relevance"], 72)
        self.assertEqual(conflicts[0]["platform"], "apple")

    def test_multiple_keywords_match_same_forbidden_term(self):
        keywords = [
            {"term": "diktieren zu text", "opportunity": 80, "relevance": 70},
            {"term": "diktieren app kostenlos", "opportunity": 75, "relevance": 65},
        ]
        conflicts = brand.detect_conflicts(keywords, self.glossar)
        self.assertEqual(len(conflicts), 2)
        matches = [c["forbidden_match"] for c in conflicts]
        self.assertEqual(matches, ["diktieren", "diktieren"])

    def test_one_match_per_keyword(self):
        keywords = [
            {"term": "diktat diktieren", "opportunity": 70, "relevance": 60}
        ]
        conflicts = brand.detect_conflicts(keywords, self.glossar)
        self.assertEqual(len(conflicts), 1)


# ===========================================================================
# AC4: Deterministic ordering
# ===========================================================================


class DeterministicOrderingTests(unittest.TestCase):
    def setUp(self):
        self.glossar = {
            "forbidden": ["diktieren", "diktat"],
            "canonical": {
                "diktieren": "Spracheingabe",
                "diktat": "Transkript",
            },
        }

    def test_byte_identical_across_two_runs(self):
        keywords = [
            {"term": "zzz diktieren app", "opportunity": 50},
            {"term": "aaa diktieren tool", "opportunity": 80},
            {"term": "diktat software", "opportunity": 60},
        ]
        a = brand.detect_conflicts(keywords, self.glossar)
        b = brand.detect_conflicts(keywords, self.glossar)
        self.assertEqual(a, b)

    def test_ordering_stable_with_shuffled_input(self):
        keywords = [
            {"term": "diktat software", "opportunity": 60},
            {"term": "aaa diktieren tool", "opportunity": 80},
            {"term": "zzz diktieren app", "opportunity": 50},
        ]
        conflicts = brand.detect_conflicts(keywords, self.glossar)
        self.assertEqual(len(conflicts), 3)
        # diktat comes before diktieren alphabetically
        self.assertIn("diktat", conflicts[0]["forbidden_match"])
        # Within same forbidden_match, sorted by term alphabetically
        if conflicts[0]["forbidden_match"] == "diktat":
            self.assertEqual(conflicts[1]["forbidden_match"], "diktieren")
            self.assertIn("aaa", conflicts[1]["term"])
            self.assertIn("zzz", conflicts[2]["term"])


# ===========================================================================
# AC5: Strategy descriptions exist
# ===========================================================================


class StrategySetTests(unittest.TestCase):
    def test_all_four_strategies_present(self):
        self.assertIn("keyword-field-only", brand.STRATEGIES)
        self.assertIn("alternative phrasing", brand.STRATEGIES)
        self.assertIn("non-brand landingpage", brand.STRATEGIES)
        self.assertIn("accept deliberately", brand.STRATEGIES)

    def test_strategies_are_non_empty_descriptions(self):
        for key, desc in brand.STRATEGIES.items():
            with self.subTest(key=key):
                self.assertIsInstance(desc, str)
                self.assertGreater(len(desc), 10)

    def test_every_exported_strategy_key_is_a_valid_python_identifier_base(self):
        for key in brand.STRATEGIES:
            self.assertNotIn(" ", key[0] if key else "")


# ===========================================================================
# AC6: Report integration — brand conflicts subsection renders
# ===========================================================================


class ReportBrandConflictsTests(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.tmpdir = self._tmp.name
        sys.path.insert(0, str(SCRIPTS_DIR))

    def tearDown(self):
        self._tmp.cleanup()

    def test_report_includes_brand_conflicts_subsection_when_conflicts_exist(self):
        import datetime
        import report as report_mod

        config = {
            "app_name": "Test App",
            "country": "de",
            "language": "de",
            "category": "Productivity",
        }
        keywords = [
            {"term": "diktieren zu text", "opportunity": 80, "relevance": 70,
             "competition": 20, "split": "primary-candidate", "is_gap": False,
             "suggest": True, "platform": "apple"},
        ]
        brand_conflicts = [
            {
                "term": "diktieren zu text",
                "forbidden_match": "diktieren",
                "replacement": "Spracheingabe",
                "opportunity": 80,
                "relevance": 70,
                "platform": "apple",
                "strategies": list(brand.STRATEGIES.keys()),
            }
        ]
        md = report_mod.build_report(
            config, [], keywords,
            now=datetime.datetime(2025, 1, 1, 12, 0, 0),
            brand_conflicts=brand_conflicts,
        )
        self.assertIn("Brand Conflicts", md)
        self.assertIn("diktieren zu text", md)
        self.assertIn("Spracheingabe", md)
        self.assertIn("keyword-field-only", md)

    def test_no_brand_conflicts_subsection_when_no_conflicts(self):
        import datetime
        import report as report_mod

        config = {
            "app_name": "Test App",
            "country": "de",
            "language": "de",
            "category": "Productivity",
        }
        keywords = [
            {"term": "spracheingabe", "opportunity": 80, "relevance": 70,
             "competition": 20, "split": "primary-candidate", "is_gap": False,
             "suggest": True},
        ]
        md = report_mod.build_report(
            config, [], keywords,
            now=datetime.datetime(2025, 1, 1, 12, 0, 0),
            brand_conflicts=[],
        )
        self.assertNotIn("Brand Conflicts", md)

    def test_no_brand_conflicts_subsection_when_none_passed(self):
        import datetime
        import report as report_mod

        config = {
            "app_name": "Test App",
            "country": "de",
            "language": "de",
            "category": "Productivity",
        }
        md = report_mod.build_report(
            config, [], [],
            now=datetime.datetime(2025, 1, 1, 12, 0, 0),
        )
        self.assertNotIn("Brand Conflicts", md)


if __name__ == "__main__":
    unittest.main()
