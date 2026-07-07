#!/usr/bin/env python3
"""Tests for owasp-bsi-audit/scripts/render_report.py.

Covers the sorting/grouping logic (natural_key, the id-parsing helpers,
is_open), compute_scope's applied/not-covered diffing, and an end-to-end
build_markdown() smoke test against a synthetic audit directory - this is
exactly the kind of silent-wrong-output risk the report's Basis-before-
Standard / natural-number ordering had before it was fixed, so a sorting
regression here would otherwise only show up as a subtly wrong report a
human has to notice by eye.

Run from the repo root:
    python3 tests/owasp-bsi-audit/test_render_report.py
"""

import json
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "owasp-bsi-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import render_report as R  # noqa: E402


class NaturalKeyTests(unittest.TestCase):
    def test_a3_sorts_before_a12(self):
        ids = ["CON.10.A12", "CON.10.A1", "CON.10.A3", "CON.10.A2"]
        ids.sort(key=R.natural_key)
        self.assertEqual(ids, ["CON.10.A1", "CON.10.A2", "CON.10.A3", "CON.10.A12"])

    def test_asvs_multi_segment_numbers(self):
        ids = ["V7.10.1", "V7.3.2", "V7.3.1", "V7.2.1"]
        ids.sort(key=R.natural_key)
        self.assertEqual(ids, ["V7.2.1", "V7.3.1", "V7.3.2", "V7.10.1"])

    def test_stable_for_equal_ids(self):
        self.assertEqual(R.natural_key("CON.10.A1"), R.natural_key("CON.10.A1"))


class IdGroupingHelperTests(unittest.TestCase):
    def test_bsi_baustein_of(self):
        self.assertEqual(R.bsi_baustein_of("CON.10.A3"), "CON.10")
        self.assertEqual(R.bsi_baustein_of("APP.3.1.A12"), "APP.3.1")

    def test_asvs_chapter_of(self):
        self.assertEqual(R.asvs_chapter_of("V7.3.2"), "V7")

    def test_masvs_group_of(self):
        self.assertEqual(R.masvs_group_of("MASVS-STORAGE-1"), "MASVS-STORAGE")

    def test_ssdf_group_of(self):
        self.assertEqual(R.ssdf_group_of("PW.6.1"), "PW.6")
        self.assertEqual(R.ssdf_group_of("RV.1.3"), "RV.1")

    def test_slsa_group_of(self):
        self.assertEqual(R.slsa_group_of("SLSA-BUILD-1"), "BUILD")


class IsOpenTests(unittest.TestCase):
    def test_open_statuses(self):
        for status in ("nein", "teilweise", "fail", "partial"):
            self.assertTrue(R.is_open({"status": status}), status)

    def test_closed_statuses(self):
        for status in ("ja", "pass", "entbehrlich", "n_a", "manual"):
            self.assertFalse(R.is_open({"status": status}), status)


class ComputeScopeTests(unittest.TestCase):
    def setUp(self):
        self.catalog_meta = {
            "bsi": {
                "CON.10": {"title": "Entwicklung von Webanwendungen", "description": "d1"},
                "APP.4.3": {"title": "Relationale Datenbanken", "description": "d2"},
            },
            "asvs": {"V7": "Authentication", "V8": "Authorization"},
            "masvs": {"MASVS-STORAGE": "Storage"},
            "ssdf": {"PW.6": "Compiler security"},
            "slsa": {"BUILD": "Build integrity"},
        }

    def test_applied_and_not_covered_bsi(self):
        bsi = [{"id": "CON.10.A1"}, {"id": "CON.10.A3"}]
        scope = R.compute_scope(bsi, [], [], [], [], self.catalog_meta)
        self.assertEqual([c for c, _, _ in scope["applied_bsi"]], ["CON.10"])
        self.assertEqual([c for c, _ in scope["not_covered_bsi"]], ["APP.4.3"])

    def test_applied_asvs_partial_coverage(self):
        asvs = [{"id": "V7.1.1"}]
        scope = R.compute_scope([], asvs, [], [], [], self.catalog_meta)
        self.assertEqual([c for c, _ in scope["applied_asvs"]], ["V7"])
        self.assertEqual([c for c, _ in scope["not_covered_asvs"]], ["V8"])

    def test_masvs_and_slsa_applied_flags(self):
        scope_without = R.compute_scope([], [], [], [], [], self.catalog_meta)
        self.assertFalse(scope_without["masvs_applied_at_all"])
        self.assertFalse(scope_without["slsa_applied_at_all"])

        masvs = [{"id": "MASVS-STORAGE-1"}]
        slsa = [{"id": "SLSA-BUILD-1"}]
        scope_with = R.compute_scope([], [], masvs, [], slsa, self.catalog_meta)
        self.assertTrue(scope_with["masvs_applied_at_all"])
        self.assertTrue(scope_with["slsa_applied_at_all"])

    def test_empty_catalog_meta_yields_empty_not_covered(self):
        empty_meta = {"bsi": {}, "asvs": {}, "masvs": {}, "ssdf": {}, "slsa": {}}
        scope = R.compute_scope([{"id": "CON.10.A1"}], [], [], [], [], empty_meta)
        self.assertEqual(scope["not_covered_bsi"], [])


