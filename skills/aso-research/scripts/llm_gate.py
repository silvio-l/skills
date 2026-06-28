#!/usr/bin/env python3
"""Token-Budget Gate (stage 50, slice 03).

The hard control on LLM context quality (PRD US13): the LLM-input
representation (condensed competitor profiles + score table) must stay
under a configured token limit (default ~70k of the ~100k sweet-spot
window). If it would exceed the limit, the gate auto-trims — primary lever
= condensed profiles (the weakest/least-relevant ones, i.e. the tail),
keeping the score table whole; only if profiles are exhausted does it trim
the score table.

Pure + dependency-free. Token estimation is a documented chars/4 heuristic
(no paid tokenizer dependency — honours US19 "no paid API keys" and the
repo-wide free-tier discipline). The representation is just data (dicts),
so the gate is agnostic to whether the condensed profiles came from the
H1 subagent or a fixture — fully offline-testable.

Trim order (documented): condensed-profiles tail -> score-table tail.
The representation is rebuilt (re-serialized) after each drop so the
measured token count reflects the trimmed payload.
"""

from __future__ import annotations

from typing import Dict, List, Tuple

import serialize  # stable JSON for a deterministic byte count

DEFAULT_GATE_TOKEN_LIMIT = 70_000  # PRD: ~70k of the ~100k sweet-spot window

# Representation payload keys the gate knows how to trim (in order).
_PROFILE_KEY = "condensed_profiles"
_SCORE_KEY = "score_table"


def estimate_tokens(text: str) -> int:
    """Dependency-free token estimate: ``max(1, len(text) // 4)``.

    The chars/4 heuristic is the standard rough estimate for English/German
    mixed text; good enough for a *budget* gate (we never claim it is an
    exact token count — only a stable, conservative bound).
    """
    if not text:
        return 0
    return max(1, len(text) // 4)


def measure_representation(rep: Dict) -> int:
    """Token estimate of the serialized representation (stable JSON)."""
    return estimate_tokens(serialize.dumps_json(rep))


def _with(rep: Dict, profiles: List, score: List) -> Dict:
    out = dict(rep)
    out[_PROFILE_KEY] = profiles
    out[_SCORE_KEY] = score
    return out


def apply_token_gate(rep: Dict, limit: int) -> Tuple[Dict, Dict]:
    """Measure ``rep`` and auto-trim it under ``limit``.

    Returns ``(trimmed_rep, gate_report)`` where ``gate_report`` is::

        {
          "measured_before": int, "measured_after": int, "limit": int,
          "trimmed": bool,
          "profiles_before": int, "profiles_kept": int,
          "score_rows_kept": int,
        }

    Trim order: condensed-profiles tail -> score-table tail.
    A representation already under the limit is returned unchanged with
    ``trimmed: False``.
    """
    if limit <= 0:
        limit = DEFAULT_GATE_TOKEN_LIMIT

    profiles_before = len(rep.get(_PROFILE_KEY) or [])
    profiles = list(rep.get(_PROFILE_KEY) or [])
    score = list(rep.get(_SCORE_KEY) or [])

    measured_before = measure_representation(_with(rep, profiles, score))
    current = measured_before
    trimmed = False

    def _measure() -> int:
        return measure_representation(_with(rep, profiles, score))

    # Tier 1: drop the least-relevant condensed profiles (tail) — primary lever.
    # Honours the limit as a hard control: drops down to an empty payload if a
    # pathologically small limit demands it (realistic ~70k limits never reach 0).
    while current > limit and len(profiles) > 0:
        profiles.pop()
        trimmed = True
        current = _measure()

    # Tier 2: once profiles are exhausted, trim the score table (tail).
    while current > limit and len(score) > 0:
        score.pop()
        trimmed = True
        current = _measure()

    trimmed_rep = _with(rep, profiles, score)
    gate_report = {
        "measured_before": measured_before,
        "measured_after": current,
        "limit": limit,
        "trimmed": trimmed,
        "profiles_before": profiles_before,
        "profiles_kept": len(profiles),
        "score_rows_kept": len(score),
    }
    return trimmed_rep, gate_report
