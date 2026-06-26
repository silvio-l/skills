#!/usr/bin/env python3
"""H2 Cross-Checker — deterministic contradiction rubric + listing
char-count validation (slice 03).

H2 (Cross-Checker, Haiku) is a *quality gate*, not a rubber stamp (PRD US17,
DoD criterion 10). To make "it demonstrably rejects a contradicting
recommendation" verifiable **offline** (without an LLM), the contradiction
logic lives here as a pure function: given an S2 listing + the score table,
flag every recommended keyword that contradicts the evidence. The H2
subagent applies this rubric **plus** catches semantic contradictions at
runtime — but the rubric alone proves the gate is non-trivial.

A recommended keyword is a **contradiction** when any of:

* it is **absent** from the scored set — but only for the hidden **Keyword
  Field**, which is an explicit comma-separated keyword list (an absent term
  there means the strategist invented a keyword with no evidence); for the
  Title / Subtitle prose slots an unscored word is just branding, not a
  contradiction, or
* its **Opportunity < OPPORTUNITY_MIN** (a low-opportunity term contradicts
  "recommend high-opportunity keywords"), or
* its **Competition > COMPETITION_MAX** (a high-competition term contradicts
  "low-competition targets").

The Title/Subtitle checks still catch a scored-but-contradicting term (e.g.
recommending a high-competition word in the title), so the gate stays
non-trivial across every slot.

If any contradiction is found the listing is ``rejected``; otherwise ``ok``.

Keyword extraction from a slot's text reuses the project tokenizer
(:func:`extract.tokenize`) so "term" matching is consistent with the score
table. Apple slot model + char limits (PRD): Title 30 / Subtitle 30 /
hidden Keyword Field 100.
"""

from __future__ import annotations

from typing import Dict, List

# Documented thresholds — the boundaries the rubric enforces.
OPPORTUNITY_MIN = 20   # recommended kw should clear this opportunity floor
COMPETITION_MAX = 70   # recommended kw should stay under this competition ceiling

# Apple slot model (PRD). S2 emits Apple slots here.
APPLE_SLOTS: Dict[str, int] = {
    "title": 30,
    "subtitle": 30,
    "keyword_field": 100,
}

# Play slot model (PRD + slice 04): Title 30 · Short Description 80 · Long
# Description 4000. Play has no hidden Keyword Field, so no slot is an
# explicit keyword list — every Play slot is prose (an unscored word is
# branding, not a contradiction).
PLAY_SLOTS: Dict[str, int] = {
    "title": 30,
    "short": 80,
    "long": 4000,
}

# Slots whose recommended text is an *explicit keyword list* — every term
# there must be evidence-backed (present in the score table). Apple's hidden
# Keyword Field is the only such slot; Play has none (per-store model).
APPLE_REQUIRE_SCORED_SLOTS = {"keyword_field"}
PLAY_REQUIRE_SCORED_SLOTS: set = set()


def _slot_limits(store: str) -> Dict[str, int]:
    return PLAY_SLOTS if store == "play" else APPLE_SLOTS


def _require_scored_slots(store: str) -> set:
    return PLAY_REQUIRE_SCORED_SLOTS if store == "play" else APPLE_REQUIRE_SCORED_SLOTS


def _score_index(score_table: List[Dict]) -> Dict[str, Dict]:
    return {str(k.get("term")): k for k in (score_table or []) if k.get("term")}


def _slot_keywords(text: str) -> List[str]:
    """Tokenise a slot's text into score-table-comparable terms."""
    import extract  # type: ignore

    return extract.tokenize(text or "")


def _check_term(term: str, index: Dict[str, Dict], *, opp_min: int, comp_max: int) -> List[str]:
    """Return contradiction reasons for a *scored* ``term`` (empty = clean).

    Caller guarantees ``term`` is present in ``index`` (absence is handled in
    :func:`crosscheck_listing`, scoped to the Keyword Field).
    """
    row = index[term]
    reasons: List[str] = []
    opp = int(row.get("opportunity", 0))
    comp = int(row.get("competition", 0))
    if opp < opp_min:
        reasons.append(f"opportunity {opp} < {opp_min}")
    if comp > comp_max:
        reasons.append(f"competition {comp} > {comp_max}")
    return reasons