class BadgeHtmlEscapingTests(unittest.TestCase):
    def test_status_badge_escapes_and_labels(self):
        badge = R.status_badge("teilweise", "bsi")
        self.assertIn("badge-status-teilweise", badge)
        self.assertIn("Teilweise", badge)

    def test_severity_badge_unknown_falls_back_to_raw_value(self):
        badge = R.severity_badge("weird")
        self.assertIn("badge-sev-weird", badge)
        self.assertIn("weird", badge)

    def test_rid_escapes_html(self):
        chip = R.rid('<script>alert(1)</script>')
        self.assertNotIn("<script>", chip)
        self.assertIn("&lt;script&gt;", chip)


class BuildMarkdownEndToEndTests(unittest.TestCase):
    """Writes a synthetic audit dir and asserts on the actual rendered
    Markdown - catches ordering/grouping regressions that unit tests on
    individual helpers could miss when they interact."""

    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.audit_dir = pathlib.Path(self.tmpdir.name)
        (self.audit_dir / "findings").mkdir()
        (self.audit_dir / "profile.json").write_text(
            json.dumps({"target": "test-target"}), encoding="utf-8")
        (self.audit_dir / "methodik.json").write_text(json.dumps({
            "strukturanalyse": [{"id": "Z1", "titel": "Backend", "typ": "App", "sprache_framework": "PHP"}],
            "schutzbedarf": [{"zielobjekt_id": "Z1", "vertraulichkeit": "normal", "integritaet": "normal",
                               "verfuegbarkeit": "normal", "einschaetzung": "normal", "begruendung": "test"}],
            "modellierung": [{"zielobjekt_id": "Z1", "bausteine": ["CON.10"], "begruendung": "test"}],
        }), encoding="utf-8")

    def tearDown(self):
        self.tmpdir.cleanup()

    def _write_findings(self, name, findings):
        (self.audit_dir / "findings" / name).write_text(
            json.dumps(findings), encoding="utf-8")

    def test_bsi_basis_group_renders_before_standard_group(self):
        self._write_findings("bsi.json", [
            {"id": "CON.10.A11", "standard": "bsi", "title": "Standard req", "level": "Standard",
             "status": "ja", "severity": "info", "evidence": [], "remediation": "ok"},
            {"id": "CON.10.A1", "standard": "bsi", "title": "Basis req", "level": "Basis",
             "status": "ja", "severity": "info", "evidence": [], "remediation": "ok"},
        ])
        md, _ = R.build_markdown(self.audit_dir)
        basis_pos = md.index("#### Basis-Anforderungen")
        standard_pos = md.index("#### Standard-Anforderungen")
        self.assertLess(basis_pos, standard_pos)

    def test_requirement_ids_render_in_natural_order_within_group(self):
        self._write_findings("bsi.json", [
            {"id": "CON.10.A12", "standard": "bsi", "title": "t12", "level": "Basis",
             "status": "ja", "severity": "info", "evidence": [], "remediation": "ok"},
            {"id": "CON.10.A2", "standard": "bsi", "title": "t2", "level": "Basis",
             "status": "ja", "severity": "info", "evidence": [], "remediation": "ok"},
        ])
        md, _ = R.build_markdown(self.audit_dir)
        self.assertLess(md.index("CON.10.A2"), md.index("CON.10.A12"))

    def test_open_findings_overview_only_lists_open_statuses(self):
        self._write_findings("bsi.json", [
            {"id": "CON.10.A1", "standard": "bsi", "title": "done", "level": "Basis",
             "status": "ja", "severity": "info", "evidence": [], "remediation": "ok"},
            {"id": "CON.10.A3", "standard": "bsi", "title": "broken", "level": "Basis",
             "status": "nein", "severity": "high", "begruendung": "missing", "evidence": [], "remediation": "fix it"},
        ])
        md, _ = R.build_markdown(self.audit_dir)
        overview = md.split("## Übersicht offener Punkte")[1].split("## Abschluss")[0]
        self.assertIn("CON.10.A3", overview)
        self.assertNotIn("CON.10.A1", overview)

    def test_hosting_finding_excluded_from_manual_section(self):
        self._write_findings("bsi.json", [
            {"id": "APP.4.3.A1", "standard": "bsi", "title": "hosting thing", "level": "Basis",
             "status": "manual", "severity": "medium", "evidence": [], "remediation": "n/a",
             "out_of_scope_reason": "hosting provider controls this"},
        ])
        md, _ = R.build_markdown(self.audit_dir)
        manual_section = md.split("## Manuelle Prüfung nötig")[1].split("## Nicht in unserer Hand")[0]
        hosting_section = md.split("## Nicht in unserer Hand")[1].split("## Risikoanalyse-Vermerk")[0]
        self.assertNotIn("APP.4.3.A1", manual_section)
        self.assertIn("APP.4.3.A1", hosting_section)

    def test_glossary_omits_masvs_entry_when_masvs_absent(self):
        self._write_findings("bsi.json", [
            {"id": "CON.10.A1", "standard": "bsi", "title": "x", "level": "Basis",
             "status": "ja", "severity": "info", "evidence": [], "remediation": "ok"},
        ])
        md, _ = R.build_markdown(self.audit_dir)
        glossary = md.split("## Glossar")[1].split("## Executive Summary")[0]
        self.assertIn("BSI", glossary)
        self.assertNotIn("MASVS", glossary)


