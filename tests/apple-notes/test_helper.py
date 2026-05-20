#!/usr/bin/env python3
"""Tests for apple-notes/scripts/_helper.py.

Run from the repo root with `python3 tests/apple-notes/test_helper.py`
or `python3 -m unittest discover tests`.

Lives outside `skills/` on purpose: the `skills` CLI bundles a skill
directory as-is, and shipping tests to every install would just bloat
the bundle. See CLAUDE.md → "Tooling and testing".
"""

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "apple-notes" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

# Suppress __pycache__ creation under the skill directory so tests do not
# leave bytecode in the bundle.
sys.dont_write_bytecode = True

import _helper as H  # noqa: E402


# Minimal 1x1 PNG (base64). Used wherever we need a valid image payload.
PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8A"
    "AAAASUVORK5CYII="
)


def img(mime: str = "png", payload: str = PNG_B64) -> str:
    return f'<img src="data:image/{mime};base64,{payload}">'


class StripBase64(unittest.TestCase):
    def test_single_image_becomes_placeholder(self):
        self.assertEqual(H.strip_base64(img()), "[image:1]")

    def test_multiple_images_get_sequential_indices(self):
        html = f"<p>a</p>{img()}<p>b</p>{img('jpeg')}<p>c</p>"
        self.assertEqual(
            H.strip_base64(html),
            "<p>a</p>[image:1]<p>b</p>[image:2]<p>c</p>",
        )

    def test_no_image_passes_through_untouched(self):
        html = "<p>plain <b>text</b></p>"
        self.assertEqual(H.strip_base64(html), html)

    def test_whitespace_inside_base64_is_tolerated(self):
        chunked = PNG_B64[:20] + "\n  " + PNG_B64[20:]
        html = f'<img src="data:image/png;base64,{chunked}">'
        self.assertEqual(H.strip_base64(html), "[image:1]")

    def test_uppercase_img_tag_matches(self):
        html = f'<IMG SRC="data:image/PNG;base64,{PNG_B64}">'
        self.assertEqual(H.strip_base64(html), "[image:1]")

    def test_single_quoted_src_matches(self):
        html = f"<img src='data:image/png;base64,{PNG_B64}'>"
        self.assertEqual(H.strip_base64(html), "[image:1]")

    def test_non_base64_img_is_left_alone(self):
        # AppleScript also produces <object> tags for non-inline attachments;
        # those should pass through (the SKILL.md reports them but cannot
        # extract them).
        html = '<object data="x-coredata://..." type="image/png"></object>'
        self.assertEqual(H.strip_base64(html), html)


class ToText(unittest.TestCase):
    def test_block_tags_become_newlines(self):
        html = "<div>line one</div><div>line two</div>"
        self.assertEqual(H.to_text(html), "line one\nline two")

    def test_br_becomes_newline(self):
        self.assertEqual(H.to_text("a<br>b<br/>c"), "a\nb\nc")

    def test_entities_are_decoded(self):
        self.assertEqual(
            H.to_text("<p>5 &lt; 10 &amp; 20 &gt; 5</p>"),
            "5 < 10 & 20 > 5",
        )

    def test_inline_images_are_placed_on_their_own_line(self):
        # Image placeholder must not glue to adjacent text. Block-closing
        # tags before the image collapse with the placeholder's leading
        # newline into a blank-line separator; the image-to-next-paragraph
        # side stays a single newline because <p> has no preceding </p>.
        html = f"<p>before</p>{img()}<p>after</p>"
        self.assertEqual(H.to_text(html), "before\n\n[image:1]\nafter")

    def test_collapses_runs_of_blank_lines(self):
        html = "<p>a</p><p></p><p></p><p></p><p>b</p>"
        self.assertEqual(H.to_text(html), "a\n\nb")

    def test_strips_leading_and_trailing_whitespace(self):
        self.assertEqual(H.to_text("\n\n  <p>x</p>\n\n"), "x")

    def test_empty_input_returns_empty_string(self):
        self.assertEqual(H.to_text(""), "")

    def test_unicode_passes_through(self):
        self.assertEqual(H.to_text("<p>Schiebéregler 🇩🇪</p>"), "Schiebéregler 🇩🇪")

    def test_headings_and_list_items_get_newlines(self):
        html = "<h1>Title</h1><ul><li>one</li><li>two</li></ul>"
        self.assertEqual(H.to_text(html), "Title\none\ntwo")


