#!/usr/bin/env python3
"""Tests for name-clearance-red-team/scripts/risk_model.py.

The most important test file in this skill. risk_model.py is the only place
a band/gate/verdict is computed, and its central job is refusing to let a
blocked lookup, an unverified claim, or an unresearched name masquerade as
a clean result. Every test here is an anti-fabrication invariant: given
artifacts a rushed or capability-limited run could plausibly produce, does
the model refuse to call it clean?

Run from the repo root:
    python3 tests/name-clearance-red-team/test_risk_model.py
"""

import pathlib
import sys
import unittest

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "name-clearance-red-team" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

sys.dont_write_bytecode = True

import risk_model as R  # noqa: E402


def make_profile(**overrides):
    base = {
        "name": "Zynqora",
        "name_type": "company",
        "goods_and_services": ["SaaS analytics"],
        "target_territories": ["DE", "EU"],
        "planned_use": ["word_mark"],
        "mode": "deep",
        "prior_events": {"cease_and_desist": False, "ongoing_dispute": False,
                          "unclear_rights_chain": False, "high_investment": False, "none": True},
        "assumptions": [],
        "created_at": "2026-08-07T00:00:00Z",
        "languages": ["de"],
    }
    base.update(overrides)
    return base


def make_row(**overrides):
    base = {
        "query": "Zynqora", "source_id": "dpma-register", "territory": "DE",
        "search_type": "exact", "source_category": "registered_mark",
        "date": "2026-08-07", "performed_by": "agent", "status": "completed",
    }
    base.update(overrides)
    return base


def make_finding(**overrides):
    base = {
        "id": "f-001", "cluster_id": "de-eu-registers", "territory": "DE",
        "category": "registered_mark", "source_id": "dpma-register",
        "severity": 1, "likelihood": 1, "legal_proximity": 1, "evidence_quality": 3,
        "verification_status": "verified_by_direct_lookup",
        "strongest_counter_argument": "goods do not overlap",
        "summary": "minor hit", "evidence": [{"url": "https://example.com"}],
        "retrieved_at": "2026-08-07T00:00:00Z",
    }
    base.update(overrides)
    return base


FULL_ROWS = [
    make_row(search_type="exact", source_category="registered_mark"),
    make_row(search_type="similarity", source_category="registered_mark"),
    make_row(search_type="unregistered", source_category="unregistered"),
    make_row(search_type="company_name", source_category="company_register", territory="DE"),
    make_row(search_type="company_name", source_category="company_register", territory="EU"),
]

# A realistic ordinary clean run: absolute_grounds_checked and
# special_sector_rules_checked are satisfied by a completed search-log row
# alone, per cluster_id convention — never by a finding, since a clean check
# produces none (ORCHESTRATION.md rule 2).
CLEAN_ROWS = FULL_ROWS + [
    make_row(query="Zynqora", source_id="model-knowledge", territory="DE",
              search_type="linguistic", source_category="linguistic",
              cluster_id="linguistic-de", status="completed"),
    make_row(query="Zynqora", source_id="web-search-general", territory="DE",
              search_type="sector", source_category="sector",
              cluster_id="sector-finance", status="completed"),
]

FULL_REDTEAM = {
    "attacks": [{"vector": "family_of_marks", "severity": 1, "argument": "a", "rebuttal": "r"}],
    "missed_vectors": [],
}


class CapEvidenceQualityTests(unittest.TestCase):
    def test_unverified_forced_to_zero(self):
        f = make_finding(verification_status="unverified", evidence_quality=3)
        self.assertEqual(R.cap_evidence_quality(f), 0)

    def test_snippet_capped_at_one(self):
        f = make_finding(verification_status="reported_by_search_snippet", evidence_quality=3)
        self.assertEqual(R.cap_evidence_quality(f), 1)

    def test_verified_direct_lookup_not_capped_below_reported(self):
        f = make_finding(verification_status="verified_by_direct_lookup", evidence_quality=2)
        self.assertEqual(R.cap_evidence_quality(f), 2)

    def test_never_exceeds_reported_value(self):
        f = make_finding(verification_status="verified_by_direct_lookup", evidence_quality=1)
        self.assertEqual(R.cap_evidence_quality(f), 1)


