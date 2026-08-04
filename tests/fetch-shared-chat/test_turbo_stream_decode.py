#!/usr/bin/env python3
"""Unit tests for the from-scratch turbo-stream decoder used by fetch-shared-chat.

Run: python3 tests/fetch-shared-chat/test_turbo_stream_decode.py

Fixtures below are hand-constructed wire-format literals (not captured real
conversation data — that would leak private chat content into the repo) with
manually verified expected output, cross-checked against the algorithm in
turbo-stream v2.4.1's own source (remix-run/turbo-stream, MIT).
"""
import json
import math
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "fetch-shared-chat" / "scripts"))

from turbo_stream_decode import decode_first_line  # noqa: E402


class TestTurboStreamDecode(unittest.TestCase):
    def test_flat_object(self):
        wire = json.dumps([{"_1": 2, "_3": 4}, "a", 1, "b", 2])
        self.assertEqual(decode_first_line(wire), {"a": 1, "b": 2})

    def test_nested_array_of_references(self):
        wire = json.dumps([{"_1": 2}, "list", [3, 4, 5], 10, 20, 30])
        self.assertEqual(decode_first_line(wire), {"list": [10, 20, 30]})

    def test_sentinels_null_undefined_nan(self):
        # Sentinel values (-5=NULL, -7=UNDEFINED, -2=NAN) sit directly in the
        # key/value *index* slot of a pair and must never touch values[] at all
        # -- indices 2, 4, 6 below are unused filler for exactly that reason.
        wire = json.dumps([{"_1": -5, "_3": -7, "_5": -2}, "a", None, "c", None, "e", None])
        result = decode_first_line(wire)
        self.assertIsNone(result["a"])
        self.assertIsNone(result["c"])
        self.assertTrue(math.isnan(result["e"]))

    def test_repeated_reference_is_shared_not_duplicated_wrongly(self):
        # {"a": {"x": 1}, "b": {"x": 1}} where both keys point at the same chunk (index 2).
        # index 4 is an unused filler slot (nothing references it).
        wire = json.dumps([{"_1": 2, "_3": 2}, "a", {"_5": 6}, "b", None, "x", 1])
        result = decode_first_line(wire)
        self.assertEqual(result["a"], {"x": 1})
        self.assertEqual(result["b"], {"x": 1})

    def test_string_type_tagged_array_is_not_mistaken_for_plain_array(self):
        # A Date chunk ("D" tag): we only need the readable literal, not a real Date.
        wire = json.dumps([{"_1": 2}, "when", ["D", "2026-01-01T00:00:00.000Z"]])
        result = decode_first_line(wire)
        self.assertEqual(result["when"], "2026-01-01T00:00:00.000Z")

    def test_deferred_promise_resolves_to_none_not_a_crash(self):
        wire = json.dumps([{"_1": 2}, "pending", ["P", 99]])
        result = decode_first_line(wire)
        self.assertIsNone(result["pending"])


if __name__ == "__main__":
    unittest.main()
