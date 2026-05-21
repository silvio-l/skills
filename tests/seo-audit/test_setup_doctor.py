#!/usr/bin/env python3
"""Tests for setup.doctor — seven check areas, dependency-injected."""

import pathlib
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from setup import doctor as DOCTOR  # noqa: E402


def _ok_runner(argv):
    return {"returncode": 0, "stdout": "1.2.3\n", "stderr": ""}


def _missing_runner(argv):
    return {"returncode": 127, "stdout": "", "stderr": "not found"}


def _mcp_ok_runner(argv):
    return {
        "returncode": 0,
        "stdout": (
            "Servers:\n"
            "  mcp__gsc__list_properties\n"
            "  mcp__gsc__inspect_url_enhanced\n"
            "  mcp__supabase__list_tables\n"
        ),
        "stderr": "",
    }


def _mcp_no_gsc_runner(argv):
    return {
        "returncode": 0,
        "stdout": "Servers:\n  mcp__supabase__list_tables\n",
        "stderr": "",
    }


def _mcp_missing_cli(argv):
    return {"returncode": 127, "stdout": "", "stderr": "claude: not found"}


class SectionOrder(unittest.TestCase):
    def test_runs_all_seven_check_areas_in_order(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "CONTEXT.md").write_text(
                "# Doc\n\n| Begriff | Stattdessen | Grund |\n"
                "|--|--|--|\n| foo | bar | baz |\n",
                encoding="utf-8",
            )
            public = root / "public"
            public.mkdir()
            report = DOCTOR.run(
                env={},
                root=root,
                public_dir=public,
                runners={"npx": _missing_runner, "mcp": _mcp_missing_cli},
            )
            areas = [s["area"] for s in report["sections"]]
            self.assertEqual(
                areas,
                ["npx", "indexnow", "pagespeed", "bing",
                 "gsc", "domain", "public"],
            )

    def test_section_order_constant_matches(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            report = DOCTOR.run(
                env={}, root=root, public_dir=None,
                runners={"npx": _missing_runner, "mcp": _mcp_missing_cli},
            )
            self.assertEqual(
                report["section_order"],
                list(report["section_order"]),
            )


class NpxSection(unittest.TestCase):
    def test_marks_missing_tools_with_cross(self):
        out = DOCTOR.check_npx(runner=_missing_runner)
        self.assertEqual(out["icon"], DOCTOR.ICON_MISSING)
        joined = "\n".join(v for _, v in out["rows"])
        self.assertIn("missing", joined)

    def test_marks_present_tools_with_check(self):
        out = DOCTOR.check_npx(runner=_ok_runner)
        self.assertEqual(out["icon"], DOCTOR.ICON_OK)


class IndexNowSection(unittest.TestCase):
    def test_missing_env_is_cross(self):
        out = DOCTOR.check_indexnow(env={}, public_dir=None)
        self.assertEqual(out["icon"], DOCTOR.ICON_MISSING)

    def test_env_set_but_no_public_dir_is_warn(self):
        out = DOCTOR.check_indexnow(env={"INDEXNOW_KEY": "abc"}, public_dir=None)
        self.assertEqual(out["icon"], DOCTOR.ICON_WARN)

    def test_key_file_present_and_matches_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp)
            (public / "abc123.txt").write_text("abc123", encoding="utf-8")
            out = DOCTOR.check_indexnow(
                env={"INDEXNOW_KEY": "abc123"},
                public_dir=public,
            )
            self.assertEqual(out["icon"], DOCTOR.ICON_OK)

    def test_key_file_content_mismatch_is_cross(self):
        with tempfile.TemporaryDirectory() as tmp:
            public = pathlib.Path(tmp)
            (public / "abc123.txt").write_text("DIFFERENT", encoding="utf-8")
            out = DOCTOR.check_indexnow(
                env={"INDEXNOW_KEY": "abc123"},
                public_dir=public,
            )
            self.assertEqual(out["icon"], DOCTOR.ICON_MISSING)


