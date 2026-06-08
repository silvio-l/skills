#!/usr/bin/env python3
"""Tests for the dotenv auto-loader in seo-audit/scripts/audit.py.

The loader exists so users don't have to remember to `source admin.env`
before every audit. It walks `--root` for a fixed list of KEY=VALUE
filenames, then any `--env-file` paths, and adds keys to `os.environ`
that are not already set — live shell values always win.

Run from the repo root:
    python3 -m unittest tests/seo-audit/test_dotenv_loader.py
"""

import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True

import audit as A  # noqa: E402


class ParseDotenvTest(unittest.TestCase):
    def test_basic_pairs(self):
        out = A._parse_dotenv("FOO=bar\nBAZ=qux\n")
        self.assertEqual(out, {"FOO": "bar", "BAZ": "qux"})

    def test_blank_and_comment_lines_ignored(self):
        text = "\n# leading comment\n   \nFOO=bar\n# tail comment\n"
        self.assertEqual(A._parse_dotenv(text), {"FOO": "bar"})

    def test_quotes_are_stripped(self):
        out = A._parse_dotenv('A="hello world"\nB=\'single\'\n')
        self.assertEqual(out, {"A": "hello world", "B": "single"})

    def test_export_prefix_supported(self):
        self.assertEqual(
            A._parse_dotenv("export FOO=bar\n"),
            {"FOO": "bar"},
        )

    def test_equals_inside_value_preserved(self):
        # Real-world: GitHub PATs, base64 tokens, JSON snippets.
        out = A._parse_dotenv("TOKEN=abc=def==\n")
        self.assertEqual(out, {"TOKEN": "abc=def=="})

    def test_hash_inside_value_preserved(self):
        # Real-world: passwords like `R9_4dl+a0#x` or URL fragments.
        # Only full-line comments are stripped; inline `#` stays.
        out = A._parse_dotenv("PASS=R9_4dl+a0#x\n")
        self.assertEqual(out, {"PASS": "R9_4dl+a0#x"})

    def test_lines_without_equals_ignored(self):
        out = A._parse_dotenv("FOO=bar\nnonsense\nBAZ=qux\n")
        self.assertEqual(out, {"FOO": "bar", "BAZ": "qux"})

    def test_empty_key_ignored(self):
        self.assertEqual(A._parse_dotenv("=value\n"), {})


class LoadDotenvFilesTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = self.tmp.name
        self.env = {}

    def tearDown(self):
        self.tmp.cleanup()

    def _write(self, name: str, body: str) -> str:
        path = os.path.join(self.root, name)
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)
        return path

    def test_no_files_no_changes(self):
        loaded = A._load_dotenv_files(self.root, env=self.env)
        self.assertEqual(loaded, [])
        self.assertEqual(self.env, {})

    def test_loads_admin_env(self):
        self._write("admin.env", "PAGESPEED_API_KEY=abc123\n")
        loaded = A._load_dotenv_files(self.root, env=self.env)
        self.assertEqual(self.env, {"PAGESPEED_API_KEY": "abc123"})
        self.assertEqual(len(loaded), 1)
        self.assertEqual(loaded[0][1], 1)  # one key added

    def test_existing_env_var_wins(self):
        self._write("admin.env", "FOO=from_file\n")
        self.env["FOO"] = "from_shell"
        A._load_dotenv_files(self.root, env=self.env)
        self.assertEqual(self.env["FOO"], "from_shell")

    def test_earlier_file_wins_over_later(self):
        # admin.env is checked before .env in DEFAULT_DOTENV_FILES.
        self._write("admin.env", "X=admin\n")
        self._write(".env", "X=base\nY=base\n")
        A._load_dotenv_files(self.root, env=self.env)
        self.assertEqual(self.env, {"X": "admin", "Y": "base"})

    def test_extra_files_loaded_before_defaults(self):
        extra = self._write("custom.env", "X=custom\n")
        self._write("admin.env", "X=admin\nY=admin\n")
        A._load_dotenv_files(
            self.root, extra_files=[extra], env=self.env,
        )
        self.assertEqual(self.env, {"X": "custom", "Y": "admin"})

    def test_extra_file_dedup_against_default(self):
        # If a user passes --env-file <root>/admin.env explicitly, the
        # same file must not be parsed twice (and the report line must
        # not show it twice either).
        admin = self._write("admin.env", "X=1\n")
        loaded = A._load_dotenv_files(
            self.root, extra_files=[admin], env=self.env,
        )
        self.assertEqual(len(loaded), 1)
        self.assertEqual(self.env, {"X": "1"})

    def test_missing_extra_file_silently_skipped(self):
        loaded = A._load_dotenv_files(
            self.root,
            extra_files=[os.path.join(self.root, "nope.env")],
            env=self.env,
        )
        self.assertEqual(loaded, [])

    def test_added_count_reflects_only_newly_set_keys(self):
        # Two keys in the file, one already in env → count must be 1.
        self._write("admin.env", "A=1\nB=2\n")
        self.env["A"] = "preset"
        loaded = A._load_dotenv_files(self.root, env=self.env)
        self.assertEqual(loaded[0][1], 1)
        self.assertEqual(self.env, {"A": "preset", "B": "2"})


if __name__ == "__main__":
    unittest.main()
