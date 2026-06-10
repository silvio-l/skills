#!/usr/bin/env python3
"""Tests for humanize-text/scripts/humanize.py — slice 05 (entry script).

Observable-behaviour only: CLI-level tests via subprocess.
No internal helpers tested directly.

Acceptance criteria covered:
  AC4 — --mode scan|score, --threshold, --format json|text, --lang passthrough
  AC5 — slop_scanner and slop_scorer remain individually CLI-callable (wired)
  AC6 — determinism; no LLM/network calls

Run from repo root:
    python3 tests/humanize-text/test_humanize_cli.py
"""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "humanize-text" / "scripts"
SKILL_DIR = REPO_ROOT / "skills" / "humanize-text"

# ---------------------------------------------------------------------------
# DE text with known tier-1 patterns
# ---------------------------------------------------------------------------
_DE_SLOP_TEXT = (
    "Zudem ist das ein wichtiger Punkt.\n"
    "Darüber hinaus gibt es weitere Aspekte.\n"
    "Es ist wichtig zu beachten, dass wir aufpassen.\n"
)

# EN text with known tier-1 patterns
_EN_SLOP_TEXT = (
    "We need to leverage our existing infrastructure.\n"
    "It is worth noting that this groundbreaking approach delves into the tapestry.\n"
    "The landscape is robust and crucial for fostering collaboration.\n"
)

# Clean text with no slop words
_CLEAN_TEXT = (
    "The system starts quickly. Tests run cleanly. Code is clear. "
    "The build passes every time. Performance is fine."
)


