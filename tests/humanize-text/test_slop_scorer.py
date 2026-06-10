#!/usr/bin/env python3
"""Tests for humanize-text/scripts/slop_scorer.py — slice 05.

Observable-behaviour only: tests drive the public API and CLI.
No internal helpers tested directly.

Acceptance criteria covered:
  AC1 — five dimensions 1-10, overall, pass/needs-revision vs threshold
  AC2 — score monotonicity + burstiness distinguishes sentence-length variance
  AC3 — tier-gating: tier-1 always, tier-2 cluster only, tier-3 density hint
  AC5 — slop_scorer standalone CLI
  AC6 — determinism + golden fixtures; no LLM/network

Run from repo root:
    python3 tests/humanize-text/test_slop_scorer.py
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

sys.path.insert(0, str(SCRIPTS_DIR))

import slop_scorer  # noqa: E402

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_finding(tier: int, line_number: int = 1) -> dict:
    """Return a minimal canonical finding for scoring tests."""
    return {
        "file_path": "test.md",
        "line_number": line_number,
        "match": "leverage",
        "pattern_id": f"en_test_{tier}",
        "type": "word",
        "tier": tier,
        "suggested_replacement": "",
        "rationale": "test",
    }


# ---------------------------------------------------------------------------
# AC1: score shape — five dimensions, overall, pass/needs-revision
# ---------------------------------------------------------------------------

class TestScoreShape(unittest.TestCase):
    """AC1: score() returns correct shape with all required fields."""

    def test_returns_dict_with_all_top_level_keys(self):
        """AC1: result has dimensions, overall, verdict."""
        result = slop_scorer.score("Hello world.", [])
        self.assertIn("dimensions", result)
        self.assertIn("overall", result)
        self.assertIn("verdict", result)

    def test_dimensions_has_five_keys(self):
        """AC1: dimensions dict has exactly the five canonical keys."""
        result = slop_scorer.score("Hello world.", [])
        dims = result["dimensions"]
        expected = {"directness", "rhythm", "trust", "authenticity", "density"}
        self.assertEqual(expected, set(dims.keys()),
                         f"Wrong dimension keys: {set(dims.keys())}")

    def test_dimensions_are_floats_1_to_10(self):
        """AC1: each dimension is a number in [1, 10]."""
        result = slop_scorer.score("Hello world.", [])
        for name, val in result["dimensions"].items():
            self.assertIsInstance(val, (int, float),
                                  f"Dimension '{name}' is not numeric: {val!r}")
            self.assertGreaterEqual(val, 1.0,
                                    f"Dimension '{name}' < 1: {val}")
            self.assertLessEqual(val, 10.0,
                                 f"Dimension '{name}' > 10: {val}")

    def test_overall_is_float_in_range(self):
        """AC1: overall score is numeric in [1, 50]."""
        result = slop_scorer.score("Hello world.", [])
        overall = result["overall"]
        self.assertIsInstance(overall, (int, float))
        self.assertGreaterEqual(overall, 1.0)
        self.assertLessEqual(overall, 50.0)

    def test_verdict_is_string_enum(self):
        """AC1: verdict is 'pass' or 'needs-revision'."""
        result = slop_scorer.score("Hello world.", [])
        self.assertIn(result["verdict"], {"pass", "needs-revision"})

    def test_clean_text_passes(self):
        """AC1: clean text with no findings should pass (high score)."""
        text = "The system starts quickly. Tests run cleanly. Code is clear."
        result = slop_scorer.score(text, [])
        self.assertEqual("pass", result["verdict"],
                         f"Clean text should pass; got overall={result['overall']}")

    def test_heavy_slop_fails(self):
        """AC1: text loaded with tier-1 findings should fail (needs-revision)."""
        text = " ".join(["leverage"] * 20 + ["delve", "tapestry", "groundbreaking"])
        findings = [_make_finding(1, i + 1) for i in range(15)]
        result = slop_scorer.score(text, findings)
        self.assertEqual("needs-revision", result["verdict"],
                         f"Heavy slop text should need revision; got overall={result['overall']}")

    def test_custom_threshold_low(self):
        """AC1: threshold=1 (very low) → always pass."""
        text = "leverage tapestry delve"
        findings = [_make_finding(1), _make_finding(1), _make_finding(1)]
        result = slop_scorer.score(text, findings, threshold=1)
        self.assertEqual("pass", result["verdict"])

    def test_custom_threshold_high(self):
        """AC1: threshold=50 (max) → always needs-revision unless perfect."""
        text = "Hello world."
        result = slop_scorer.score(text, [], threshold=50)
        self.assertEqual("needs-revision", result["verdict"])


# ---------------------------------------------------------------------------
# AC2: monotonicity — more findings → lower score
# ---------------------------------------------------------------------------

class TestScoreMonotonicity(unittest.TestCase):
    """AC2: adding more tier-1 findings lowers the score."""

    _BASE_TEXT = (
        "The system starts quickly. Tests run cleanly. "
        "Code is clear. The build passes consistently. "
        "Performance is acceptable across all benchmarks."
    )

    def test_zero_findings_higher_than_few(self):
        """AC2: no findings → higher overall than with some findings."""
        r0 = slop_scorer.score(self._BASE_TEXT, [])
        r_few = slop_scorer.score(self._BASE_TEXT, [_make_finding(1)] * 3)
        self.assertGreater(r0["overall"], r_few["overall"],
                           "0 findings must score higher than 3 findings")

    def test_few_findings_higher_than_many(self):
        """AC2: few findings → higher overall than many findings."""
        r_few = slop_scorer.score(self._BASE_TEXT, [_make_finding(1)] * 3)
        r_many = slop_scorer.score(self._BASE_TEXT, [_make_finding(1)] * 10)
        self.assertGreater(r_few["overall"], r_many["overall"],
                           "3 findings must score higher than 10 findings")

    def test_tier2_lighter_than_tier1(self):
        """AC2: tier-2 findings penalise less than equal-count tier-1 findings."""
        text = self._BASE_TEXT
        r_t1 = slop_scorer.score(text, [_make_finding(1)] * 5)
        r_t2 = slop_scorer.score(text, [_make_finding(2)] * 5)
        self.assertGreaterEqual(r_t2["overall"], r_t1["overall"],
                                "Tier-2 findings must not penalise more than tier-1")


# ---------------------------------------------------------------------------
# AC2: burstiness — sentence-length variance affects Rhythm dimension
# ---------------------------------------------------------------------------

class TestBurstiness(unittest.TestCase):
    """AC2: burstiness of sentence lengths affects the Rhythm dimension."""

    def test_uniform_sentences_lower_rhythm_than_varied(self):
        """AC2: uniform sentence lengths score lower Rhythm than varied lengths."""
        # All sentences roughly same length
        uniform = (
            "The cat sat. The dog ran. The bird flew. The fish swam. "
            "The frog jumped. The ant walked. The bee buzzed."
        )
        # Varied: very short + very long sentences interleaved
        varied = (
            "Stop. "
            "This is a considerably longer sentence that provides real context and nuance. "
            "Go. "
            "Another long sentence appears here to contrast sharply with the one-word entries."
        )
        r_uniform = slop_scorer.score(uniform, [])
        r_varied = slop_scorer.score(varied, [])
        self.assertGreater(
            r_varied["dimensions"]["rhythm"],
            r_uniform["dimensions"]["rhythm"],
            f"Varied text should have higher Rhythm score. "
            f"uniform={r_uniform['dimensions']['rhythm']}, "
            f"varied={r_varied['dimensions']['rhythm']}",
        )

    def test_single_sentence_rhythm_is_bounded(self):
        """AC2: single sentence (zero variance) returns Rhythm in [1, 10]."""
        result = slop_scorer.score("Just one sentence here.", [])
        r = result["dimensions"]["rhythm"]
        self.assertGreaterEqual(r, 1.0)
        self.assertLessEqual(r, 10.0)


# ---------------------------------------------------------------------------
# AC3: tier-gating
# ---------------------------------------------------------------------------

class TestTierGating(unittest.TestCase):
    """AC3: tier-1 always surfaced, tier-2 only in clusters, tier-3 density hint only."""

    def test_tier1_findings_always_in_surfaced(self):
        """AC3: tier-1 findings always appear in surfaced_findings."""
        findings = [_make_finding(1, i + 1) for i in range(3)]
        result = slop_scorer.apply_tier_gating(findings, word_count=100)
        surfaced_ids = {f["pattern_id"] for f in result["surfaced_findings"]}
        for f in findings:
            self.assertIn(f["pattern_id"], surfaced_ids,
                          f"Tier-1 finding {f['pattern_id']} not surfaced")

    def test_tier2_isolated_not_surfaced(self):
        """AC3: isolated tier-2 finding (below cluster threshold) not in surfaced."""
        # Just one tier-2 finding — below any reasonable cluster definition
        findings = [_make_finding(2, 1)]
        result = slop_scorer.apply_tier_gating(findings, word_count=200)
        surfaced_ids = {f["pattern_id"] for f in result["surfaced_findings"]}
        self.assertNotIn(findings[0]["pattern_id"], surfaced_ids,
                         "Isolated tier-2 finding must not be surfaced")

    def test_tier2_clustered_surfaced(self):
        """AC3: tier-2 findings in a cluster (≥3 within 10 lines) ARE surfaced."""
        # 3 tier-2 findings on consecutive lines → cluster
        findings = [_make_finding(2, i + 1) for i in range(3)]
        result = slop_scorer.apply_tier_gating(findings, word_count=200)
        surfaced_ids = {f["pattern_id"] for f in result["surfaced_findings"]}
        # All three should appear (they're in a cluster)
        for f in findings:
            self.assertIn(f["pattern_id"], surfaced_ids,
                          f"Tier-2 cluster finding {f['pattern_id']} not surfaced")

    def test_tier3_never_in_surfaced(self):
        """AC3: tier-3 findings never appear in surfaced_findings."""
        findings = [_make_finding(3, i + 1) for i in range(5)]
        result = slop_scorer.apply_tier_gating(findings, word_count=200)
        surfaced = result["surfaced_findings"]
        tier3_surfaced = [f for f in surfaced if f["tier"] == 3]
        self.assertEqual([], tier3_surfaced,
                         "Tier-3 findings must never appear in surfaced_findings")

    def test_tier3_density_hint_present_when_dense(self):
        """AC3: tier-3 density hint appears when density exceeds threshold."""
        # Enough tier-3 findings relative to word count
        findings = [_make_finding(3, i + 1) for i in range(6)]
        result = slop_scorer.apply_tier_gating(findings, word_count=100)
        self.assertTrue(result["tier3_density_hint"],
                        "tier3_density_hint should be True when density ≥ threshold")

    def test_tier3_density_hint_absent_when_sparse(self):
        """AC3: tier-3 density hint is False when tier-3 density is low."""
        findings = [_make_finding(3, 1)]  # just one finding in 1000 words
        result = slop_scorer.apply_tier_gating(findings, word_count=1000)
        self.assertFalse(result["tier3_density_hint"],
                         "tier3_density_hint should be False when density is low")

    def test_gating_result_has_required_keys(self):
        """AC3: apply_tier_gating returns dict with expected keys."""
        result = slop_scorer.apply_tier_gating([], word_count=100)
        self.assertIn("surfaced_findings", result)
        self.assertIn("tier3_density_hint", result)

    def test_mixed_tiers_gated_correctly(self):
        """AC3: mixed-tier fixture — t1 always, t2 cluster, t3 never surfaced."""
        findings = (
            [_make_finding(1, i + 1) for i in range(2)]      # 2x tier-1: always surfaced
            + [_make_finding(2, i + 10) for i in range(3)]   # 3x tier-2, lines 10-12: cluster
            + [_make_finding(3, i + 20) for i in range(10)]  # 10x tier-3: never surfaced
        )
        result = slop_scorer.apply_tier_gating(findings, word_count=500)
        surfaced = result["surfaced_findings"]

        # All tier-1 present
        t1_surfaced = [f for f in surfaced if f["tier"] == 1]
        self.assertEqual(2, len(t1_surfaced))

        # Tier-2 cluster surfaced (3 within 3 lines)
        t2_surfaced = [f for f in surfaced if f["tier"] == 2]
        self.assertEqual(3, len(t2_surfaced))

        # No tier-3
        t3_surfaced = [f for f in surfaced if f["tier"] == 3]
        self.assertEqual(0, len(t3_surfaced))


# ---------------------------------------------------------------------------
# AC5: standalone CLI for slop_scorer
# ---------------------------------------------------------------------------

class TestScorerCLI(unittest.TestCase):
    """AC5: slop_scorer.py is independently CLI-callable."""

    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()

    def tearDown(self):
        self._tmpdir.cleanup()

    def _run_scorer_cli(self, text: str, findings: list, extra_args: list = None) -> dict:
        # Write text to temp file
        txt_path = os.path.join(self._tmpdir.name, "input.txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(text)
        # Write findings to temp JSON file
        findings_path = os.path.join(self._tmpdir.name, "findings.json")
        with open(findings_path, "w", encoding="utf-8") as f:
            json.dump(findings, f)

        cmd = [
            sys.executable,
            str(SCRIPTS_DIR / "slop_scorer.py"),
            txt_path,
            findings_path,
        ]
        if extra_args:
            cmd.extend(extra_args)

        env = os.environ.copy()
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        result = subprocess.run(cmd, capture_output=True, text=True, env=env)
        return result

    def test_cli_exit_0_pass(self):
        """AC5: CLI exits 0 when text passes the gate."""
        proc = self._run_scorer_cli(
            "The system starts quickly. Tests run cleanly. Code is clear.",
            [],
        )
        self.assertEqual(0, proc.returncode,
                         f"Expected exit 0 (pass). stderr: {proc.stderr}")

    def test_cli_exit_1_needs_revision(self):
        """AC5: CLI exits 1 when text needs revision."""
        findings = [_make_finding(1, i + 1) for i in range(15)]
        proc = self._run_scorer_cli(
            " ".join(["leverage"] * 50),
            findings,
        )
        self.assertEqual(1, proc.returncode,
                         f"Expected exit 1 (needs-revision). stderr: {proc.stderr}")

    def test_cli_output_is_valid_json(self):
        """AC5: CLI stdout is valid JSON."""
        proc = self._run_scorer_cli("Hello world.", [])
        self.assertEqual(0, proc.returncode, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertIsInstance(data, dict)

    def test_cli_output_has_required_keys(self):
        """AC5: CLI JSON output contains dimensions, overall, verdict."""
        proc = self._run_scorer_cli("Hello world.", [])
        self.assertEqual(0, proc.returncode, proc.stderr)
        data = json.loads(proc.stdout)
        self.assertIn("dimensions", data)
        self.assertIn("overall", data)
        self.assertIn("verdict", data)

    def test_cli_custom_threshold(self):
        """AC5: --threshold flag changes the verdict."""
        proc = self._run_scorer_cli(
            "Hello world.",
            [],
            extra_args=["--threshold", "50"],
        )
        # Threshold 50 means even clean text needs revision
        data = json.loads(proc.stdout)
        self.assertEqual("needs-revision", data["verdict"])

    def test_cli_no_third_party_imports(self):
        """AC6: slop_scorer.py imports only stdlib modules."""
        import ast
        scorer_src = SCRIPTS_DIR / "slop_scorer.py"
        with open(scorer_src, encoding="utf-8") as f:
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
                        f"Third-party import '{top}' found in slop_scorer.py",
                    )


# ---------------------------------------------------------------------------
# AC6: determinism + golden fixtures
# ---------------------------------------------------------------------------

class TestDeterminism(unittest.TestCase):
    """AC6: identical inputs produce byte-identical scores."""

    _GOLDEN_TEXT = (
        "We need to leverage our existing infrastructure to foster collaboration. "
        "It is worth noting that this groundbreaking approach will delve into the "
        "rich tapestry of modern solutions. The landscape is robust and crucial."
    )

    _GOLDEN_FINDINGS = [
        {
            "file_path": "golden.md",
            "line_number": 1,
            "match": "leverage",
            "pattern_id": "en_leverage",
            "type": "word",
            "tier": 1,
            "suggested_replacement": "use",
            "rationale": "overused business jargon",
        },
        {
            "file_path": "golden.md",
            "line_number": 1,
            "match": "foster",
            "pattern_id": "en_foster",
            "type": "word",
            "tier": 1,
            "suggested_replacement": "support",
            "rationale": "corporate filler",
        },
        {
            "file_path": "golden.md",
            "line_number": 1,
            "match": "groundbreaking",
            "pattern_id": "en_groundbreaking",
            "type": "word",
            "tier": 1,
            "suggested_replacement": "new",
            "rationale": "empty superlative",
        },
    ]

    def test_two_runs_byte_identical(self):
        """AC6: two score() calls with same inputs produce identical JSON."""
        r1 = slop_scorer.score(self._GOLDEN_TEXT, self._GOLDEN_FINDINGS)
        r2 = slop_scorer.score(self._GOLDEN_TEXT, self._GOLDEN_FINDINGS)
        j1 = json.dumps(r1, ensure_ascii=False, sort_keys=True)
        j2 = json.dumps(r2, ensure_ascii=False, sort_keys=True)
        self.assertEqual(j1, j2)

    def test_golden_dimensions_stable(self):
        """AC6: golden fixture produces stable dimension values."""
        r = slop_scorer.score(self._GOLDEN_TEXT, self._GOLDEN_FINDINGS)
        # Directness must be < 10 because there are findings
        self.assertLess(r["dimensions"]["directness"], 10.0)
        # Density must be < 10 because there are findings per 100 words
        self.assertLess(r["dimensions"]["density"], 10.0)

    def test_empty_text_produces_valid_score(self):
        """AC6: empty text does not crash; returns bounded dimensions."""
        r = slop_scorer.score("", [])
        for name, val in r["dimensions"].items():
            self.assertGreaterEqual(val, 1.0,
                                    f"Empty text: dimension '{name}' < 1")
            self.assertLessEqual(val, 10.0,
                                 f"Empty text: dimension '{name}' > 10")

    def test_tier_gating_determinism(self):
        """AC6: apply_tier_gating is deterministic for same input."""
        findings = [_make_finding(t, i) for t in [1, 2, 3] for i in range(3)]
        r1 = slop_scorer.apply_tier_gating(findings, word_count=300)
        r2 = slop_scorer.apply_tier_gating(findings, word_count=300)
        j1 = json.dumps(r1, ensure_ascii=False, sort_keys=True)
        j2 = json.dumps(r2, ensure_ascii=False, sort_keys=True)
        self.assertEqual(j1, j2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
