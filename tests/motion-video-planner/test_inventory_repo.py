#!/usr/bin/env python3
"""Tests for motion-video-planner/scripts/inventory_repo.py.

The inventory decides what the planner reads and what it reports as
"deliberately not read". A misclassification is silent: a logo filed as
generic media, node_modules leaking into the walk, or an issue number
reported as a brand color all produce a plausible but wrong context file.

Run from the repo root:
    python3 tests/motion-video-planner/test_inventory_repo.py
"""

import os
import pathlib
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
import zlib

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "motion-video-planner" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import inventory_repo as I  # noqa: E402


def png_bytes(width, height):
    def chunk(tag, data):
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\0" + b"\0\0\0" * width for _ in range(height))
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")


def jpeg_bytes(width, height):
    # SOI, APP0 stub, SOF0 with the frame size, EOI - enough for the header parser.
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\0" + b"\x01\x01\0\0\x01\0\x01\0\0"
    sof0 = b"\xff\xc0" + struct.pack(">HBHHB", 11, 8, height, width, 1) + b"\x01\x11\0"
    return b"\xff\xd8" + app0 + sof0 + b"\xff\xd9"


class Fixture:
    """A small product repo with every category the inventory distinguishes."""

    FILES = {
        "README.md": "# Acme\nFixes #123 and #4567.\nBrand color #FF5500.\n",
        "CHANGELOG.md": "## 1.0\n- shipped\n",
        "src/app.ts": "export const accent = '#ff5500';\n",
        "src/styles/global.css": "body { font-family: 'Inter', sans-serif; color: #0B122A; }\n",
        "design-tokens/primitives.tokens.json": '{"accent": "#ff5500", "ink": "#0b122a"}\n',
        "src/locales/de.json": '{"hello": "Hallo"}\n',
        "lib/l10n/app_en.arb": '{"hello": "Hello"}\n',
        "tests/test_app.py": "def test_x():\n    pass\n",
        "src/app.test.ts": "it('works', () => {});\n",
        "marketing/press-release.md": "Acme launches.\n",
        "fastlane/metadata/de-DE/description.txt": "Beschreibung\n",
        "assets/logo.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 240 80"></svg>\n',
        "assets/fonts/Inter.woff2": b"wOF2\0\0binary",
        "assets/sfx/click.wav": b"RIFF\0\0\0\0WAVE",
        "assets/demo.mp4": b"\0\0\0\x18ftypmp42",
        "dist/bundle.js": "console.log(1)\n",
        "web/app.min.js": "!function(){}()\n",
        "package-lock.json": "{}\n",
        "blob.dat": b"\x00\x01\x02binary",
        "notes.unknownext": "plain text\n",
    }

    def __init__(self, git):
        self.root = tempfile.mkdtemp(prefix="inv-test-")
        for rel, content in self.FILES.items():
            self.write(rel, content)
        self.write("assets/hero.png", png_bytes(64, 32))
        self.write("assets/photo.jpg", jpeg_bytes(1920, 1080))
        self.write("node_modules/dep/index.js", "module.exports = '#123456';\n")
        if git:
            self.write(".gitignore", "node_modules/\ndist/\n")
            subprocess.run(["git", "init", "-q", self.root], check=True)

    def write(self, rel, content):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(path, mode) as fh:
            fh.write(content)

    def cleanup(self):
        shutil.rmtree(self.root, ignore_errors=True)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture(git=False)
        self.inv = I.build_inventory(self.fx.root)

    def tearDown(self):
        self.fx.cleanup()

    def all_paths(self):
        cats = ("docs", "tests", "media", "generated", "dependency_locks", "binary_other")
        paths = set()
        for c in cats:
            for x in self.inv[c]:
                paths.add(x["path"] if isinstance(x, dict) else x)
        return paths

    def test_node_modules_and_dist_are_excluded_with_reason(self):
        self.assertIn("node_modules", self.inv["excluded_dirs"])
        self.assertIn("dist", self.inv["excluded_dirs"])
        self.assertNotIn("node_modules/dep/index.js", self.all_paths())
        self.assertEqual(self.inv["excluded_dirs"]["node_modules"]["reason"], "installed dependencies")

    def test_excluded_dependency_colors_never_reach_the_palette(self):
        self.assertNotIn("#123456", [c["hex"] for c in self.inv["colors"]])

    def test_tests_detected_by_dir_and_by_suffix(self):
        self.assertIn("tests/test_app.py", self.inv["tests"])
        self.assertIn("src/app.test.ts", self.inv["tests"])

    def test_ui_strings_from_locale_dir_and_arb(self):
        self.assertIn("src/locales/de.json", self.inv["ui_strings"])
        self.assertIn("lib/l10n/app_en.arb", self.inv["ui_strings"])

    def test_marketing_material_tagged(self):
        self.assertIn("marketing/press-release.md", self.inv["marketing"])
        self.assertIn("fastlane/metadata/de-DE/description.txt", self.inv["marketing"])

    def test_logo_is_brand_candidate_with_svg_viewbox_size(self):
        self.assertIn("assets/logo.svg", self.inv["brand_candidates"])
        logo = next(m for m in self.inv["media"] if m["path"] == "assets/logo.svg")
        self.assertEqual(logo["px"], [240, 80])

    def test_png_and_jpeg_pixel_sizes_from_headers(self):
        media = {m["path"]: m for m in self.inv["media"]}
        self.assertEqual(media["assets/hero.png"]["px"], [64, 32])
        self.assertEqual(media["assets/photo.jpg"]["px"], [1920, 1080])

    def test_media_kinds(self):
        kinds = {m["path"]: m["kind"] for m in self.inv["media"]}
        self.assertEqual(kinds["assets/fonts/Inter.woff2"], "font")
        self.assertEqual(kinds["assets/sfx/click.wav"], "audio")
        self.assertEqual(kinds["assets/demo.mp4"], "video")

    def test_generated_lock_and_binary_are_separated(self):
        self.assertIn("web/app.min.js", self.inv["generated"])
        self.assertIn("package-lock.json", self.inv["dependency_locks"])
        self.assertIn("blob.dat", self.inv["binary_other"])
        self.assertEqual(self.inv["counts"].get("other-text"), 1)  # notes.unknownext

    def test_issue_numbers_in_prose_are_not_colors(self):
        hexes = [c["hex"] for c in self.inv["colors"]]
        self.assertNotIn("#112233", hexes)  # "#123" expanded would be this
        self.assertNotIn("#4567", hexes)

    def test_token_file_colors_rank_first_and_hex_is_normalized(self):
        top_two = [c["hex"] for c in self.inv["colors"][:2]]
        self.assertEqual(set(top_two), {"#ff5500", "#0b122a"})
        accent = next(c for c in self.inv["colors"] if c["hex"] == "#ff5500")
        self.assertEqual(accent["token_files"], 1)
        self.assertGreaterEqual(accent["files"], 3)

    def test_font_family_extracted(self):
        self.assertIn("Inter", [f["family"] for f in self.inv["fonts"]])

    def test_key_docs(self):
        self.assertIn("README.md", self.inv["key_docs"])
        self.assertIn("CHANGELOG.md", self.inv["key_docs"])

    def test_markdown_report_states_heuristics_and_exclusions(self):
        md = I.render_markdown(self.inv)
        self.assertIn("heuristic", md)
        self.assertIn("Deliberately not read", md)
        self.assertIn("`node_modules/` - installed dependencies", md)