def _run_humanize(args: list, text: str = None, tmpdir: str = None) -> subprocess.CompletedProcess:
    """Run humanize.py with given args. If text is given, write to temp file and prepend path."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    cmd = [sys.executable, str(SCRIPTS_DIR / "humanize.py")]

    if text is not None:
        path = os.path.join(tmpdir, "input.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        cmd.append(path)

    cmd.extend(args)

    return subprocess.run(cmd, capture_output=True, text=True, env=env)


# ---------------------------------------------------------------------------
# AC4: --mode scan
# ---------------------------------------------------------------------------

class TestModeScan(unittest.TestCase):
    """AC4: --mode scan reports findings only, exits 0 regardless of findings."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_scan_exits_0_clean_text(self):
        """AC4: scan mode exits 0 for clean text."""
        proc = _run_humanize(
            ["--mode", "scan", "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode,
                         f"Scan mode must exit 0. stderr: {proc.stderr}")

    def test_scan_exits_0_with_slop(self):
        """AC4: scan mode exits 0 even when text has many slop findings."""
        proc = _run_humanize(
            ["--mode", "scan", "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_EN_SLOP_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode,
                         "Scan mode must always exit 0 (reports only, no gate)")

    def test_scan_json_output_has_language_and_findings(self):
        """AC4: scan mode JSON output has language + findings fields."""
        proc = _run_humanize(
            ["--mode", "scan", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_EN_SLOP_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertIn("language", data)
        self.assertIn("findings", data)

    def test_scan_json_findings_non_empty_for_slop_text(self):
        """AC4: scan JSON has findings for text with known slop words."""
        proc = _run_humanize(
            ["--mode", "scan", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_EN_SLOP_TEXT,
            tmpdir=self._tmpdir.name,
        )
        data = json.loads(proc.stdout)
        self.assertGreater(len(data["findings"]), 0,
                           "Expected findings for slop text in scan mode")

    def test_scan_text_format_exits_0(self):
        """AC4: scan mode with --format text exits 0 and produces output."""
        proc = _run_humanize(
            ["--mode", "scan", "--format", "text",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_EN_SLOP_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertGreater(len(proc.stdout.strip()), 0,
                           "Text format should produce non-empty output")

    def test_scan_de_lang_passthrough(self):
        """AC4: --lang de finds DE slop words in scan mode."""
        proc = _run_humanize(
            ["--mode", "scan", "--format", "json",
             "--lang", "de", "--lexicon-dir", str(SKILL_DIR)],
            text=_DE_SLOP_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertEqual("de", data["language"])
        self.assertGreater(len(data["findings"]), 0)


# ---------------------------------------------------------------------------
# AC4: --mode score
# ---------------------------------------------------------------------------

class TestModeScore(unittest.TestCase):
    """AC4: --mode score delivers the gate; exit 0 = pass, exit 1 = needs-revision."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_score_clean_text_exits_0(self):
        """AC4: score mode exits 0 (pass) for clean text."""
        proc = _run_humanize(
            ["--mode", "score", "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode,
                         f"Clean text should pass (exit 0). stderr: {proc.stderr}")

    def test_score_slop_text_exits_1(self):
        """AC4: score mode exits 1 (needs-revision) for heavy slop text."""
        # Repeat slop pattern to ensure it fails
        heavy = _EN_SLOP_TEXT * 5
        proc = _run_humanize(
            ["--mode", "score", "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=heavy,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(1, proc.returncode,
                         f"Heavy slop should need revision (exit 1). "
                         f"stdout: {proc.stdout[:200]}")

    def test_score_json_output_has_required_keys(self):
        """AC4: score mode JSON output has dimensions, overall, verdict."""
        proc = _run_humanize(
            ["--mode", "score", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertIn("dimensions", data)
        self.assertIn("overall", data)
        self.assertIn("verdict", data)

    def test_score_json_includes_findings_summary(self):
        """AC4: score mode JSON also includes language + findings from scan."""
        proc = _run_humanize(
            ["--mode", "score", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_EN_SLOP_TEXT,
            tmpdir=self._tmpdir.name,
        )
        data = json.loads(proc.stdout)
        self.assertIn("language", data)
        self.assertIn("findings", data)

    def test_score_custom_threshold_changes_verdict(self):
        """AC4: --threshold 1 makes clean text always pass."""
        proc = _run_humanize(
            ["--mode", "score", "--threshold", "1",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode)

    def test_score_high_threshold_fails_clean(self):
        """AC4: --threshold 50 makes even clean text need revision."""
        proc = _run_humanize(
            ["--mode", "score", "--threshold", "50",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(1, proc.returncode,
                         "Threshold 50 should make even clean text fail (exit 1)")

    def test_score_text_format_works(self):
        """AC4: score mode with --format text produces non-empty output."""
        proc = _run_humanize(
            ["--mode", "score", "--format", "text",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        self.assertGreater(len(proc.stdout.strip()), 0)


# ---------------------------------------------------------------------------
# AC4: --format json and text
# ---------------------------------------------------------------------------

class TestFormatFlag(unittest.TestCase):
    """AC4: --format json|text both work for both modes."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_json_output_parseable_scan(self):
        """AC4: --format json emits parseable JSON in scan mode."""
        proc = _run_humanize(
            ["--mode", "scan", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        data = json.loads(proc.stdout)
        self.assertIsInstance(data, dict)

    def test_json_output_parseable_score(self):
        """AC4: --format json emits parseable JSON in score mode."""
        proc = _run_humanize(
            ["--mode", "score", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        data = json.loads(proc.stdout)
        self.assertIsInstance(data, dict)

    def test_text_format_not_json_scan(self):
        """AC4: --format text in scan mode emits human-readable (not raw JSON object)."""
        proc = _run_humanize(
            ["--mode", "scan", "--format", "text",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_EN_SLOP_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(0, proc.returncode, proc.stderr)
        # Should not start with '{' (that would be JSON object mode)
        self.assertFalse(proc.stdout.strip().startswith("{"),
                         "text format must not emit raw JSON object")

    def test_text_format_not_json_score(self):
        """AC4: --format text in score mode emits human-readable output."""
        proc = _run_humanize(
            ["--mode", "score", "--format", "text",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertFalse(proc.stdout.strip().startswith("{"),
                         "text format must not emit raw JSON object")


# ---------------------------------------------------------------------------
# AC5: slop_scanner and slop_scorer remain individually callable
# ---------------------------------------------------------------------------

class TestStandaloneCallable(unittest.TestCase):
    """AC5: both slop_scanner.py and slop_scorer.py are individually CLI-callable."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_slop_scanner_callable_standalone(self):
        """AC5: slop_scanner.py --lang en runs standalone and exits 0."""
        path = os.path.join(self._tmpdir.name, "test.md")
        with open(path, "w", encoding="utf-8") as f:
            f.write("Hello world.\n")
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "slop_scanner.py"),
             path, "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(0, proc.returncode,
                         f"slop_scanner.py standalone failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertIn("language", data)
        self.assertIn("findings", data)

    def test_slop_scorer_callable_standalone(self):
        """AC5: slop_scorer.py runs standalone and exits 0 for clean text."""
        txt_path = os.path.join(self._tmpdir.name, "text.txt")
        findings_path = os.path.join(self._tmpdir.name, "findings.json")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write("The system works well.")
        with open(findings_path, "w", encoding="utf-8") as f:
            json.dump([], f)
        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        proc = subprocess.run(
            [sys.executable, str(SCRIPTS_DIR / "slop_scorer.py"),
             txt_path, findings_path],
            capture_output=True, text=True, env=env,
        )
        self.assertEqual(0, proc.returncode,
                         f"slop_scorer.py standalone failed: {proc.stderr}")
        data = json.loads(proc.stdout)
        self.assertIn("verdict", data)


# ---------------------------------------------------------------------------
# AC6: determinism for humanize.py
# ---------------------------------------------------------------------------

class TestHumanizeDeterminism(unittest.TestCase):
    """AC6: humanize.py produces byte-identical output on repeated calls."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def test_scan_mode_deterministic(self):
        """AC6: two scan-mode runs produce identical stdout."""
        r1 = _run_humanize(
            ["--mode", "scan", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_EN_SLOP_TEXT,
            tmpdir=self._tmpdir.name,
        )
        r2 = _run_humanize(
            ["--mode", "scan", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_EN_SLOP_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(r1.stdout, r2.stdout,
                         "Two scan-mode runs must produce identical output")

    def test_score_mode_deterministic(self):
        """AC6: two score-mode runs produce identical stdout."""
        r1 = _run_humanize(
            ["--mode", "score", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        r2 = _run_humanize(
            ["--mode", "score", "--format", "json",
             "--lang", "en", "--lexicon-dir", str(SKILL_DIR)],
            text=_CLEAN_TEXT,
            tmpdir=self._tmpdir.name,
        )
        self.assertEqual(r1.stdout, r2.stdout)

    def test_no_third_party_imports_humanize(self):
        """AC6: humanize.py imports only stdlib modules."""
        import ast
        humanize_src = SCRIPTS_DIR / "humanize.py"
        with open(humanize_src, encoding="utf-8") as f:
            tree = ast.parse(f.read())
        third_party = {
            "requests", "httpx", "urllib3", "aiohttp", "numpy",
            "pandas", "pytest", "flask", "django",
        }
        for node in ast.walk(tree):
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                names = (
                    [a.name for a in node.names]
                    if isinstance(node, ast.Import)
                    else [node.module or ""]
                )
                for name in names:
                    top = (name or "").split(".")[0]
                    self.assertNotIn(
                        top, third_party,
                        f"Third-party import '{top}' found in humanize.py",
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
