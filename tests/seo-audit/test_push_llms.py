#!/usr/bin/env python3
"""Tests for the llms.txt / llms-full.txt generator.

The generator must:
* produce llmstxt.org-shaped llms.txt from a domain doc (CONTEXT.md etc.),
* concatenate docs/**.md for llms-full.txt,
* be idempotent (byte-identical output on repeated runs).
"""

import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from push import llms_generator as LLMS  # noqa: E402


SAMPLE_CONTEXT_MD = """# Sample Site

> Eine sanfte Web-App, die Texte teilt.

## Über

Mehr Prosa hier.

## Anti-Vokabular

| Begriff | Stattdessen | Grund |
| ------- | ----------- | ----- |
| App     | Web App     | Marke |
"""

SAMPLE_DOCS_AUDIENCE = """# Zielgruppe

Menschen, die kurz Text loswerden wollen.
"""


def _write(p: pathlib.Path, content: str) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


class GenerateLlmsTxt(unittest.TestCase):
    def test_generates_minimal_llms_txt_from_context(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            ctx = tmp / "CONTEXT.md"
            _write(ctx, SAMPLE_CONTEXT_MD)
            out_dir = tmp / "public"
            out_dir.mkdir()

            written = LLMS.generate(ctx, out_dir)
            self.assertTrue(written.exists())
            self.assertEqual(written.name, "llms.txt")

            body = written.read_text(encoding="utf-8")
            # Section 1 of llmstxt.org: H1 title.
            self.assertTrue(body.startswith("# Sample Site\n"))
            # Blockquote summary follows.
            self.assertIn("> Eine sanfte Web-App", body)

    def test_includes_optional_audience_doc_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            ctx = tmp / "CONTEXT.md"
            _write(ctx, SAMPLE_CONTEXT_MD)
            _write(tmp / "docs" / "audience.md", SAMPLE_DOCS_AUDIENCE)
            out_dir = tmp / "public"
            out_dir.mkdir()

            written = LLMS.generate(ctx, out_dir)
            body = written.read_text(encoding="utf-8")
            # Optional section lists audience.md as a doc link.
            self.assertIn("audience.md", body)

    def test_idempotent_byte_identical_output(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            ctx = tmp / "CONTEXT.md"
            _write(ctx, SAMPLE_CONTEXT_MD)
            out_dir = tmp / "public"
            out_dir.mkdir()

            first = LLMS.generate(ctx, out_dir).read_bytes()
            second = LLMS.generate(ctx, out_dir).read_bytes()
            self.assertEqual(first, second)

    def test_writes_into_provided_output_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            ctx = tmp / "CONTEXT.md"
            _write(ctx, SAMPLE_CONTEXT_MD)
            other = tmp / "dist"
            other.mkdir()

            written = LLMS.generate(ctx, other)
            self.assertEqual(written.parent, other)


class GenerateLlmsFullTxt(unittest.TestCase):
    def test_full_concatenates_context_only_when_no_docs(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            ctx = tmp / "CONTEXT.md"
            _write(ctx, SAMPLE_CONTEXT_MD)
            out_dir = tmp / "public"
            out_dir.mkdir()

            written = LLMS.generate(ctx, out_dir, full=True)
            self.assertEqual(written.name, "llms-full.txt")
            body = written.read_text(encoding="utf-8")
            self.assertIn("Sample Site", body)
            self.assertIn("Anti-Vokabular", body)

    def test_full_concatenates_docs_markdown_when_present(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            ctx = tmp / "CONTEXT.md"
            _write(ctx, SAMPLE_CONTEXT_MD)
            _write(tmp / "docs" / "audience.md", SAMPLE_DOCS_AUDIENCE)
            out_dir = tmp / "public"
            out_dir.mkdir()

            written = LLMS.generate(ctx, out_dir, full=True)
            body = written.read_text(encoding="utf-8")
            self.assertIn("Zielgruppe", body)
            self.assertIn("Sample Site", body)

    def test_full_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            ctx = tmp / "CONTEXT.md"
            _write(ctx, SAMPLE_CONTEXT_MD)
            _write(tmp / "docs" / "audience.md", SAMPLE_DOCS_AUDIENCE)
            out_dir = tmp / "public"
            out_dir.mkdir()
            first = LLMS.generate(ctx, out_dir, full=True).read_bytes()
            second = LLMS.generate(ctx, out_dir, full=True).read_bytes()
            self.assertEqual(first, second)


class GenerateSnapshot(unittest.TestCase):
    """Golden-snapshot test against a frozen expected output."""

    EXPECTED = (
        "# Sample Site\n"
        "\n"
        "> Eine sanfte Web-App, die Texte teilt.\n"
        "\n"
        "## Docs\n"
        "\n"
        "- [Domain Doc](CONTEXT.md): Anti-Vokabular und Markenkontext\n"
    )

    def test_minimal_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp = pathlib.Path(tmp)
            ctx = tmp / "CONTEXT.md"
            _write(ctx, SAMPLE_CONTEXT_MD)
            out_dir = tmp / "public"
            out_dir.mkdir()

            body = LLMS.generate(ctx, out_dir).read_text(encoding="utf-8")
            self.assertEqual(body, self.EXPECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