class BandForFindingTests(unittest.TestCase):
    def test_hard_stop_forces_black(self):
        f = make_finding(severity=0, likelihood=0, legal_proximity=0,
                          hard_stop_id="identical_mark_identical_goods",
                          verification_status="verified_by_direct_lookup", evidence_quality=3)
        self.assertEqual(R.band_for_finding(f), "BLACK")

    def test_hard_stop_with_unverified_evidence_capped_to_red_not_green(self):
        f = make_finding(severity=0, likelihood=0, legal_proximity=0,
                          hard_stop_id="identical_mark_identical_goods",
                          verification_status="unverified", evidence_quality=0)
        band = R.band_for_finding(f)
        self.assertEqual(band, "RED")
        self.assertNotIn(band, ("GREEN", "BLACK"))

    def test_hard_stop_never_lowers_score_band(self):
        f = make_finding(severity=4, likelihood=4, legal_proximity=4,
                          hard_stop_id="unclear_rights_chain",  # only forces RED
                          verification_status="verified_by_direct_lookup", evidence_quality=3)
        self.assertEqual(R.band_for_finding(f), "BLACK")  # score alone already worse than RED

    def test_all_14_hard_stops_have_a_band(self):
        expected_ids = {
            "identical_mark_identical_goods", "famous_mark_collision", "actual_cease_and_desist",
            "near_identical_high_proximity", "company_sign_conflict", "work_title_conflict",
            "misleading_official_certification_proximity", "protected_professional_title",
            "personality_or_name_right", "protected_geographic_indication",
            "problematic_official_emblem", "ongoing_litigation", "unclear_rights_chain",
            "high_investment_under_uncertainty",
        }
        self.assertEqual(set(R.HARD_STOP_BAND.keys()), expected_ids)
        for hard_stop_id in expected_ids:
            f = make_finding(severity=0, likelihood=0, legal_proximity=0, hard_stop_id=hard_stop_id,
                              verification_status="verified_by_direct_lookup", evidence_quality=3)
            self.assertIn(R.band_for_finding(f), R.BANDS)

    def test_low_likelihood_shifts_band_down(self):
        f = make_finding(severity=2, likelihood=0, legal_proximity=2)
        f_normal = make_finding(severity=2, likelihood=2, legal_proximity=2)
        self.assertLess(R._band_index(R.band_for_finding(f)), R._band_index(R.band_for_finding(f_normal)))

    def test_high_likelihood_shifts_band_up(self):
        f = make_finding(severity=2, likelihood=4, legal_proximity=2)
        f_normal = make_finding(severity=2, likelihood=2, legal_proximity=2)
        self.assertGreater(R._band_index(R.band_for_finding(f)), R._band_index(R.band_for_finding(f_normal)))


class OverallBandTests(unittest.TestCase):
    def test_no_findings_is_green(self):
        band, dominating, reason = R.overall_band([])
        self.assertEqual(band, "GREEN")
        self.assertIsNone(dominating)

    def test_worst_of_not_averaged(self):
        clean = [make_finding(id=f"f-{i}", severity=0, likelihood=0, legal_proximity=0) for i in range(20)]
        bad = make_finding(id="f-bad", severity=4, likelihood=4, legal_proximity=4,
                            hard_stop_id="famous_mark_collision",
                            verification_status="verified_by_direct_lookup", evidence_quality=3,
                            summary="famous mark collision")
        band, dominating, reason = R.overall_band(clean + [bad])
        self.assertEqual(band, "BLACK")
        self.assertEqual(dominating, "f-bad")


