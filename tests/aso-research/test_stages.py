#!/usr/bin/env python3
"""Tests for the stage-level idempotency / crash-resume / --fresh /
timing logic (slice 06).

Run from the repo root:
    python3 tests/aso-research/test_stages.py

Covers the offline-testable pure logic only: with injectable stage
callables + a temp artefact store + an injected clock, a stage whose
checkpoint is fresh is SKIPPED (callable not re-invoked, artefact
byte-identical); a stale/missing checkpoint runs; ``--fresh`` bypasses;
a simulated crash resumes at the failed stage; per-stage timing is
recorded. The live collectors are not involved.
"""

import json
import os
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import cache as CACHE  # noqa: E402
import serialize  # noqa: E402
import stages  # noqa: E402
import aso_research  # noqa: E402


# ===========================================================================
# Stage idempotency (AC1)
# ===========================================================================

class StageIdempotencyTests(unittest.TestCase):
    def test_first_run_executes_and_writes_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            runner = stages.StageRunner(d, fresh=False, now=1000.0)

            def fn():
                calls.append("ran")
                return {"competitors": [{"id": "1"}], "n": 1}

            result, status = runner.stage("collect", fn, ttl=CACHE.BROWSER_TTL)
            self.assertEqual(status, "ran")
            self.assertEqual(result, {"competitors": [{"id": "1"}], "n": 1})
            self.assertEqual(calls, ["ran"])
            self.assertTrue(
                os.path.isfile(os.path.join(d, "stages", "collect.json"))
            )

    def test_fresh_checkpoint_is_skipped_and_callable_not_reinvoked(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            stages.StageRunner(d, fresh=False, now=1000.0).stage(
                "collect", lambda: (calls.append("ran") or {"v": 1}),
                ttl=CACHE.BROWSER_TTL,
            )
            # Re-run within TTL: new runner, same dir, fresh checkpoint.
            runner2 = stages.StageRunner(d, fresh=False, now=1000.0 + 60)
            result, status = runner2.stage(
                "collect", lambda: (calls.append("again") or {"v": 99}),
                ttl=CACHE.BROWSER_TTL,
            )
            self.assertEqual(status, "skipped")
            self.assertEqual(calls, ["ran"])  # not re-invoked
            self.assertEqual(result, {"v": 1})  # artefact reused as-is

    def test_skipped_checkpoint_leaves_artefact_byte_identical(self):
        # AC1: a warm re-run leaves the finished artefact byte-identical.
        with tempfile.TemporaryDirectory() as d:
            runner = stages.StageRunner(d, fresh=False, now=1000.0)
            runner.stage(
                "collect", lambda: {"a": [3, 1, 2]}, ttl=CACHE.BROWSER_TTL
            )
            ckpt = os.path.join(d, "stages", "collect.json")
            with open(ckpt, encoding="utf-8") as fh:
                before = fh.read()
            # Warm re-run — the callable would return different data, but
            # the skip must NOT touch the checkpoint.
            stages.StageRunner(d, fresh=False, now=1100.0).stage(
                "collect", lambda: {"a": [9, 9, 9]}, ttl=CACHE.BROWSER_TTL
            )
            with open(ckpt, encoding="utf-8") as fh:
                after = fh.read()
            self.assertEqual(before, after)

    def test_missing_checkpoint_runs(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            stages.StageRunner(d, fresh=False, now=1000.0).stage(
                "x", lambda: (calls.append(1) or {"v": 1}), ttl=CACHE.BROWSER_TTL
            )
            self.assertEqual(calls, [1])

    def test_stale_checkpoint_runs_again(self):
        with tempfile.TemporaryDirectory() as d:
            stages.StageRunner(d, fresh=False, now=1000.0).stage(
                "x", lambda: {"v": 1}, ttl=100
            )
            runner2 = stages.StageRunner(d, fresh=False, now=2000.0)  # past TTL
            calls = []
            result, status = runner2.stage(
                "x", lambda: (calls.append(1) or {"v": 2}), ttl=100
            )
            self.assertEqual(status, "ran")
            self.assertEqual(result, {"v": 2})


# ===========================================================================
# --fresh bypass (AC3)
# ===========================================================================

class FreshBypassTests(unittest.TestCase):
    def test_fresh_flag_forces_rerun_even_with_fresh_checkpoint(self):
        with tempfile.TemporaryDirectory() as d:
            calls = []
            stages.StageRunner(d, fresh=False, now=1000.0).stage(
                "x", lambda: (calls.append(1) or {"v": 1}), ttl=CACHE.BROWSER_TTL
            )
            # --fresh bypasses the freshness check.
            runner2 = stages.StageRunner(d, fresh=True, now=1000.0)
            result, status = runner2.stage(
                "x", lambda: (calls.append(2) or {"v": 2}), ttl=CACHE.BROWSER_TTL
            )
            self.assertEqual(status, "ran")
            self.assertEqual(result, {"v": 2})
            self.assertEqual(calls, [1, 2])

    def test_skippable_false_always_runs_and_writes_no_checkpoint(self):
        # The terminal report stage is never skipped (timestamp differs by
        # design) but still records timing.
        with tempfile.TemporaryDirectory() as d:
            calls = []
            runner = stages.StageRunner(d, fresh=False, now=1000.0)
            runner.stage(
                "report", lambda: (calls.append(1) or {"t": "now"}),
                ttl=CACHE.BROWSER_TTL, skippable=False,
            )
            runner.stage(
                "report", lambda: (calls.append(2) or {"t": "later"}),
                ttl=CACHE.BROWSER_TTL, skippable=False,
            )
            self.assertEqual(calls, [1, 2])
            self.assertFalse(
                os.path.isfile(os.path.join(d, "stages", "report.json"))
            )


# ===========================================================================
# Crash-resume (AC2)
# ===========================================================================

class CrashResumeTests(unittest.TestCase):
    def test_resume_skips_completed_stages_runs_the_failed_one(self):
        with tempfile.TemporaryDirectory() as d:
            log = []
            # First run: stages 1 and 2 complete, then "crash" before 3.
            r1 = stages.StageRunner(d, fresh=False, now=1000.0)
            r1.stage("one", lambda: (log.append("one") or {"i": 1}), ttl=CACHE.HTTP_TTL)
            r1.stage("two", lambda: (log.append("two") or {"i": 2}), ttl=CACHE.HTTP_TTL)
            self.assertEqual(log, ["one", "two"])

            # Resume run: one + two are skipped (fresh checkpoints), three runs.
            r2 = stages.StageRunner(d, fresh=False, now=1000.0)
            _, s1 = r2.stage(
                "one", lambda: (log.append("one!") or {"i": 9}), ttl=CACHE.HTTP_TTL
            )
            _, s2 = r2.stage(
                "two", lambda: (log.append("two!") or {"i": 9}), ttl=CACHE.HTTP_TTL
            )
            _, s3 = r2.stage(
                "three", lambda: (log.append("three") or {"i": 3}), ttl=CACHE.HTTP_TTL
            )
            self.assertEqual(s1, "skipped")
            self.assertEqual(s2, "skipped")
            self.assertEqual(s3, "ran")
            self.assertEqual(log, ["one", "two", "three"])  # 1,2 not re-run


# ===========================================================================
# Per-stage timing instrumentation (AC5 — observable structure)
# ===========================================================================

class TimingTests(unittest.TestCase):
    def test_timing_records_status_and_numeric_elapsed(self):
        with tempfile.TemporaryDirectory() as d:
            runner = stages.StageRunner(d, fresh=False, now=1000.0)
            runner.stage("a", lambda: {"x": 1}, ttl=CACHE.HTTP_TTL)
            runner.stage("b", lambda: {"x": 1}, ttl=CACHE.HTTP_TTL)
            t = runner.timing()
            self.assertEqual(t["a"]["status"], "ran")
            self.assertEqual(t["b"]["status"], "ran")
            self.assertGreaterEqual(t["a"]["elapsed_seconds"], 0.0)
            self.assertIsInstance(t["a"]["elapsed_seconds"], float)

    def test_skipped_stage_records_zero_elapsed(self):
        with tempfile.TemporaryDirectory() as d:
            stages.StageRunner(d, fresh=False, now=1000.0).stage(
                "a", lambda: {"x": 1}, ttl=CACHE.HTTP_TTL
            )
            r2 = stages.StageRunner(d, fresh=False, now=1100.0)
            r2.stage("a", lambda: {"x": 1}, ttl=CACHE.HTTP_TTL)
            t = r2.timing()
            self.assertEqual(t["a"]["status"], "skipped")
            self.assertEqual(t["a"]["elapsed_seconds"], 0.0)


# ===========================================================================
# Run-summary timing instrumentation (AC5 — the ≤30-min target is observable)
# ===========================================================================

class RunSummaryTimingTests(unittest.TestCase):
    def test_run_summary_carries_per_stage_timing(self):
        # The observable check for AC5: run-summary records per-stage
        # status + elapsed so the ≤30-min target can be measured. The
        # actual live wall-clock is NOT asserted here (would be fabricated).
        timing = {
            "collect": {"status": "ran", "elapsed_seconds": 312.4},
            "score": {"status": "ran", "elapsed_seconds": 0.8},
            "llm-inputs": {"status": "ran", "elapsed_seconds": 0.1},
            "report": {"status": "ran", "elapsed_seconds": 0.2},
        }
        summary = aso_research._build_run_summary(
            "20260626-120000-habit-hero",
            [{"id": "1", "platform": "apple"}],
            [{"term": "habit", "platform": "apple", "opportunity": 50}],
            [], {"itunes_search": "ok"}, True, timing,
        )
        self.assertIn("stage_timing", summary)
        self.assertEqual(summary["stage_timing"], timing)
        self.assertEqual(summary["run_id"], "20260626-120000-habit-hero")
        self.assertEqual(summary["platforms"], ["apple", "play"])
        self.assertEqual(summary["competitor_count"], 1)
        self.assertEqual(summary["keyword_count"], 1)
        # the existing machine-readable fields are preserved
        self.assertIn("channels", summary)
        self.assertIn("source_status", summary)


# ===========================================================================
# Reproducibility through the stage mechanism (AC6 / US18)
# ===========================================================================

class ReproducibilityTests(unittest.TestCase):
    def test_warm_rerun_leaves_human_artefact_byte_identical(self):
        # Mimics the dispatcher: the "collect" stage writes competition.json
        # as a side effect; a warm re-run skips it and must not alter it.
        with tempfile.TemporaryDirectory() as d:
            fixed = [{"id": "1", "platform": "apple", "title": "X"}]

            def collect_fn():
                serialize.dump_json(fixed, os.path.join(d, "competition.json"))
                return {"competitors": fixed}

            stages.StageRunner(d, fresh=False, now=1000.0).stage(
                "collect", collect_fn, ttl=CACHE.HTTP_TTL
            )
            comp_path = os.path.join(d, "competition.json")
            with open(comp_path, encoding="utf-8") as fh:
                before = fh.read()

            # Warm re-run with a callable that would write DIFFERENT data —
            # the skip must keep the original byte-identical.
            def collect_fn_changed():
                serialize.dump_json([{"id": "9"}], comp_path)
                return {"competitors": [{"id": "9"}]}

            stages.StageRunner(d, fresh=False, now=1100.0).stage(
                "collect", collect_fn_changed, ttl=CACHE.HTTP_TTL
            )
            with open(comp_path, encoding="utf-8") as fh:
                after = fh.read()
            self.assertEqual(before, after)

    def test_checkpoint_roundtrip_is_stable_json(self):
        with tempfile.TemporaryDirectory() as d:
            payload = {"b": 2, "a": [3, 1, 2], "nested": {"y": 1, "x": 2}}
            stages.StageRunner(d, fresh=False, now=1000.0).stage(
                "s", lambda: payload, ttl=CACHE.HTTP_TTL
            )
            ckpt = os.path.join(d, "stages", "s.json")
            # Checkpoint is the stable, key-sorted serialization.
            with open(ckpt, encoding="utf-8") as fh:
                self.assertEqual(fh.read(), serialize.dumps_json(payload))
            # And a skip loads the exact same structure back.
            r2 = stages.StageRunner(d, fresh=False, now=1100.0)
            result, status = r2.stage(
                "s", lambda: {"different": True}, ttl=CACHE.HTTP_TTL
            )
            self.assertEqual(status, "skipped")
            self.assertEqual(result, payload)


if __name__ == "__main__":
    unittest.main()
