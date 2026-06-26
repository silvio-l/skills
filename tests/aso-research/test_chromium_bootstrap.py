#!/usr/bin/env python3
"""Tests for Chromium bootstrap (P6 — slice 03 quality hardening).

Run from the repo root:
    python3 tests/aso-research/test_chromium_bootstrap.py

Covers ACs:
- AC1: With chromium present, _ensure_chromium() is a no-op (no subprocess)
- AC2: With chromium absent, install attempted exactly once
- AC3: Bootstrap failure degrades never-blocking (reason-bearing unavailable)
- AC4: Observable log lines (probe result, install attempted/skipped)
- AC5: Idempotent: repeated runs do not redo the install
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "aso-research" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))
sys.dont_write_bytecode = True


def _reset_bootstrap():
    """Reset module-level bootstrap state so each test starts clean."""
    import apple_browser
    apple_browser._ensure_chromium_done = False
    apple_browser._ensure_chromium_result = None


class ChromiumPresentNoOpTests(unittest.TestCase):
    """AC1: With the binary already present, _ensure_chromium() is a no-op."""

    def setUp(self):
        _reset_bootstrap()

    def test_probe_returns_true_no_install_attempted(self):
        import apple_browser

        install_calls = []

        def present_probe():
            return True

        def fake_install():
            install_calls.append(1)
            return True

        ok, reason = apple_browser._ensure_chromium(
            probe_fn=present_probe, install_fn=fake_install
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)
        self.assertEqual(install_calls, [])

    def test_log_line_indicates_present_skip(self):
        import apple_browser
        import io

        buf = io.StringIO()

        def present_probe():
            return True

        ok, reason = apple_browser._ensure_chromium(
            probe_fn=present_probe, install_fn=lambda: True, log_file=buf
        )
        self.assertTrue(ok)
        log = buf.getvalue()
        self.assertIn("present", log.lower())


class ChromiumAbsentInstallOnceTests(unittest.TestCase):
    """AC2: With binary absent, install attempted exactly once."""

    def setUp(self):
        _reset_bootstrap()

    def test_probe_returns_false_install_called_once(self):
        import apple_browser

        install_calls = []

        def absent_probe():
            return False

        def fake_install():
            install_calls.append(1)
            return True

        ok, reason = apple_browser._ensure_chromium(
            probe_fn=absent_probe, install_fn=fake_install
        )
        self.assertTrue(ok)
        self.assertIsNone(reason)
        self.assertEqual(install_calls, [1])

    def test_second_call_does_not_redo_install(self):
        import apple_browser

        install_calls = []

        def absent_probe():
            return False

        def fake_install():
            install_calls.append(1)
            return True

        # first call — install runs
        ok1, _ = apple_browser._ensure_chromium(
            probe_fn=absent_probe, install_fn=fake_install
        )
        self.assertTrue(ok1)
        self.assertEqual(len(install_calls), 1)

        # second call — cached, install NOT called again
        ok2, _ = apple_browser._ensure_chromium(
            probe_fn=absent_probe, install_fn=fake_install
        )
        self.assertTrue(ok2)
        self.assertEqual(len(install_calls), 1)

    def test_log_line_indicates_absent_installing(self):
        import apple_browser
        import io

        buf = io.StringIO()

        def absent_probe():
            return False

        ok, reason = apple_browser._ensure_chromium(
            probe_fn=absent_probe, install_fn=lambda: True, log_file=buf
        )
        self.assertTrue(ok)
        log = buf.getvalue()
        self.assertIn("absent", log.lower())
        self.assertIn("install", log.lower())


class BootstrapFailureDegradesTests(unittest.TestCase):
    """AC3: Bootstrap failure degrades never-blocking — reason-bearing."""

    def setUp(self):
        _reset_bootstrap()

    def test_install_returns_false_yields_unavailable_reason(self):
        import apple_browser

        def absent_probe():
            return False

        def failing_install():
            return False  # install failed

        ok, reason = apple_browser._ensure_chromium(
            probe_fn=absent_probe, install_fn=failing_install
        )
        self.assertFalse(ok)
        self.assertIsNotNone(reason)
        self.assertIn("install failed", reason.lower())

    def test_install_raises_yields_reason_bearing(self):
        import apple_browser

        def absent_probe():
            return False

        def boom_install():
            raise RuntimeError("network unreachable")

        ok, reason = apple_browser._ensure_chromium(
            probe_fn=absent_probe, install_fn=boom_install
        )
        self.assertFalse(ok)
        self.assertIsNotNone(reason)
        self.assertIn("network unreachable", reason)

    def test_probe_fn_raises_yields_reason(self):
        import apple_browser

        def boom_probe():
            raise OSError("disk full")

        ok, reason = apple_browser._ensure_chromium(
            probe_fn=boom_probe, install_fn=lambda: True
        )
        self.assertFalse(ok)
        self.assertIsNotNone(reason)
        self.assertIn("disk full", reason)

    def test_reason_first_line_only(self):
        import apple_browser

        def absent_probe():
            return False

        def install_returns_long_stderr():
            return False, "line1\nline2\nline3"

        ok, reason = apple_browser._ensure_chromium(
            probe_fn=absent_probe, install_fn=install_returns_long_stderr
        )
        self.assertFalse(ok)
        self.assertNotIn("\n", reason or "")
        self.assertIn("line1", reason or "")


class IdempotencyTests(unittest.TestCase):
    """AC5: Idempotent — repeated runs do not redo the install."""

    def setUp(self):
        _reset_bootstrap()

    def test_three_calls_only_probes_once(self):
        import apple_browser

        probe_calls = []
        install_calls = []

        def counting_probe():
            probe_calls.append(1)
            return True

        def counting_install():
            install_calls.append(1)
            return True

        for _ in range(3):
            apple_browser._ensure_chromium(
                probe_fn=counting_probe, install_fn=counting_install
            )

        self.assertEqual(len(probe_calls), 1)
        self.assertEqual(len(install_calls), 0)

    def test_present_cached_across_calls_with_different_fns(self):
        import apple_browser

        # First call: probe returns True
        ok1, _ = apple_browser._ensure_chromium(
            probe_fn=lambda: True, install_fn=lambda: True
        )
        self.assertTrue(ok1)

        # Second call: inject a probe that would fail — but cached result used
        ok2, _ = apple_browser._ensure_chromium(
            probe_fn=lambda: False, install_fn=lambda: False
        )
        self.assertTrue(ok2)  # cached from first call

    def test_absent_and_installed_cached_across_calls(self):
        import apple_browser

        install_calls = []
        # First call: probe absent, install succeeds
        ok1, _ = apple_browser._ensure_chromium(
            probe_fn=lambda: False, install_fn=lambda: [install_calls.append(1), True][1]
        )
        self.assertTrue(ok1)
        self.assertEqual(len(install_calls), 1)

        # Second call: inject broken probe — cached result used
        ok2, _ = apple_browser._ensure_chromium(
            probe_fn=lambda: (_ for _ in ()).throw(RuntimeError("x")),
            install_fn=lambda: False,
        )
        self.assertTrue(ok2)


class FetchAppleAppIntegrationTests(unittest.TestCase):
    """fetch_apple_app degrades when _ensure_chromium reports unavailable."""

    def setUp(self):
        _reset_bootstrap()
        import apple_browser
        apple_browser._ensure_chromium_done = True
        apple_browser._ensure_chromium_result = (False, "bootstrap: chromium install failed")

    def tearDown(self):
        _reset_bootstrap()

    def test_fetch_apple_app_returns_empty_on_bootstrap_failure(self):
        import apple_browser

        result = apple_browser.fetch_apple_app(
            "123", country="de", cache_dir="", fresh=True
        )
        self.assertEqual(result, {"subtitle": "", "similar_app_ids": []})

    def test_collect_subtitle_returns_empty_on_bootstrap_failure(self):
        import apple_browser

        result = apple_browser.collect_subtitle(
            "123", country="de", cache_dir="", fetch_fn=apple_browser.fetch_apple_app
        )
        self.assertEqual(result, "")

    def test_collect_similar_returns_empty_on_bootstrap_failure(self):
        import apple_browser

        result = apple_browser.collect_similar(
            "123", country="de", cache_dir="", fetch_fn=apple_browser.fetch_apple_app
        )
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()