class VerdictForTests(unittest.TestCase):
    def test_quick_mode_ignores_gates_entirely(self):
        gates = {"any_gate": {"value": False, "reason": "irrelevant in quick mode"}}
        verdict = R.verdict_for("BLACK", "quick", gates, [])
        self.assertEqual(verdict, "IMMEDIATE STOP")

    def test_quick_mode_never_a_green_light(self):
        gates = {}
        for band in R.BANDS:
            verdict = R.verdict_for(band, "quick", gates, [])
            self.assertIn(verdict, R.QUICK_SCAN_VERDICTS)

    def test_open_gate_forces_incomplete_not_green(self):
        gates = {"exact_search_completed": {"value": False, "reason": "1 blocked row"}}
        verdict = R.verdict_for("GREEN", "deep", gates, [])
        self.assertEqual(verdict, R.INCOMPLETE_VERDICT)

    def test_blocked_row_never_reads_as_clean(self):
        # zero findings + one blocked row -> RESULT INCOMPLETE, not PRELIMINARILY CLEAR
        gates = R.derive_gates(
            make_profile(), {"variants": [{"variant": "Zynkora"}]},
            [make_row(status="blocked", block_reason="empty_shell")], [], FULL_REDTEAM,
        )
        verdict = R.verdict_for("GREEN", "deep", gates, [make_row(status="blocked")])
        self.assertEqual(verdict, R.INCOMPLETE_VERDICT)

    def test_all_gates_pass_but_no_primary_lookup_not_preliminarily_clear(self):
        rows = [make_row(source_category="unregistered", search_type="unregistered")]
        gates = {name: {"value": True, "reason": "ok"} for name in R.REQUIRED_GATES}
        verdict = R.verdict_for("GREEN", "deep", gates, rows)
        self.assertEqual(verdict, "PROCEED WITH CONDITIONS")
        self.assertNotEqual(verdict, "PRELIMINARILY CLEAR")

    def test_all_gates_pass_with_primary_lookup_is_preliminarily_clear(self):
        rows = [make_row(source_category="registered_mark", status="completed")]
        gates = {name: {"value": True, "reason": "ok"} for name in R.REQUIRED_GATES}
        verdict = R.verdict_for("GREEN", "deep", gates, rows)
        self.assertEqual(verdict, "PRELIMINARILY CLEAR")

    def test_user_performed_row_satisfies_primary_lookup_requirement(self):
        rows = [make_row(source_category="registered_mark", status="completed", performed_by="user")]
        gates = {name: {"value": True, "reason": "ok"} for name in R.REQUIRED_GATES}
        verdict = R.verdict_for("GREEN", "deep", gates, rows)
        self.assertEqual(verdict, "PRELIMINARILY CLEAR")

    def test_cli_neutral_case_no_research_capability_never_green(self):
        # every planned row not_attempted (host had no fetch/search capability at all), zero findings
        rows = [make_row(status="not_attempted", performed_by="agent")]
        profile = make_profile()
        gates = R.derive_gates(profile, {"variants": [{"variant": "x"}]}, rows, [], {})
        verdict = R.verdict_for("GREEN", "deep", gates, rows)
        self.assertEqual(verdict, R.INCOMPLETE_VERDICT)
        self.assertNotEqual(verdict, "PRELIMINARILY CLEAR")