def crosscheck_listing(
    listing: Dict,
    score_table: List[Dict],
    *,
    opp_min: int = OPPORTUNITY_MIN,
    comp_max: int = COMPETITION_MAX,
) -> Dict:
    """Apply the contradiction rubric to an S2 listing recommendation.

    ``listing`` is the S2 output schema (Apple or Play)::

        {"store": "apple"|"play",
         "slots": [{"slot": <name>,
                    "recommended": {"text": "..."},
                    "alternatives": [{"text": "..."}, {"text": "..."}]}]}

    Every token of the recommended text (and alternatives) is checked
    against the score table. Returns::

        {"status": "ok"|"rejected",
         "findings": [{"slot", "source", "keyword", "reasons": [...], "severity"}],
         "note": str}

    ``status`` is ``rejected`` as soon as one high-opportunity/low-competition
    contradiction (or an unscored term in an explicit keyword-list slot) is
    found. The set of slots that require evidence-backed terms is per-store
    (Apple: the hidden Keyword Field; Play: none — all prose).
    """
    store = listing.get("store", "apple")
    require_scored = _require_scored_slots(store)
    index = _score_index(score_table)
    findings: List[Dict] = []

    for slot in listing.get("slots", []):
        slot_name = slot.get("slot", "?")
        # Only explicit keyword-list slots (Apple's Keyword Field) demand an
        # evidence-backed term; Title/Subtitle/Short/Long are prose, so an
        # unscored word is branding, not a contradiction. The gate validates
        # the single *recommended* entry (the decision the user acts on).
        require_scored_slot = slot_name in require_scored
        rec = slot.get("recommended") or {}
        text = rec.get("text", "")
        seen: set = set()
        for term in _slot_keywords(text):
            if term in seen:
                continue
            seen.add(term)
            if term not in index:
                if require_scored_slot:
                    findings.append(
                        {
                            "slot": slot_name,
                            "source": "recommended",
                            "keyword": term,
                            "reasons": [
                                f"unscored term '{term}' not present in the "
                                f"score table (Keyword Field must be "
                                f"evidence-backed)"
                            ],
                            "severity": "contradiction",
                        }
                    )
                continue
            reasons = _check_term(term, index, opp_min=opp_min, comp_max=comp_max)
            if reasons:
                findings.append(
                    {
                        "slot": slot_name,
                        "source": "recommended",
                        "keyword": term,
                        "reasons": reasons,
                        "severity": "contradiction",
                    }
                )

    rejected = bool(findings)
    return {
        "status": "rejected" if rejected else "ok",
        "findings": findings,
        "note": (
            f"{len(findings)} contradiction(s) against the score table "
            f"(opp_min={opp_min}, comp_max={comp_max}); recommendation rejected."
            if rejected
            else f"every recommended keyword is evidence-conform "
            f"(opp_min={opp_min}, comp_max={comp_max})."
        ),
    }


def validate_listing(listing: Dict) -> Dict:
    """Verify each slot's recommended + alternative text fits its limit.

    Routes by ``listing["store"]`` so the per-store char limits apply: Apple
    (Title 30 / Subtitle 30 / Keyword Field 100) or Play (Title 30 / Short 80
    / Long 4000). Checks the ``char_count`` field equals ``len(text)``
    (accurate) and the text length is within the slot's limit. Returns::

        {"valid": bool,
         "store": "apple"|"play",
         "slots": [{"slot", "limit",
                    "recommended": {"text", "char_count", "fits", "accurate"},
                    "alternatives": [ {same fields} ]}]}
    """
    store = listing.get("store", "apple")
    limits = _slot_limits(store)
    slots_out: List[Dict] = []
    valid = True
    for slot in listing.get("slots", []):
        name = slot.get("slot", "")
        limit = limits.get(name, 0)
        slot_out = {"slot": name, "limit": limit}
        entries = [("recommended", slot.get("recommended", {}))]
        for alt in slot.get("alternatives", []):
            entries.append(("alternative", alt))
        rendered: List[Dict] = []
        for _kind, entry in entries:
            entry = entry or {}
            text = entry.get("text", "")
            actual = len(text)
            reported = entry.get("char_count")
            fits = actual <= limit
            accurate = reported == actual
            if not (fits and accurate):
                valid = False
            rendered.append(
                {"text": text, "char_count": actual, "fits": fits, "accurate": accurate}
            )
        slot_out["recommended"] = rendered[0]
        slot_out["alternatives"] = rendered[1:]
        slots_out.append(slot_out)
    return {"valid": valid, "store": store, "slots": slots_out}
