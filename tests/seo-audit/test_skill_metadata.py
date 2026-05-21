#!/usr/bin/env python3
"""Structural checks for the seo-audit skill bundle.

Verifies the AC items that are documents rather than code:
* `SKILL.md` exists with the right frontmatter shape.
* Every phase doc referenced in `SKILL.md` exists.
* `templates/report.md` exists and is non-empty.
* `README.md` at the repo root contains a `### seo-audit` block.

Run from the repo root:
    python3 tests/seo-audit/test_skill_metadata.py
"""

import pathlib
import re
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SKILL_DIR = REPO_ROOT / "skills" / "seo-audit"
SKILL_MD = SKILL_DIR / "SKILL.md"
README = REPO_ROOT / "README.md"

sys.dont_write_bytecode = True


def _read(p: pathlib.Path) -> str:
    return p.read_text(encoding="utf-8")


def _frontmatter(text: str) -> dict:
    m = re.match(r"---\n(.*?)\n---\n", text, re.DOTALL)
    if not m:
        return {}
    out = {}
    for line in m.group(1).splitlines():
        if ":" in line and not line.startswith(" "):
            k, _, v = line.partition(":")
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


class SkillMd(unittest.TestCase):
    def test_skill_md_exists(self):
        self.assertTrue(SKILL_MD.is_file(),
                        msg=f"missing {SKILL_MD}")

    def test_frontmatter_name_matches_directory(self):
        fm = _frontmatter(_read(SKILL_MD))
        self.assertEqual(fm.get("name"), "seo-audit")

    def test_description_is_non_empty_and_has_trigger_phrase(self):
        fm = _frontmatter(_read(SKILL_MD))
        desc = fm.get("description", "")
        self.assertGreater(len(desc), 80,
                           "description should be a full paragraph")
        # Trigger marker convention per CLAUDE.md.
        self.assertRegex(desc.lower(), r"use when",
                         "description must end with 'Use when …' trigger phrases")


class PhaseDocs(unittest.TestCase):
    REQUIRED = ["inventory.md", "brand.md", "probes.md", "push.md",
                "setup.md", "synthesis.md", "report.md"]

    def test_phase_docs_exist(self):
        for name in self.REQUIRED:
            with self.subTest(name=name):
                self.assertTrue((SKILL_DIR / name).is_file(),
                                msg=f"missing skills/seo-audit/{name}")

    def test_skill_md_links_each_phase_doc(self):
        text = _read(SKILL_MD)
        for name in self.REQUIRED:
            with self.subTest(name=name):
                self.assertIn(name, text,
                              msg=f"SKILL.md should reference {name}")


class SetupModule(unittest.TestCase):
    REQUIRED = [
        "scripts/setup/__init__.py",
        "scripts/setup/urls.py",
        "scripts/setup/diagnoses.py",
        "scripts/setup/doctor.py",
        "scripts/setup/verify.py",
        "scripts/setup/setup_indexnow.py",
        "scripts/setup/setup_pagespeed.py",
        "scripts/setup/setup_bing.py",
        "scripts/setup/setup_gsc.py",
    ]

    def test_setup_module_files_exist(self):
        for relpath in self.REQUIRED:
            with self.subTest(relpath=relpath):
                self.assertTrue((SKILL_DIR / relpath).is_file(),
                                msg=f"missing skills/seo-audit/{relpath}")

    def test_setup_md_has_live_smoke_section(self):
        body = _read(SKILL_DIR / "setup.md")
        self.assertRegex(body, r"(?m)^## Live-Smoke",
                         "setup.md must have a `## Live-Smoke` section")

    def test_skill_md_references_setup_md(self):
        text = _read(SKILL_MD)
        self.assertIn("setup.md", text)

    def test_skill_md_argument_hint_mentions_doctor_setup_verify(self):
        text = _read(SKILL_MD)
        for flag in ("--doctor", "--setup", "--verify"):
            with self.subTest(flag=flag):
                self.assertIn(flag, text,
                              msg=f"SKILL.md should mention {flag}")


class FreeTierTable(unittest.TestCase):
    """AC11 — free-tier table stays consistent (no new tools)."""

    EXPECTED_ROWS = [
        "Lighthouse",
        "pa11y",
        "W3C Nu validator",
        "Schema.org validator",
        "Mozilla HTTP Observatory",
        "Google Search Console API",
        "Google PageSpeed Insights API",
        "IndexNow",
        "Bing Webmaster URL Submission API",
        "`llms.txt`",
    ]

    def test_existing_free_tier_rows_are_present(self):
        body = _read(SKILL_MD)
        for row in self.EXPECTED_ROWS:
            with self.subTest(row=row):
                self.assertIn(row, body,
                              msg=f"free-tier row '{row}' must remain")


class Template(unittest.TestCase):
    def test_template_exists_and_has_sections(self):
        tpl = SKILL_DIR / "templates" / "report.md"
        self.assertTrue(tpl.is_file())
        body = _read(tpl)
        self.assertIn("Executive Summary", body)
        self.assertIn("Findings nach Kategorie", body)
        self.assertIn("Diff zum letzten Lauf", body)
        self.assertIn("Empfehlungen", body)


class Readme(unittest.TestCase):
    def test_readme_lists_seo_audit(self):
        body = _read(README)
        self.assertRegex(body, r"###\s+`?seo-audit`?",
                         "README needs a `### seo-audit` block")
        # Problem/Fix shape — mirrors the other skills.
        seo_section = re.search(
            r"###\s+`?seo-audit`?(.*?)(?=\n###\s|\n## )",
            body, re.DOTALL,
        )
        self.assertIsNotNone(seo_section)
        section = seo_section.group(1)
        self.assertIn("Problem", section)
        self.assertIn("Fix", section)


if __name__ == "__main__":
    unittest.main(verbosity=2)