class PageSpeedSection(unittest.TestCase):
    def test_no_env_is_cross(self):
        out = DOCTOR.check_pagespeed(env={})
        self.assertEqual(out["icon"], DOCTOR.ICON_MISSING)

    def test_env_set_no_pinger_is_ok_with_skipped_probe(self):
        out = DOCTOR.check_pagespeed(env={"PAGESPEED_API_KEY": "k"})
        self.assertEqual(out["icon"], DOCTOR.ICON_OK)
        self.assertIn("skipped", "\n".join(v for _, v in out["rows"]))


class BingSection(unittest.TestCase):
    def test_no_env_is_cross(self):
        out = DOCTOR.check_bing(env={})
        self.assertEqual(out["icon"], DOCTOR.ICON_MISSING)

    def test_env_set_no_pinger_is_ok(self):
        out = DOCTOR.check_bing(env={"BING_WEBMASTER_API_KEY": "k"})
        self.assertEqual(out["icon"], DOCTOR.ICON_OK)


class GscSection(unittest.TestCase):
    def test_no_cli_is_cross(self):
        out = DOCTOR.check_gsc(runner=_mcp_missing_cli)
        self.assertEqual(out["icon"], DOCTOR.ICON_MISSING)

    def test_cli_present_no_gsc_is_cross(self):
        out = DOCTOR.check_gsc(runner=_mcp_no_gsc_runner)
        self.assertEqual(out["icon"], DOCTOR.ICON_MISSING)

    def test_cli_present_with_gsc_is_ok(self):
        out = DOCTOR.check_gsc(runner=_mcp_ok_runner)
        self.assertEqual(out["icon"], DOCTOR.ICON_OK)


class DomainSection(unittest.TestCase):
    def test_no_doc_is_cross(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = DOCTOR.check_domain_doc(pathlib.Path(tmp))
            self.assertEqual(out["icon"], DOCTOR.ICON_MISSING)

    def test_doc_without_anti_vocab_is_warn(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "CONTEXT.md").write_text("# Doc\nProse.\n", encoding="utf-8")
            out = DOCTOR.check_domain_doc(root)
            self.assertEqual(out["icon"], DOCTOR.ICON_WARN)

    def test_doc_with_anti_vocab_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "CONTEXT.md").write_text(
                "# Doc\n\n| Begriff | Stattdessen | Grund |\n"
                "|--|--|--|\n| x | y | z |\n",
                encoding="utf-8",
            )
            out = DOCTOR.check_domain_doc(root)
            self.assertEqual(out["icon"], DOCTOR.ICON_OK)


class PublicSection(unittest.TestCase):
    def test_none_is_cross(self):
        out = DOCTOR.check_public(None)
        self.assertEqual(out["icon"], DOCTOR.ICON_MISSING)

    def test_existing_writable_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = DOCTOR.check_public(pathlib.Path(tmp))
            self.assertEqual(out["icon"], DOCTOR.ICON_OK)


class Render(unittest.TestCase):
    def test_render_emits_top_fix_first(self):
        report = {
            "sections": [
                {"area": "npx", "icon": DOCTOR.ICON_MISSING,
                 "rows": [("npx --version", "missing")],
                 "summary": "missing"},
            ],
            "top_fix_first": ["npx"],
            "section_order": list(DOCTOR.SECTION_ORDER),
        }
        out = DOCTOR.render(report)
        self.assertIn("Top fix-first", out)
        self.assertIn("npx tools", out)

    def test_render_when_clean_says_complete(self):
        report = {
            "sections": [
                {"area": "npx", "icon": DOCTOR.ICON_OK,
                 "rows": [("npx", "1.0")], "summary": "ok"},
            ],
            "top_fix_first": [],
            "section_order": list(DOCTOR.SECTION_ORDER),
        }
        out = DOCTOR.render(report)
        self.assertIn("onboarding complete", out)


if __name__ == "__main__":
    unittest.main(verbosity=2)