class GitListingTests(unittest.TestCase):
    def setUp(self):
        if shutil.which("git") is None:
            self.skipTest("git not installed")
        self.fx = Fixture(git=True)
        self.inv = I.build_inventory(self.fx.root)

    def tearDown(self):
        self.fx.cleanup()

    def test_gitignore_is_respected_and_untracked_files_included(self):
        self.assertTrue(self.inv["listing_source"].startswith("git ls-files"))
        self.assertIn("README.md", self.inv["key_docs"])  # untracked but not ignored
        self.assertIn("node_modules", self.inv["excluded_dirs"])  # present, ignored
        self.assertNotIn("dist/bundle.js", self.inv["generated"])


class CliTests(unittest.TestCase):
    def test_missing_directory_exits_2(self):
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
        r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "inventory_repo.py"), "/nonexistent-dir-xyz"],
                           capture_output=True, text=True, env=env)
        self.assertEqual(r.returncode, 2)
        self.assertIn("not a directory", r.stderr)

    def test_json_output_written(self):
        fx = Fixture(git=False)
        try:
            out = os.path.join(fx.root, "..", os.path.basename(fx.root) + ".json")
            env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
            r = subprocess.run([sys.executable, str(SCRIPTS_DIR / "inventory_repo.py"), fx.root, "--json", out],
                               capture_output=True, text=True, env=env)
            self.assertEqual(r.returncode, 0, r.stderr)
            import json
            with open(out) as fh:
                data = json.load(fh)
            self.assertEqual(data["root"], os.path.abspath(fx.root))
            os.remove(out)
        finally:
            fx.cleanup()


if __name__ == "__main__":
    unittest.main(verbosity=1)