class DeriveGatesTests(unittest.TestCase):
    def test_all_true_on_fully_completed_clean_workdir(self):
        # Mirrors an ordinary clean deep run: DE+EU territories, one applicable
        # sector module, every planned row completed, nothing adverse found
        # anywhere (findings=[]). This must reach every gate true — if it
        # can't, PRELIMINARILY CLEAR is structurally unreachable for the good
        # case, the same deadlock shape the manual-lookup escape hatch exists
        # to prevent.
        profile = make_profile(sector_modules_applicable=["finance"])
        variants = {"variants": [{"variant": "Zynkora"}]}
        gates = R.derive_gates(profile, variants, CLEAN_ROWS, [], FULL_REDTEAM)
        for name, g in gates.items():
            with self.subTest(gate=name):
                self.assertTrue(g["value"], msg=g["reason"])

    def test_company_names_checked_does_not_require_eu_register(self):
        # There is no EU-wide company register (SOURCES.md) — only DE/AT/CH
        # need a completed row. A DE+EU profile must not be blocked on EU.
        rows = [make_row(search_type="company_name", source_category="company_register", territory="DE")]
        profile = make_profile(target_territories=["DE", "EU"])
        gates = R.derive_gates(profile, {}, rows, [], {})
        self.assertTrue(gates["company_names_checked"]["value"], msg=gates["company_names_checked"]["reason"])

    def test_absolute_grounds_checked_reads_searchlog_not_findings(self):
        # A clean absolute-grounds assessment writes no finding at all
        # (nothing adverse to report) — the gate must still close on the
        # search-log row alone.
        rows = [make_row(query="Zynqora", source_id="model-knowledge", territory="DE",
                          search_type="linguistic", source_category="linguistic",
                          cluster_id="linguistic-de", status="completed")]
        gates = R.derive_gates(make_profile(languages=["de"]), {}, rows, [], {})
        self.assertTrue(gates["absolute_grounds_checked"]["value"], msg=gates["absolute_grounds_checked"]["reason"])

    def test_absolute_grounds_finding_alone_does_not_satisfy_gate(self):
        # Regression: a finding with no matching search-log row must not
        # silently satisfy the gate — that was the pre-fix unreachable-gate bug.
        findings = [make_finding(category="absolute_ground", language="de", cluster_id="linguistic-de")]
        gates = R.derive_gates(make_profile(languages=["de"]), {}, [], findings, {})
        self.assertFalse(gates["absolute_grounds_checked"]["value"])

    def test_sector_module_with_completed_row_and_no_finding_passes_gate(self):
        profile = make_profile(sector_modules_applicable=["finance"])
        rows = [make_row(query="Zynqora", source_id="web-search-general", territory="DE",
                          search_type="sector", source_category="sector",
                          cluster_id="sector-finance", status="completed")]
        gates = R.derive_gates(profile, {}, rows, [], {})
        self.assertTrue(gates["special_sector_rules_checked"]["value"], msg=gates["special_sector_rules_checked"]["reason"])

    def test_missing_profile_field_fails_context_complete(self):
        profile = make_profile()
        del profile["goods_and_services"]
        gates = R.derive_gates(profile, {}, [], [], {})
        self.assertFalse(gates["context_complete"]["value"])

    def test_blocked_row_fails_its_gate(self):
        rows = [make_row(search_type="exact", status="blocked", block_reason="empty_shell")]
        gates = R.derive_gates(make_profile(), {"variants": [{"variant": "x"}]}, rows, [], {})
        self.assertFalse(gates["exact_search_completed"]["value"])
        self.assertIn("blocked", gates["exact_search_completed"]["reason"])

    def test_user_completed_row_passes_gate(self):
        rows = [make_row(search_type="exact", status="completed", performed_by="user")]
        gates = R.derive_gates(make_profile(), {"variants": [{"variant": "x"}]}, rows, [], {})
        self.assertTrue(gates["exact_search_completed"]["value"])

    def test_red_team_without_attacks_fails_gate(self):
        gates = R.derive_gates(make_profile(), {}, [], [], {"attacks": [], "missed_vectors": []})
        self.assertFalse(gates["red_team_completed"]["value"])

    def test_red_team_missing_rebuttal_fails_gate(self):
        redteam = {"attacks": [{"vector": "x", "severity": 1, "argument": "a", "rebuttal": ""}], "missed_vectors": []}
        gates = R.derive_gates(make_profile(), {}, [], [], redteam)
        self.assertFalse(gates["red_team_completed"]["value"])

    def test_unresolved_missed_vector_fails_gate(self):
        redteam = {
            "attacks": [{"vector": "x", "severity": 1, "argument": "a", "rebuttal": "r"}],
            "missed_vectors": [{"vector": "y", "severity": 2, "resolution": None}],
        }
        gates = R.derive_gates(make_profile(), {}, [], [], redteam)
        self.assertFalse(gates["red_team_completed"]["value"])

    def test_finding_without_evidence_fails_gate(self):
        findings = [make_finding(evidence=[])]
        gates = R.derive_gates(make_profile(), {}, [], findings, {})
        self.assertFalse(gates["evidence_review_completed"]["value"])

    def test_finding_with_register_id_but_no_url_passes_gate(self):
        findings = [make_finding(evidence=[{"register_id": "DE12345"}])]
        gates = R.derive_gates(make_profile(), {}, FULL_ROWS, findings, FULL_REDTEAM)
        self.assertTrue(gates["evidence_review_completed"]["value"])

    def test_sector_module_without_finding_or_exclusion_fails_gate(self):
        profile = make_profile(sector_modules_applicable=["finance"])
        gates = R.derive_gates(profile, {}, [], [], {})
        self.assertFalse(gates["special_sector_rules_checked"]["value"])

    def test_sector_module_excluded_with_reason_passes_gate(self):
        profile = make_profile(
            sector_modules_applicable=["finance"],
            sector_modules_not_applicable=[{"module": "finance", "reason": "not a regulated activity"}],
        )
        gates = R.derive_gates(profile, {}, [], [], {})
        self.assertTrue(gates["special_sector_rules_checked"]["value"])

    def test_limitations_disclosed_always_true(self):
        gates = R.derive_gates({}, {}, [], [], {})
        self.assertTrue(gates["limitations_disclosed"]["value"])

    def test_no_variants_fails_gate(self):
        gates = R.derive_gates(make_profile(), {"variants": []}, [], [], {})
        self.assertFalse(gates["name_variants_generated"]["value"])


if __name__ == "__main__":
    unittest.main()
