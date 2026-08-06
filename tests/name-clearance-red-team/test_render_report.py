#!/usr/bin/env python3
"""Tests for name-clearance-red-team/scripts/render_report.py.

Covers the workdir-loading/merge logic (plan rows overridden by cluster
files, findings flattened across cluster files) and the RESULT INCOMPLETE
behavior: an open gate must replace only the verdict line, never suppress
the rest of the report - that's the whole point of the design (see
RISK-MODEL.md), so a regression here is exactly the kind of silent
plausible-but-wrong output that would go unnoticed without a test.

Run from the repo root:
    python3 tests/name-clearance-red-team/test_render_report.py
"""

import json
import pathlib
import sys
import tempfile
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "name-clearance-red-team" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import render_report as RR  # noqa: E402
import risk_model as R  # noqa: E402


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f)


MINIMAL_PROFILE = {
    "name": "Zynqora", "name_type": "company", "goods_and_services": ["SaaS"],
    "target_territories": ["DE"], "planned_use": ["word_mark"], "mode": "deep",
    "prior_events": {"none": True}, "assumptions": [], "created_at": "2026-08-07T00:00:00Z",
}


class LoadWorkdirTests(unittest.TestCase):
    def test_cluster_file_overrides_plan_row(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = pathlib.Path(tmp)
            write_json(workdir / "profile.json", MINIMAL_PROFILE)
            plan_row = {"query": "Zynqora", "source_id": "dpma-register", "territory": "DE",
                        "search_type": "exact", "source_category": "registered_mark",
                        "cluster_id": "de-eu-registers",
                        "date": "2026-08-07", "performed_by": "agent", "status": "not_attempted"}
            write_json(workdir / "searchlog" / "_plan.json", {"rows": [plan_row]})
            completed_row = dict(plan_row, status="completed", result_summary="no hits")
            write_json(workdir / "searchlog" / "de-eu-registers.json", [completed_row])

            _, _, _, rows, _, _ = RR.load_workdir(workdir)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["status"], "completed")

    def test_plan_only_row_stays_not_attempted_when_no_cluster_file_covers_it(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = pathlib.Path(tmp)
            write_json(workdir / "profile.json", MINIMAL_PROFILE)
            plan_row = {"query": "Zynqora", "source_id": "wipo-gbd", "territory": "US",
                        "search_type": "exact", "source_category": "registered_mark",
                        "cluster_id": "intl-wipo",
                        "date": "2026-08-07", "performed_by": "agent", "status": "not_attempted"}
            write_json(workdir / "searchlog" / "_plan.json", {"rows": [plan_row]})

            _, _, _, rows, _, _ = RR.load_workdir(workdir)
            self.assertEqual(rows[0]["status"], "not_attempted")

    def test_cluster_id_mismatch_between_plan_and_cluster_row_leaves_plan_row_stuck(self):
        # Regression guard: if a dispatched cluster ever omits cluster_id (or sets a
        # different one than the plan row it's meant to complete), the merge key no
        # longer matches - both rows survive and the plan row stays not_attempted
        # forever, which is exactly the silent RESULT INCOMPLETE this key exists to prevent.
        with tempfile.TemporaryDirectory() as tmp:
            workdir = pathlib.Path(tmp)
            write_json(workdir / "profile.json", MINIMAL_PROFILE)
            plan_row = {"query": "Zynqora", "source_id": "dpma-register", "territory": "DE",
                        "search_type": "exact", "source_category": "registered_mark",
                        "cluster_id": "de-eu-registers",
                        "date": "2026-08-07", "performed_by": "agent", "status": "not_attempted"}
            write_json(workdir / "searchlog" / "_plan.json", {"rows": [plan_row]})
            completed_row = dict(plan_row, cluster_id=None, status="completed", result_summary="no hits")
            write_json(workdir / "searchlog" / "de-eu-registers.json", [completed_row])

            _, _, _, rows, _, _ = RR.load_workdir(workdir)
            self.assertEqual(len(rows), 2)
            statuses = {r["status"] for r in rows}
            self.assertIn("not_attempted", statuses)

    def test_rows_differing_only_in_cluster_id_both_survive(self):
        # Two linguistic clusters (de, en) can legitimately share query/source_id/territory
        # (e.g. source_id: model-knowledge). Only cluster_id tells them apart -
        # the merge key must include it or one silently overwrites the other.
        with tempfile.TemporaryDirectory() as tmp:
            workdir = pathlib.Path(tmp)
            write_json(workdir / "profile.json", MINIMAL_PROFILE)
            row_de = {"query": "Zynqora", "source_id": "model-knowledge", "territory": "DE",
                      "search_type": "linguistic", "source_category": "linguistic",
                      "cluster_id": "linguistic-de", "date": "2026-08-07",
                      "performed_by": "agent", "status": "completed"}
            row_en = dict(row_de, cluster_id="linguistic-en")
            write_json(workdir / "searchlog" / "linguistic-de.json", [row_de])
            write_json(workdir / "searchlog" / "linguistic-en.json", [row_en])

            _, _, _, rows, _, _ = RR.load_workdir(workdir)
            self.assertEqual({r["cluster_id"] for r in rows}, {"linguistic-de", "linguistic-en"})

    def test_findings_flattened_across_cluster_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = pathlib.Path(tmp)
            write_json(workdir / "profile.json", MINIMAL_PROFILE)
            write_json(workdir / "findings" / "cluster-a.json", [{"id": "a-1"}])
            write_json(workdir / "findings" / "cluster-b.json", [{"id": "b-1"}, {"id": "b-2"}])

            _, _, _, _, findings, _ = RR.load_workdir(workdir)
            self.assertEqual({f["id"] for f in findings}, {"a-1", "b-1", "b-2"})

    def test_missing_optional_files_default_gracefully(self):
        with tempfile.TemporaryDirectory() as tmp:
            workdir = pathlib.Path(tmp)
            write_json(workdir / "profile.json", MINIMAL_PROFILE)
            profile, variants, digital, rows, findings, redteam = RR.load_workdir(workdir)
            self.assertEqual(variants, {})
            self.assertEqual(digital, {"records": []})
            self.assertEqual(rows, [])
            self.assertEqual(findings, [])
            self.assertEqual(redteam, {})


class RenderMarkdownTests(unittest.TestCase):
    def test_open_gate_replaces_only_verdict_line_report_stays_full(self):
        profile = dict(MINIMAL_PROFILE, assumptions=[{"field": "risk_tolerance", "assumed_value": "low", "reason": "default"}])
        rows = [{"query": "Zynqora", "source_id": "dpma-register", "territory": "DE",
                 "search_type": "exact", "source_category": "registered_mark",
                 "date": "2026-08-07", "performed_by": "agent", "status": "blocked",
                 "block_reason": "empty_shell",
                 "manual_instructions": {"url": "https://register.example/search", "search_string": "Zynqora"}}]
        findings = [{
            "id": "f-1", "cluster_id": "de-eu-registers", "territory": "DE", "category": "registered_mark",
            "source_id": "dpma-register", "severity": 1, "likelihood": 1, "legal_proximity": 1,
            "evidence_quality": 2, "verification_status": "reported_by_search_snippet",
            "strongest_counter_argument": "weak overlap", "summary": "minor collision",
            "evidence": [{"url": "https://example.com"}], "retrieved_at": "2026-08-07T00:00:00Z",
        }]
        markdown = RR.render_markdown(profile, {"variants": []}, {"records": []}, rows, findings, {}, "deep")

        self.assertIn(R.INCOMPLETE_VERDICT, markdown)
        self.assertNotIn("PRELIMINARILY CLEAR", markdown)
        # everything else must still be present, not suppressed
        self.assertIn("minor collision", markdown)
        self.assertIn("## Territorial coverage", markdown)
        self.assertIn("## Gate status", markdown)
        self.assertIn("## What is missing and how to complete it", markdown)
        self.assertIn("https://register.example/search", markdown)
        self.assertIn("## Limitations", markdown)

    def test_quick_mode_only_shows_quick_verdict(self):
        markdown = RR.render_markdown(MINIMAL_PROFILE, {}, {}, [], [], {}, "quick")
        self.assertIn("Quick Scan result:", markdown)
        for label in ("Gate status", "Red team", "Registrability assessment"):
            self.assertNotIn(label, markdown)

    def test_territorial_coverage_shows_not_searched_for_uncovered_territory(self):
        profile = dict(MINIMAL_PROFILE, target_territories=["DE", "US"])
        rows = [{"query": "Zynqora", "source_id": "dpma-register", "territory": "DE",
                 "search_type": "exact", "source_category": "registered_mark",
                 "date": "2026-08-07", "performed_by": "agent", "status": "completed"}]
        markdown = RR.render_markdown(profile, {}, {}, rows, [], {}, "deep")
        self.assertIn("| US |", markdown)
        self.assertIn("not searched", markdown)


if __name__ == "__main__":
    unittest.main()
