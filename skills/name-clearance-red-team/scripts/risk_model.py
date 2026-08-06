"""
Pure risk-model module for name-clearance-red-team. No filesystem, no
network, no argparse — every function here takes already-loaded dicts/lists
and returns a value. check_gates.py and render_report.py are the only
callers; both import this module rather than reimplementing any of it.

Normative source: RISK-MODEL.md. Keep this file and that document in sync —
if you change a threshold or a hard-stop mapping here, update the doc too.
"""

BANDS = ["GREEN", "YELLOW", "ORANGE", "RED", "BLACK"]

BAND_TO_VERDICT = {
    "GREEN": "PRELIMINARILY CLEAR",
    "YELLOW": "PROCEED WITH CONDITIONS",
    "ORANGE": "MODIFY BEFORE USE",
    "RED": "LAWYER CLEARANCE REQUIRED",
    "BLACK": "DO NOT USE",
}

QUICK_SCAN_VERDICTS = ("GO TO DEEP CHECK", "RENAME LIKELY", "IMMEDIATE STOP")

INCOMPLETE_VERDICT = "RESULT INCOMPLETE – NO RELEASE RECOMMENDATION POSSIBLE"

# The 14 §11 hard stops. The three most severe force BLACK outright; the
# other eleven force at least RED regardless of the finding's own axis
# scores — a hard stop overrides the score-based band, never the reverse.
HARD_STOP_BAND = {
    "identical_mark_identical_goods": "BLACK",
    "famous_mark_collision": "BLACK",
    "actual_cease_and_desist": "BLACK",
    "near_identical_high_proximity": "RED",
    "company_sign_conflict": "RED",
    "work_title_conflict": "RED",
    "misleading_official_certification_proximity": "RED",
    "protected_professional_title": "RED",
    "personality_or_name_right": "RED",
    "protected_geographic_indication": "RED",
    "problematic_official_emblem": "RED",
    "ongoing_litigation": "RED",
    "unclear_rights_chain": "RED",
    "high_investment_under_uncertainty": "RED",
}

# max_allowed evidence_quality per verification_status. cap_evidence_quality
# never trusts what a finding reports for itself — a claim with no traceable
# source can raise a risk band (a suspicious but unverified hit still gets
# investigated) but must never count as evidence that clears the name.
_EVIDENCE_CAP = {
    "unverified": 0,
    "reported_by_search_snippet": 1,
    "verified_by_direct_lookup": 3,
}

_GATE_SEARCH_TYPES = {
    "exact_search_completed": "exact",
    "similarity_search_completed": "similarity",
    "unregistered_rights_checked": "unregistered",
}

# Territories SOURCES.md lists an actual company register for. There is no
# EU-wide company register, so "EU" is deliberately absent — company_names_checked
# only demands a completed row for territories where one genuinely exists.
_TERRITORIES_WITH_COMPANY_REGISTER = {"DE", "AT", "CH"}

REQUIRED_GATES = (
    "context_complete",
    "territories_defined",
    "goods_services_defined",
    "name_variants_generated",
    "exact_search_completed",
    "similarity_search_completed",
    "unregistered_rights_checked",
    "company_names_checked",
    "absolute_grounds_checked",
    "special_sector_rules_checked",
    "red_team_completed",
    "evidence_review_completed",
    "limitations_disclosed",
)


def _band_index(band):
    return BANDS.index(band)


def _max_band(*bands):
    return BANDS[max(_band_index(b) for b in bands)]


def cap_evidence_quality(finding):
    reported = finding.get("evidence_quality", 0)
    status = finding.get("verification_status", "unverified")
    cap = _EVIDENCE_CAP.get(status, 0)
    return min(reported, cap)


def _score_band(finding):
    base = max(finding.get("severity", 0), finding.get("legal_proximity", 0))
    likelihood = finding.get("likelihood", 0)
    if likelihood <= 1:
        index = max(base - 1, 0)
    elif likelihood == 4:
        index = min(base + 1, 4)
    else:
        index = base
    return BANDS[index]


def band_for_finding(finding):
    """Score-based band, hard-stop override, evidence-quality floor for BLACK."""
    score_band = _score_band(finding)
    hard_stop_id = finding.get("hard_stop_id")
    band = score_band
    if hard_stop_id:
        band = _max_band(score_band, HARD_STOP_BAND.get(hard_stop_id, "GREEN"))
    if band == "BLACK" and cap_evidence_quality(finding) < 2:
        band = "RED"
    return band


def overall_band(findings):
    """Worst-of across all findings, never averaged. Empty findings -> GREEN."""
    if not findings:
        return "GREEN", None, "no adverse findings recorded"
    worst_band = "GREEN"
    dominating = None
    for finding in findings:
        band = band_for_finding(finding)
        if _band_index(band) > _band_index(worst_band):
            worst_band = band
            dominating = finding
    if dominating is None:
        # All findings landed on GREEN — still report the first as reference.
        dominating = findings[0]
    reason = dominating.get("summary", "")
    return worst_band, dominating.get("id"), reason


def _has_primary_register_lookup(searchlog_rows):
    return any(
        row.get("source_category") == "registered_mark" and row.get("status") == "completed"
        for row in searchlog_rows
    )


