#!/usr/bin/env python3
"""Unit tests for keyword_expand.py's response parsers.

Both response bodies below are the literal, unmodified bodies captured from
a real request during development (see the skill's commit history) — the
Firefox-client and YouTube-client autocomplete endpoints use genuinely
different shapes, and a parser that silently returns [] on the wrong shape
is exactly the plausible-but-wrong failure mode worth pinning down.

Run: python3 tests/seo-aso-optimizer/test_keyword_expand.py
"""
import importlib.util
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

SCRIPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "skills" / "seo-aso-optimizer" / "scripts" / "keyword_expand.py"
)
spec = importlib.util.spec_from_file_location("keyword_expand", SCRIPT_PATH)
keyword_expand = importlib.util.module_from_spec(spec)
spec.loader.exec_module(keyword_expand)

# Captured live from suggestqueries.google.com, client=firefox, q="whisper desktop".
GOOGLE_RESPONSE = (
    '["whisper desktop",["whisper desktop","whisper desktop download",'
    '"whisper desktop windows","whisper desktop github",'
    '"whisper desktop windows download","whisper desktop app",'
    '"whisper desktop download free","whisper desktop gui",'
    '"whisper desktop windows github","whisper desktop mac"],[],'
    '{"google:suggestsubtypes":[[512],[512],[512],[512],[512],[512],[512],'
    '[22,30],[22,30],[22,30]]}]'
)

# Captured live from suggestqueries.google.com, client=youtube, q="whisper desktop".
YOUTUBE_RESPONSE = (
    'window.google.ac.h(["whisper desktop",'
    '[["whisper desktop",0,[512]],["whisper desktop download",0,[512]],'
    '["whisper colab",0,[512,546,650]],["whisper.ai",0,[512,546,650]]],'
    '{"k":1}])'
)


class GoogleParsing(unittest.TestCase):
    def test_extracts_flat_suggestion_strings(self):
        result = keyword_expand.parse_google_response(GOOGLE_RESPONSE)
        self.assertIn("whisper desktop download", result)
        self.assertIn("whisper desktop mac", result)
        self.assertEqual(len(result), 10)

    def test_empty_suggestions_returns_empty_list(self):
        result = keyword_expand.parse_google_response('["seed",[]]')
        self.assertEqual(result, [])


class YoutubeParsing(unittest.TestCase):
    def test_extracts_text_from_nested_triples(self):
        # This is the shape bug: YouTube items are [text, weight, [codes]],
        # not flat strings like the Firefox client — a parser written for
        # one shape silently yields [] (or garbage) against the other.
        result = keyword_expand.parse_youtube_response(YOUTUBE_RESPONSE)
        self.assertEqual(
            result,
            ["whisper desktop", "whisper desktop download", "whisper colab", "whisper.ai"],
        )

    def test_strips_jsonp_wrapper(self):
        result = keyword_expand.parse_youtube_response(YOUTUBE_RESPONSE)
        self.assertNotIn("window.google.ac.h", " ".join(result))


class QueryBuilding(unittest.TestCase):
    def test_covers_seed_letters_questions_and_modifiers(self):
        queries = keyword_expand.build_queries("seed")
        self.assertIn("seed", queries)
        self.assertIn("seed a", queries)
        self.assertIn("seed z", queries)
        self.assertIn("how seed", queries)
        self.assertIn("seed alternative", queries)
        # seed + 26 letters + question words + modifiers, no more no less
        expected = 1 + 26 + len(keyword_expand.QUESTION_WORDS) + len(keyword_expand.MODIFIERS)
        self.assertEqual(len(queries), expected)


if __name__ == "__main__":
    unittest.main()