class BuildFixPlanTests(unittest.TestCase):
    def test_basis_open_bsi_goes_to_sofort(self):
        findings = {
            "bsi": [{"id": "CON.10.A3", "title": "t", "level": "Basis", "status": "nein",
                      "severity": "high", "evidence": [], "remediation": "fix"}],
            "asvs": [], "masvs": [], "ssdf": [], "slsa": [],
        }
        plan = R.build_fix_plan(findings)
        sofort = plan.split("## Sofort")[1].split("## Kurzfristig")[0]
        self.assertIn("CON.10.A3", sofort)

    def test_standard_open_bsi_goes_to_kurzfristig(self):
        findings = {
            "bsi": [{"id": "CON.10.A11", "title": "t", "level": "Standard", "status": "teilweise",
                      "severity": "medium", "evidence": [], "remediation": "fix"}],
            "asvs": [], "masvs": [], "ssdf": [], "slsa": [],
        }
        plan = R.build_fix_plan(findings)
        kurzfristig = plan.split("## Kurzfristig")[1].split("## Mittelfristig")[0]
        self.assertIn("CON.10.A11", kurzfristig)

    def test_ssdf_and_slsa_findings_are_bucketed_by_severity(self):
        findings = {
            "bsi": [], "asvs": [], "masvs": [],
            "ssdf": [{"id": "PW.6.1", "title": "t", "status": "fail",
                       "severity": "critical", "evidence": [], "remediation": "fix"}],
            "slsa": [{"id": "SLSA-BUILD-2", "title": "t", "status": "fail",
                       "severity": "low", "evidence": [], "remediation": "fix"}],
        }
        plan = R.build_fix_plan(findings)
        sofort = plan.split("## Sofort")[1].split("## Kurzfristig")[0]
        mittelfristig = plan.split("## Mittelfristig")[1]
        self.assertIn("PW.6.1", sofort)
        self.assertIn("SLSA-BUILD-2", mittelfristig)

    def test_closed_findings_never_appear(self):
        findings = {
            "bsi": [{"id": "CON.10.A1", "title": "t", "level": "Basis", "status": "ja",
                      "severity": "info", "evidence": [], "remediation": "ok"}],
            "asvs": [], "masvs": [], "ssdf": [], "slsa": [],
        }
        plan = R.build_fix_plan(findings)
        self.assertNotIn("CON.10.A1", plan)


if __name__ == "__main__":
    unittest.main()