def verdict_for(band, mode, gates, searchlog_rows):
    """The only place a verdict string is produced. No model writes this directly."""
    if mode == "quick":
        if band in ("BLACK", "RED"):
            return "IMMEDIATE STOP"
        if band == "ORANGE":
            return "RENAME LIKELY"
        return "GO TO DEEP CHECK"

    if any(not g["value"] for g in gates.values()):
        return INCOMPLETE_VERDICT

    effective_band = band
    if band == "GREEN" and not _has_primary_register_lookup(searchlog_rows):
        effective_band = "YELLOW"
    return BAND_TO_VERDICT[effective_band]


def _rows_of_type(searchlog_rows, search_type):
    return [r for r in searchlog_rows if r.get("search_type") == search_type]


def _gate_all_completed(searchlog_rows, search_type):
    rows = _rows_of_type(searchlog_rows, search_type)
    if not rows:
        return False, f"no '{search_type}' rows were planned — the search plan is incomplete"
    incomplete = [r for r in rows if r.get("status") != "completed"]
    if incomplete:
        reasons = ", ".join(sorted({r.get("status", "?") for r in incomplete}))
        return False, f"{len(incomplete)}/{len(rows)} '{search_type}' rows are not completed ({reasons})"
    return True, f"all {len(rows)} '{search_type}' rows completed"


def derive_gates(profile, variants, searchlog_rows, findings, redteam):
    """Every gate computed from artifacts on disk. No gate is ever a stored boolean."""
    gates = {}

    missing = [
        f for f in ("name", "name_type", "goods_and_services", "target_territories", "planned_use", "prior_events")
        if not profile.get(f)
    ]
    gates["context_complete"] = {
        "value": not missing,
        "reason": "intake complete" if not missing else f"missing profile fields: {', '.join(missing)}",
    }

    territories = profile.get("target_territories") or []
    gates["territories_defined"] = {
        "value": bool(territories),
        "reason": f"{len(territories)} territories" if territories else "no target_territories set",
    }

    goods = profile.get("goods_and_services") or []
    gates["goods_services_defined"] = {
        "value": bool(goods),
        "reason": f"{len(goods)} entries" if goods else "goods_and_services is empty",
    }

    variant_list = (variants or {}).get("variants") or []
    gates["name_variants_generated"] = {
        "value": bool(variant_list),
        "reason": f"{len(variant_list)} variants" if variant_list else "no variants generated",
    }

    for gate_name, search_type in _GATE_SEARCH_TYPES.items():
        ok, reason = _gate_all_completed(searchlog_rows, search_type)
        gates[gate_name] = {"value": ok, "reason": reason}

    # Only territories SOURCES.md actually lists a company register for are required —
    # the EU has no EU-wide company register, so a DE+EU run must not be blocked on it.
    territories_with_register = [t for t in territories if t in _TERRITORIES_WITH_COMPANY_REGISTER]
    company_missing = [
        t for t in territories_with_register
        if not any(
            r.get("source_category") == "company_register" and r.get("status") == "completed" and r.get("territory") == t
            for r in searchlog_rows
        )
    ]
    gates["company_names_checked"] = {
        "value": not company_missing,
        "reason": "company register checked for every target territory that has one (SOURCES.md: DE/AT/CH)" if not company_missing
        else f"no completed company-register row for: {', '.join(company_missing)}",
    }

    # These two read the search log, not findings — a clean check produces zero findings
    # by design (see ORCHESTRATION.md rule 2), so requiring a finding to close the gate
    # would make it unreachable for the ordinary, adverse-free case.
    languages = profile.get("languages") or ["de"]
    lang_missing = [
        lang for lang in languages
        if not any(
            r.get("status") == "completed" and r.get("cluster_id") == f"linguistic-{lang}"
            for r in searchlog_rows
        )
    ]
    gates["absolute_grounds_checked"] = {
        "value": not lang_missing,
        "reason": "absolute grounds checked for every target language" if not lang_missing
        else f"no completed linguistic-cluster row for: {', '.join(lang_missing)}",
    }

    applicable = profile.get("sector_modules_applicable") or []
    not_applicable = {e.get("module") for e in (profile.get("sector_modules_not_applicable") or [])}
    sector_missing = [
        m for m in applicable
        if m not in not_applicable and not any(
            r.get("status") == "completed" and r.get("cluster_id") == f"sector-{m}"
            for r in searchlog_rows
        )
    ]
    gates["special_sector_rules_checked"] = {
        "value": not sector_missing,
        "reason": "every applicable sector module resolved" if not sector_missing
        else f"unresolved sector modules: {', '.join(sector_missing)}",
    }

    redteam = redteam or {}
    attacks = redteam.get("attacks") or []
    missed = redteam.get("missed_vectors") or []
    redteam_problems = []
    if not attacks:
        redteam_problems.append("no attacks recorded")
    if any(not a.get("rebuttal") for a in attacks):
        redteam_problems.append("an attack is missing its rebuttal")
    if any(v.get("resolution") is None for v in missed):
        redteam_problems.append("a missed_vector has no resolution")
    gates["red_team_completed"] = {
        "value": not redteam_problems,
        "reason": "red team pass complete" if not redteam_problems else "; ".join(redteam_problems),
    }

    evidence_problems = [
        f.get("id", "?") for f in findings
        if not f.get("evidence") or not any(e.get("url") or e.get("register_id") for e in f.get("evidence", []))
    ]
    gates["evidence_review_completed"] = {
        "value": not evidence_problems,
        "reason": "every finding has traceable evidence" if not evidence_problems
        else f"findings without a url/register_id: {', '.join(evidence_problems)}",
    }

    gates["limitations_disclosed"] = {
        "value": True,
        "reason": "the renderer always emits the limitations/coverage sections",
    }

    return gates
