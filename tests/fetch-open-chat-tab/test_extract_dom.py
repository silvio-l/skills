#!/usr/bin/env python3
"""Unit tests for the pure functions in fetch-open-chat-tab's extract_dom.js:
site detection, the dedup fingerprint, and the numeric-id reordering used to
fix virtualized-scroll collection order (claude.ai) without disturbing sites
whose natural DOM order is already correct (chatgpt.com).

Run: python3 tests/fetch-open-chat-tab/test_extract_dom.py

These call the *actual* extract_dom.js via Node (module.exports branch at
the bottom of that file), not a reimplementation — a change to the real
site-detection regexes or the ordering rule is caught here directly.
"""
import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

EXTRACT_DOM = Path(__file__).resolve().parents[2] / "skills" / "fetch-open-chat-tab" / "scripts" / "extract_dom.js"


def call(fn_name, args_json):
    """Run `require(EXTRACT_DOM).fn_name(...args)` under Node and return the parsed JSON result."""
    script = (
        f"const lib = require({json.dumps(str(EXTRACT_DOM))});"
        f"const args = {args_json};"
        f"console.log(JSON.stringify(lib.{fn_name}(...args)));"
    )
    proc = subprocess.run(
        ["node", "-e", script],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
        timeout=15,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"node failed: {proc.stderr}")
    return json.loads(proc.stdout)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestDetectSite(unittest.TestCase):
    def test_chatgpt_com(self):
        self.assertEqual(call("detectSite", '["chatgpt.com", "/c/abc"]'), "chatgpt")

    def test_chat_openai_com_legacy_domain(self):
        self.assertEqual(call("detectSite", '["chat.openai.com", "/c/abc"]'), "chatgpt")

    def test_claude_ai(self):
        self.assertEqual(call("detectSite", '["claude.ai", "/chat/abc"]'), "claude")

    def test_gemini_google_com(self):
        self.assertEqual(call("detectSite", '["gemini.google.com", "/app/abc"]'), "gemini")

    def test_unrecognized_host_returns_null(self):
        self.assertIsNone(call("detectSite", '["example.com", "/"]'))

    def test_lookalike_subdomain_is_not_spoofed(self):
        # "claude.ai" must anchor at the end of the hostname -- a hostile
        # subdomain must not be trusted with the claude.ai extractor.
        self.assertIsNone(call("detectSite", '["claude.ai.evil-attacker.com", "/x"]'))
        self.assertIsNone(call("detectSite", '["notclaude.ai", "/x"]'))

    def test_subdomain_of_real_host_still_matches(self):
        self.assertEqual(call("detectSite", '["www.claude.ai", "/chat/abc"]'), "claude")

    def test_case_insensitive(self):
        self.assertEqual(call("detectSite", '["ChatGPT.com", "/c/abc"]'), "chatgpt")


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestFingerprint(unittest.TestCase):
    def test_same_id_same_role_collides(self):
        self.assertEqual(
            call("fingerprint", '["user", "hello", "id-1"]'),
            call("fingerprint", '["user", "different text now", "id-1"]'),
        )

    def test_id_takes_priority_over_text(self):
        # Two messages with the same id must fingerprint identically even if
        # the text differs (e.g. streaming re-render mid-collection).
        a = call("fingerprint", '["assistant", "partial...", "msg-42"]')
        b = call("fingerprint", '["assistant", "partial... now complete", "msg-42"]')
        self.assertEqual(a, b)

    def test_no_id_falls_back_to_exact_text(self):
        a = call("fingerprint", '["user", "hello", null]')
        b = call("fingerprint", '["user", "hello", null]')
        c = call("fingerprint", '["user", "hello world", null]')
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)

    def test_different_roles_never_collide(self):
        a = call("fingerprint", '["user", "same text", null]')
        b = call("fingerprint", '["assistant", "same text", null]')
        self.assertNotEqual(a, b)


@unittest.skipUnless(shutil.which("node"), "node is not installed")
class TestOrderMessages(unittest.TestCase):
    def test_numeric_ids_sorted_ascending(self):
        msgs = [
            {"id": "9", "role": "user", "text": "i"},
            {"id": "2", "role": "assistant", "text": "a"},
            {"id": "1", "role": "user", "text": "u"},
        ]
        result = call("orderMessages", f"[{json.dumps(msgs)}]")
        self.assertEqual([m["id"] for m in result], ["1", "2", "9"])

    def test_non_numeric_ids_keep_insertion_order(self):
        # ChatGPT's UUID ids: already-correct DOM/insertion order must survive
        # untouched, not get shuffled by a string sort.
        msgs = [
            {"id": "c7f19071-uuid", "role": "user", "text": "second"},
            {"id": "a462317d-uuid", "role": "assistant", "text": "first"},
        ]
        result = call("orderMessages", f"[{json.dumps(msgs)}]")
        self.assertEqual([m["text"] for m in result], ["second", "first"])

    def test_missing_ids_keep_insertion_order(self):
        # Gemini has no stable id at all (None/null for every message).
        msgs = [
            {"id": None, "role": "user", "text": "first"},
            {"id": None, "role": "assistant", "text": "second"},
        ]
        result = call("orderMessages", f"[{json.dumps(msgs)}]")
        self.assertEqual([m["text"] for m in result], ["first", "second"])

    def test_mixed_numeric_and_missing_ids_not_sorted(self):
        # A single non-numeric/missing id anywhere disqualifies numeric
        # sorting for the whole batch -- partial numeric ids are not a
        # reliable enough signal to reorder by.
        msgs = [
            {"id": "3", "role": "user", "text": "a"},
            {"id": None, "role": "assistant", "text": "b"},
        ]
        result = call("orderMessages", f"[{json.dumps(msgs)}]")
        self.assertEqual([m["text"] for m in result], ["a", "b"])

    def test_empty_list(self):
        self.assertEqual(call("orderMessages", "[[]]"), [])

    def test_does_not_mutate_input_order_semantics_for_single_item(self):
        msgs = [{"id": "5", "role": "user", "text": "only"}]
        result = call("orderMessages", f"[{json.dumps(msgs)}]")
        self.assertEqual(result, msgs)


if __name__ == "__main__":
    unittest.main()
