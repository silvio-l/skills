#!/usr/bin/env python3
"""Unit tests for fetch_open_chat_tab.py's Markdown rendering — the one part
of that script that is pure and deterministic (everything else drives a real
Safari tab via osascript and can't be unit tested).

Run: python3 tests/fetch-open-chat-tab/test_fetch_open_chat_tab.py
"""
import sys
import unittest
from pathlib import Path

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "fetch-open-chat-tab" / "scripts"))

from fetch_open_chat_tab import render_fallback_markdown, render_markdown  # noqa: E402


class TestRenderMarkdown(unittest.TestCase):
    def test_basic_structure(self):
        result = {
            "title": "My Conversation",
            "host": "chatgpt.com",
            "site": "chatgpt",
            "messages": [
                {"role": "user", "text": "Hallo"},
                {"role": "assistant", "text": "Hi there"},
            ],
        }
        md = render_markdown(result)
        self.assertIn("# My Conversation", md)
        self.assertIn("chatgpt.com", md)
        self.assertIn("## USER\nHallo", md)
        self.assertIn("## ASSISTANT\nHi there", md)
        # user message must precede the assistant reply in the rendered text
        self.assertLess(md.index("Hallo"), md.index("Hi there"))

    def test_missing_title_falls_back_to_untitled(self):
        result = {"host": "claude.ai", "site": "claude", "messages": []}
        md = render_markdown(result)
        self.assertIn("# Untitled", md)

    def test_empty_messages_still_renders_header(self):
        result = {"title": "Empty", "host": "gemini.google.com", "site": "gemini", "messages": []}
        md = render_markdown(result)
        self.assertIn("# Empty", md)
        self.assertNotIn("## USER", md)

    def test_role_is_uppercased(self):
        result = {"title": "T", "host": "h", "site": "s", "messages": [{"role": "assistant", "text": "x"}]}
        md = render_markdown(result)
        self.assertIn("## ASSISTANT", md)
        self.assertNotIn("## assistant", md)


class TestRenderFallbackMarkdown(unittest.TestCase):
    def test_includes_warning_banner_and_raw_text(self):
        result = {"title": "Some Page", "host": "example.com", "fallbackText": "raw body text here"}
        md = render_fallback_markdown(result)
        self.assertIn("UNSTRUCTURED FALLBACK", md)
        self.assertIn("example.com", md)
        self.assertIn("raw body text here", md)

    def test_missing_fallback_text_does_not_crash(self):
        result = {"title": "Empty Page", "host": "example.com"}
        md = render_fallback_markdown(result)
        self.assertIn("# Empty Page", md)
        self.assertIn("UNSTRUCTURED FALLBACK", md)


if __name__ == "__main__":
    unittest.main()
