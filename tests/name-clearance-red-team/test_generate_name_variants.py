#!/usr/bin/env python3
"""Tests for name-clearance-red-team/scripts/generate_name_variants.py.

Covers the deterministic variant classes: this script feeds directly into
the search plan, so a silently-missing variant class here means a real
conflicting mark never gets searched for at all - a wrong-but-plausible
result no roundtrip check would catch.

Run from the repo root:
    python3 tests/name-clearance-red-team/test_generate_name_variants.py
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "name-clearance-red-team" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import generate_name_variants as G  # noqa: E402


class UmlautAsciiTests(unittest.TestCase):
    def test_ae_roundtrip(self):
        variants = G.umlaut_ascii_variants("Bär")
        self.assertIn("Baer", variants)
        self.assertIn("Bar", variants)

    def test_eszett_to_ss(self):
        variants = G.umlaut_ascii_variants("Straße")
        self.assertIn("Strasse", variants)

    def test_no_umlaut_no_variants(self):
        self.assertEqual(G.umlaut_ascii_variants("Zynqora"), [])

    def test_never_includes_input_itself(self):
        variants = G.umlaut_ascii_variants("Bär")
        self.assertNotIn("Bär", variants)


class SpacingVariantTests(unittest.TestCase):
    def test_camel_case_split(self):
        variants = G.spacing_variants("MyBrand")
        self.assertIn("My Brand", variants)
        self.assertIn("My-Brand", variants)

    def test_hyphen_to_space_and_joined(self):
        variants = G.spacing_variants("foo-bar")
        self.assertIn("foo bar", variants)
        self.assertIn("foobar", variants)

    def test_space_to_hyphen_and_joined(self):
        variants = G.spacing_variants("foo bar")
        self.assertIn("foo-bar", variants)
        self.assertIn("foobar", variants)

    def test_never_includes_input_itself(self):
        variants = G.spacing_variants("foo-bar")
        self.assertNotIn("foo-bar", variants)


class TranspositionTests(unittest.TestCase):
    def test_all_adjacent_pairs_generated(self):
        variants = G.adjacent_transpositions("abcd")
        self.assertEqual(set(variants), {"bacd", "acbd", "abdc"})

    def test_deduplicated(self):
        variants = G.adjacent_transpositions("aab")
        self.assertEqual(len(variants), len(set(variants)))

    def test_never_includes_input_itself(self):
        self.assertNotIn("abcd", G.adjacent_transpositions("abcd"))


class PluralHeuristicTests(unittest.TestCase):
    def test_german_default_e_suffix(self):
        self.assertEqual(G.plural_heuristic_de("Hund"), "Hunde")

    def test_german_skips_already_plural_looking_word(self):
        self.assertIsNone(G.plural_heuristic_de("Lehrer"))

    def test_english_default_s_suffix(self):
        self.assertEqual(G.plural_heuristic_en("cat"), "cats")

    def test_english_es_after_sibilant(self):
        self.assertEqual(G.plural_heuristic_en("box"), "boxes")

    def test_english_consonant_y_to_ies(self):
        self.assertEqual(G.plural_heuristic_en("company"), "companies")

    def test_english_vowel_y_keeps_s(self):
        self.assertEqual(G.plural_heuristic_en("day"), "days")


class PhoneticVariantTests(unittest.TestCase):
    def test_german_rule_fires_for_de(self):
        # phonetic_variants matches against the lowercased candidate too, so
        # "Phon" (capital P) still yields the lowercase "fon" substitution.
        variants = G.phonetic_variants("Phon", ["de"])
        self.assertTrue(any(v == "fon" for v, lang, rule in variants))

    def test_de_only_rule_does_not_fire_for_en(self):
        # the "ei"<->"ai" rule is DE-only; requesting only "en" must not produce it
        variants = G.phonetic_variants("Kaiser", ["en"])
        self.assertFalse(any(rule == "ei" for _, _, rule in variants))

    def test_no_languages_no_variants(self):
        self.assertEqual(G.phonetic_variants("Phon", []), [])


class TransliterationTests(unittest.TestCase):
    def test_latin_to_cyrillic_confusable(self):
        variants = G.transliteration_variants("apex")
        translit = "".join(G.LATIN_TO_CYRILLIC.get(ch, ch) for ch in "apex")
        self.assertIn(translit, variants)

    def test_bidirectional_table_consistency(self):
        for latin, cyrillic in G.LATIN_TO_CYRILLIC.items():
            self.assertEqual(G.CYRILLIC_TO_LATIN[cyrillic], latin)

    def test_no_confusable_chars_no_variants(self):
        self.assertEqual(G.transliteration_variants("zzz"), [])


class GenerateEndToEndTests(unittest.TestCase):
    def test_no_duplicates(self):
        result = G.generate("Bär", ["de", "en"])
        variants = [entry["variant"] for entry in result["variants"]]
        self.assertEqual(len(variants), len(set(variants)))

    def test_input_never_appears_as_its_own_variant(self):
        result = G.generate("Zynqora", ["de", "en"])
        variants = [entry["variant"] for entry in result["variants"]]
        self.assertNotIn("Zynqora", variants)

    def test_semantic_hint_slot_per_language(self):
        result = G.generate("Zynqora", ["de", "en", "fr"])
        self.assertEqual(len(result["semantic_hint"]), 3)
        self.assertEqual({slot["language"] for slot in result["semantic_hint"]}, {"de", "en", "fr"})
        for slot in result["semantic_hint"]:
            self.assertIsNone(slot["translation"])

    def test_every_variant_has_required_fields(self):
        result = G.generate("Bär", ["de"])
        for entry in result["variants"]:
            self.assertIn("variant", entry)
            self.assertIn("class", entry)
            self.assertIn("rule", entry)
            self.assertIn("search_priority", entry)


if __name__ == "__main__":
    unittest.main()
