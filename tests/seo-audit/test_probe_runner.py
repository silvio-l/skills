#!/usr/bin/env python3
"""Tests for the probe.run orchestrator.

Covers:
* AC3: adapters run concurrently — verified by tracking thread ids.
* AC4: `--quick` skips lighthouse + pa11y.
* One adapter failing does not nuke the rest.
"""

import pathlib
import sys
import threading
import time
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from probes import probe as PROBE  # noqa: E402


def _make_adapter(name, sev="med", delay=0.05):
    def adapter(url):
        time.sleep(delay)
        return [{
            "category":    name,
            "severity":    sev,
            "user_impact": 2,
            "fix_effort":  2,
            "file_path":   url,
            "line_number": 0,
            "match":       f"{name}:test",
            "rationale":   f"{name} adapter result",
            "suggested_replacement": "",
        }]
    return adapter


class ProbeRunner(unittest.TestCase):
    def test_run_invokes_every_registered_adapter(self):
        registry = {
            "alpha": _make_adapter("alpha"),
            "beta":  _make_adapter("beta"),
        }
        findings = PROBE.run(["https://x.example/"], adapters=registry)
        cats = sorted(f["category"] for f in findings)
        self.assertEqual(cats, ["alpha", "beta"])

    def test_runs_adapters_concurrently(self):
        thread_ids = set()
        lock = threading.Lock()

        def slow_adapter(name):
            def fn(url):
                with lock:
                    thread_ids.add(threading.get_ident())
                time.sleep(0.2)
                return []
            return fn

        registry = {f"a{i}": slow_adapter(f"a{i}") for i in range(4)}
        t0 = time.monotonic()
        PROBE.run(["https://x.example/"], adapters=registry)
        elapsed = time.monotonic() - t0
        # Four 200 ms adapters run serial would be >0.8 s; in parallel
        # they fit comfortably under 0.5 s.
        self.assertLess(elapsed, 0.5,
                        f"adapters appear serial — took {elapsed:.2f}s")
        self.assertGreater(len(thread_ids), 1,
                           "adapters must run on more than one thread")

    def test_quick_skips_heavy_adapters(self):
        called = []

        def make(name):
            def fn(url):
                called.append(name)
                return []
            return fn

        registry = {
            "lighthouse": make("lighthouse"),
            "pa11y":      make("pa11y"),
            "w3c":        make("w3c"),
            "observatory": make("observatory"),
        }
        PROBE.run(["https://x.example/"], adapters=registry, quick=True)
        self.assertNotIn("lighthouse", called)
        self.assertNotIn("pa11y", called)
        self.assertIn("w3c", called)
        self.assertIn("observatory", called)

    def test_adapter_failure_does_not_nuke_run(self):
        def boom(url):
            raise RuntimeError("network melted")

        registry = {
            "boom":  boom,
            "alpha": _make_adapter("alpha"),
        }
        findings = PROBE.run(["https://x.example/"], adapters=registry)
        cats = sorted(f["category"] for f in findings)
        # The failure is swallowed; alpha findings still appear.
        self.assertEqual(cats, ["alpha"])

    def test_empty_url_list_yields_no_findings(self):
        registry = {"alpha": _make_adapter("alpha")}
        self.assertEqual(PROBE.run([], adapters=registry), [])

    def test_default_registry_contains_seven_adapters(self):
        names = set(PROBE.DEFAULT_ADAPTERS.keys())
        self.assertEqual(names, {
            "lighthouse", "pa11y", "w3c", "schema",
            "observatory", "gsc", "pagespeed",
        })


if __name__ == "__main__":
    unittest.main(verbosity=2)