class ExtractImages(unittest.TestCase):
    def test_writes_files_and_reports_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = f"<p>x</p>{img()}<p>y</p>{img('jpeg')}"
            result = H.extract_images(html, tmp)
            self.assertEqual(len(result), 2)
            for entry in result:
                self.assertTrue(os.path.isfile(entry["path"]))
                self.assertGreater(entry["bytes"], 0)
                self.assertEqual(
                    entry["bytes"], os.path.getsize(entry["path"])
                )
            self.assertEqual(result[0]["mime"], "image/png")
            self.assertTrue(result[0]["path"].endswith(".png"))
            self.assertEqual(result[1]["mime"], "image/jpeg")
            self.assertTrue(result[1]["path"].endswith(".jpg"))

    def test_indices_are_one_based_and_sequential(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = img() + img() + img()
            result = H.extract_images(html, tmp)
            self.assertEqual([e["index"] for e in result], [1, 2, 3])

    def test_unknown_mime_falls_back_to_bin_extension(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = f'<img src="data:image/x-weird;base64,{PNG_B64}">'
            result = H.extract_images(html, tmp)
            self.assertEqual(len(result), 1)
            self.assertTrue(result[0]["path"].endswith(".bin"))
            self.assertEqual(result[0]["mime"], "image/x-weird")

    def test_broken_base64_is_skipped_with_stderr(self):
        with tempfile.TemporaryDirectory() as tmp:
            html = '<img src="data:image/png;base64,!!!notbase64!!!">'
            result = H.extract_images(html, tmp)
            self.assertEqual(result, [])
            self.assertEqual(os.listdir(tmp), [])

    def test_empty_input_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(H.extract_images("", tmp), [])
            self.assertEqual(os.listdir(tmp), [])

    def test_output_dir_is_created_if_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            nested = os.path.join(tmp, "a", "b", "c")
            self.assertFalse(os.path.exists(nested))
            result = H.extract_images(img(), nested)
            self.assertEqual(len(result), 1)
            self.assertTrue(os.path.isdir(nested))

    def test_filename_contains_short_content_hash(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = H.extract_images(img(), tmp)
            fname = os.path.basename(result[0]["path"])
            self.assertRegex(fname, r"^image-01-[0-9a-f]{8}\.png$")


class CliDispatcher(unittest.TestCase):
    """Smoketest the CLI surface — argv parsing, stdin handling, exit codes."""

    SCRIPT = str(SCRIPTS_DIR / "_helper.py")

    def _run(self, args, stdin: str = "") -> subprocess.CompletedProcess:
        env = dict(os.environ)
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        return subprocess.run(
            [sys.executable, self.SCRIPT, *args],
            input=stdin,
            capture_output=True,
            text=True,
            env=env,
        )

    def test_to_text_subcommand(self):
        r = self._run(["to-text"], stdin="<p>hi</p>")
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "hi")

    def test_strip_base64_subcommand(self):
        r = self._run(["strip-base64"], stdin=img())
        self.assertEqual(r.returncode, 0)
        self.assertEqual(r.stdout.strip(), "[image:1]")

    def test_extract_images_emits_valid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            r = self._run(["extract-images", tmp], stdin=img())
            self.assertEqual(r.returncode, 0)
            parsed = json.loads(r.stdout)
            self.assertEqual(len(parsed), 1)
            self.assertEqual(set(parsed[0].keys()), {"index", "path", "bytes", "mime"})

    def test_extract_images_requires_out_dir(self):
        r = self._run(["extract-images"], stdin=img())
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("extract-images requires", r.stderr)

    def test_no_subcommand_prints_usage(self):
        r = self._run([])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("usage:", r.stderr)

    def test_unknown_subcommand_errors(self):
        r = self._run(["bogus"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("unknown subcommand", r.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
