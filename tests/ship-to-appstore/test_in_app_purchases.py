#!/usr/bin/env python3
"""Tests for detect_in_app_purchases() in ship-to-appstore/scripts/phase0-introspect.

Run from the repo root:
    python3 tests/ship-to-appstore/test_in_app_purchases.py

These tests drive detect_in_app_purchases() in isolation. The function is
independent of the Flutter/iOS gate, so we do not need full fixtures here —
tiny tempfile repos with just pubspec.yaml and lib/ are enough. Importing the
script via importlib because, like the dispatcher it is, it has no .py
extension (so a plain `import` will not find it).

Why this file exists: the IAP gate (Phase 3 Step 10b) is the only thing
standing between a release and a Guideline 2.1(b) App-Completeness reject.
A false negative here ("no IAPs") silently skips the gate — the bug is
plausible-but-wrong output, exactly the kind CLAUDE.md asks to cover.

Lives outside skills/ on purpose: the skills CLI bundles a skill directory
as-is. See CLAUDE.md -> "Tooling and testing".
"""

import importlib.machinery
import importlib.util
import os
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPT_PATH = os.path.join(
    REPO_ROOT, "skills", "ship-to-appstore", "scripts", "phase0-introspect"
)

# The dispatcher has no .py extension, so spec_from_file_location will not pick
# a loader on its own — supply a SourceFileLoader explicitly.
_loader = importlib.machinery.SourceFileLoader("phase0_introspect", SCRIPT_PATH)
_spec = importlib.util.spec_from_loader("phase0_introspect", _loader)
P = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(P)


def _write(root: str, relpath: str, content: str) -> None:
    abspath = os.path.join(root, relpath)
    os.makedirs(os.path.dirname(abspath), exist_ok=True)
    with open(abspath, "w", encoding="utf-8") as f:
        f.write(content)


class InAppPurchasesDetectionTests(unittest.TestCase):
    def test_iap_sdk_in_pubspec_marks_present(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "pubspec.yaml", (
                "name: x\nversion: 1.0.0+1\n\n"
                "dependencies:\n"
                "  flutter:\n"
                "    sdk: flutter\n"
                "  in_app_purchase: ^3.1.0\n"
            ))
            res = P.detect_in_app_purchases(root)
            self.assertTrue(res["likely_present"])
            self.assertIn("in_app_purchase", res["packages"])

    def test_revenuecat_sdk_in_pubspec_marks_present(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "pubspec.yaml", (
                "name: x\nversion: 1.0.0+1\n\n"
                "dependencies:\n"
                "  flutter:\n"
                "    sdk: flutter\n"
                "  purchases_flutter: ^6.0.0\n"
            ))
            res = P.detect_in_app_purchases(root)
            self.assertTrue(res["likely_present"])
            self.assertIn("purchases_flutter", res["packages"])

    def test_two_distinct_code_markers_mark_present_without_sdk(self):
        # A build that wires up IAP directly without a wrapper SDK still has
        # to be caught — the in_app_purchase plugin ships with Flutter, so the
        # pubspec line is not the only valid signal.
        with tempfile.TemporaryDirectory() as root:
            _write(root, "pubspec.yaml", "name: x\nversion: 1.0.0+1\n")
            _write(root, "lib/main.dart", (
                "import 'package:flutter/material.dart';\n"
                "void main() {\n"
                "  final iap = InAppPurchase.instance;\n"
                "  iap.queryProductDetails(<String>{'premium'});\n"
                "}\n"
            ))
            res = P.detect_in_app_purchases(root)
            self.assertTrue(res["likely_present"])
            self.assertIn("InAppPurchase", res["code_markers"])
            self.assertIn("queryProductDetails", res["code_markers"])

    def test_single_stray_marker_does_not_mark_present(self):
        # One stray mention in a comment must not flip the gate on.
        with tempfile.TemporaryDirectory() as root:
            _write(root, "pubspec.yaml", "name: x\nversion: 1.0.0+1\n")
            _write(root, "lib/main.dart", (
                "// TODO: maybe call InAppPurchase one day\n"
                "void main() {}\n"
            ))
            res = P.detect_in_app_purchases(root)
            self.assertFalse(res["likely_present"])

    def test_no_iap_signals_marks_absent(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "pubspec.yaml", (
                "name: x\nversion: 1.0.0+1\n"
                "dependencies:\n"
                "  flutter:\n"
                "    sdk: flutter\n"
            ))
            _write(root, "lib/main.dart", "void main() {}\n")
            res = P.detect_in_app_purchases(root)
            self.assertFalse(res["likely_present"])
            self.assertEqual(res["packages"], [])

    def test_missing_lib_dir_is_safe(self):
        # No lib/ must not crash — just report no code markers.
        with tempfile.TemporaryDirectory() as root:
            _write(root, "pubspec.yaml", "name: x\nversion: 1.0.0+1\n")
            res = P.detect_in_app_purchases(root)
            self.assertFalse(res["likely_present"])
            self.assertEqual(res["code_markers"], [])

    def test_result_shape(self):
        with tempfile.TemporaryDirectory() as root:
            _write(root, "pubspec.yaml", "name: x\nversion: 1.0.0+1\n")
            res = P.detect_in_app_purchases(root)
            for key in ("likely_present", "packages", "code_markers"):
                self.assertIn(key, res)


if __name__ == "__main__":
    unittest.main(verbosity=2)
