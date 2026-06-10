#!/usr/bin/env python3
"""Deterministic slop scorer for humanize-text skill — slice 05.

Input:  text (str) + findings list (canonical 8-key dicts from slop_scanner)
Output: score dict with five dimensions (each 1–10), overall score (sum,
        max 50), verdict ('pass'/'needs-revision'), and gating metadata.

Standalone CLI for debugging:
    python3 slop_scorer.py <text_file> <findings_json> [--threshold N]

Exit codes (standalone CLI and humanize.py --mode score):
    0  → pass
    1  → needs-revision

Scoring formulas (deterministic, no LLM calls):
──────────────────────────────────────────────
  word_count = max(len(text.split()), 1)
  findings_per_100 = len(findings) / word_count * 100

  Directness  (1–10):
    Counts tier-1 findings. Each tier-1 finding deducts 1 point.
    raw = 10 - count_tier1
    clamped to [1, 10].

  Rhythm      (1–10):
    Sentence-length burstiness: coefficient of variation of word-counts
    per sentence. cv = stdev(lens) / mean(lens) for sentences with ≥2 words.
    Mapped: cv=0 → score 1 (uniform = boring); cv≥0.8 → score 10.
    score = clamp(1 + cv / 0.8 * 9, 1, 10).
    Single sentence (or no sentences): score = 5 (neutral).
    rhythm_neutral=True (fragment files, e.g. i18n .ts): held at NEUTRAL_RHYTHM
    (5.5) — concatenated independent UI strings have meaningless burstiness, so
    they are neither rewarded with a free 10 nor punished.

  Trust       (1–10):
    Trust = deduction for hedging/filler phrases (tier-2 structure findings).
    raw = 10 - count_tier2
    clamped to [1, 10].

  Authenticity (1–10):
    Deduction for tier-1 and tier-2 findings, each weighted at 0.5. Tier-3
    tells (em-dash density, tricolon) are weak density-only signals and carry
    NO linear penalty — they only drive tier3_density_hint.
    Concretely: raw = 10 - (count_tier1 * 0.5 + count_tier2 * 0.5)
    clamped to [1, 10].

  Density     (1–10):
    Two components:
      - tier-1/tier-2 findings density per 100 words: −0.5 per unit.
      - em-dash DENSITY (soft frequency check): once em-dashes per 100 prose
        words cross EM_DASH_DENSITY_FLOOR, −EM_DASH_PENALTY_SLOPE per unit,
        capped at EM_DASH_PENALTY_CAP. A single em-dash costs nothing; a text
        peppered with them is dragged down (2026 research: it is a frequency
        tell, not a per-occurrence one).
    raw = 10 - findings_per_100 * 0.5 - em_dash_penalty
    clamped to [1, 10].

  Scoring runs over PROSE only — short UI labels (i18n nav strings) are excluded
  by the caller (humanize.py via slop_scanner.extract_prose_text) so a slop-dense
  paragraph is not diluted by dozens of one-word labels.

  Overall = sum of five dimensions (max 50).
  Default threshold = 37 (pass if overall ≥ threshold).

Tier-gating (apply_tier_gating):
─────────────────────────────────
  Tier-1: always surfaced.
  Tier-2: only surfaced when "clustered" = ≥3 tier-2 findings within any
          10-line window (sliding window over sorted line_numbers).
  Tier-3: never surfaced individually. Instead emits tier3_density_hint=True
          when count_tier3 / word_count * 100 ≥ 3.0 (≥3 per 100 words).
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_THRESHOLD: float = 37.0   # pass if overall >= threshold (out of 50)
TIER2_CLUSTER_SIZE: int = 3        # ≥N tier-2 findings in a window = cluster
TIER2_CLUSTER_WINDOW: int = 10     # line-window for tier-2 clustering
TIER3_DENSITY_THRESHOLD: float = 3.0  # tier-3 per 100 words → hint

# Em-dash density (soft frequency check). A handful of intentional em-dashes is
# free; above the floor the Density dimension is penalised proportionally.
EM_DASH_DENSITY_FLOOR: float = 1.0   # em-dashes per 100 prose words tolerated
EM_DASH_PENALTY_SLOPE: float = 1.2   # points deducted per unit above the floor
EM_DASH_PENALTY_CAP: float = 5.0     # max points em-dash density can remove

# Rhythm value used when sentence burstiness is not measurable (fragment files).
NEUTRAL_RHYTHM: float = 5.5

# High-confidence structural tells that are ALWAYS surfaced, bypassing the
# tier-2 cluster gate (the cluster gate is for the softer neg-parallelism only).
ALWAYS_SURFACE_IDS: frozenset = frozenset(
    ["struct_anaphora", "struct_adj_tricolon"]
)

# ---------------------------------------------------------------------------
# Sentence splitting (stdlib, no external deps)
# ---------------------------------------------------------------------------

# Sentence-ending punctuation: . ! ? followed by whitespace or end-of-string
_SENTENCE_END_RE = re.compile(r"[.!?]+(?:\s+|$)")


def _split_sentences(text: str) -> List[str]:
    """Split text into sentences by . ! ? terminators.

    Returns a list of non-empty stripped strings.
    """
    parts = _SENTENCE_END_RE.split(text)
    return [p.strip() for p in parts if p.strip()]


def _word_count(text: str) -> int:
    """Return number of whitespace-separated tokens in *text*."""
    return len(text.split())


# ---------------------------------------------------------------------------
# Dimension formulas
# ---------------------------------------------------------------------------

def _score_directness(findings: List[Dict]) -> float:
    """Directness: deduct 1 per tier-1 finding, floor at 1."""
    count_t1 = sum(1 for f in findings if f.get("tier") == 1)
    return max(1.0, 10.0 - count_t1)


def _score_rhythm(text: str) -> float:
    """Rhythm (burstiness): coefficient of variation of sentence word-counts.

    cv = 0  (uniform) → score 1
    cv ≥ 0.8 (varied)  → score 10
    Single sentence     → score 5 (neutral)
    """
    sentences = _split_sentences(text)
    lens = [_word_count(s) for s in sentences if _word_count(s) >= 1]
    if len(lens) < 2:
        return 5.0
    mean = sum(lens) / len(lens)
    if mean == 0:
        return 5.0
    variance = sum((x - mean) ** 2 for x in lens) / len(lens)
    stdev = math.sqrt(variance)
    cv = stdev / mean
    raw = 1.0 + (cv / 0.8) * 9.0
    return min(10.0, max(1.0, raw))


def _score_trust(findings: List[Dict]) -> float:
    """Trust: deduct 1 per tier-2 finding, floor at 1."""
    count_t2 = sum(1 for f in findings if f.get("tier") == 2)
    return max(1.0, 10.0 - count_t2)


def _score_authenticity(findings: List[Dict]) -> float:
    """Authenticity: tier-1 at 0.5 + tier-2 at 0.5. Tier-3 does NOT deduct.

    Tier-1 and tier-2 are primary style issues already captured by
    Directness and Trust; weight them at 0.5 so no single tier dominates
    the Authenticity dimension.

    Tier-3 tells (em-dash density, tricolon) are deliberately weak,
    density-only signals — 2026 research shows a single em-dash proves
    nothing and humans use them intentionally. They therefore carry NO
    linear score penalty; their only effect is the tier3_density_hint
    raised by apply_tier_gating when density crosses the threshold.
    """
    count_t1 = sum(1 for f in findings if f.get("tier") == 1)
    count_t2 = sum(1 for f in findings if f.get("tier") == 2)
    raw = 10.0 - (count_t1 * 0.5 + count_t2 * 0.5)
    return max(1.0, min(10.0, raw))


def _em_dash_penalty(findings: List[Dict], word_count: int) -> float:
    """Soft frequency penalty for em-dash DENSITY (not per-occurrence).

    Counts em-dash occurrences (pattern_id punct_em_dash) per 100 prose words.
    Below EM_DASH_DENSITY_FLOOR: no penalty (intentional em-dashes are free).
    Above it: EM_DASH_PENALTY_SLOPE points per unit, capped at EM_DASH_PENALTY_CAP.
    This is the 'soft' check 2026 research calls for — a single em-dash proves
    nothing, but a text peppered with them is dragged down.
    """
    wc = max(word_count, 1)
    em_count = sum(1 for f in findings if f.get("pattern_id") == "punct_em_dash")
    per_100 = em_count / wc * 100.0
    excess = max(0.0, per_100 - EM_DASH_DENSITY_FLOOR)
    return min(EM_DASH_PENALTY_CAP, excess * EM_DASH_PENALTY_SLOPE)


def _score_density(findings: List[Dict], word_count: int) -> float:
    """Density: tier-1/tier-2 findings per 100 words, plus em-dash frequency.

    Two components:
      - Lexical/structural findings (tier-1 + tier-2) per 100 words, −0.5 each.
      - Em-dash DENSITY penalty (soft frequency check, see _em_dash_penalty).
    Generic tricolon (tier-3 struct) is still excluded; em-dash is the only
    tier-3 signal that now moves the score, and only via density, never per hit.
    """
    wc = max(word_count, 1)
    scoring = [f for f in findings if f.get("tier") in (1, 2)]
    per_100 = len(scoring) / wc * 100.0
    raw = 10.0 - per_100 * 0.5 - _em_dash_penalty(findings, wc)
    return max(1.0, min(10.0, raw))


# ---------------------------------------------------------------------------
# Tier gating
# ---------------------------------------------------------------------------

def apply_tier_gating(
    findings: List[Dict],
    word_count: int,
) -> Dict:
    """Apply tier-gating rules and return surfaced findings + density hint.

    Rules:
    - Tier-1: always surfaced.
    - Tier-2: surfaced only when ≥TIER2_CLUSTER_SIZE tier-2 findings exist
              within any TIER2_CLUSTER_WINDOW consecutive lines.
    - Tier-3: never surfaced individually; tier3_density_hint=True when
              count_tier3 / word_count * 100 >= TIER3_DENSITY_THRESHOLD.

    Parameters
    ----------
    findings:
        List of canonical finding dicts.
    word_count:
        Number of words in the scanned text.

    Returns
    -------
    {
      'surfaced_findings': [...],   # subset to show to the user
      'tier3_density_hint': bool,   # True when tier-3 density is significant
    }
    """
    tier1 = [f for f in findings if f.get("tier") == 1]
    tier2 = [f for f in findings if f.get("tier") == 2]
    tier3 = [f for f in findings if f.get("tier") == 3]

    # Tier-2 cluster detection: sliding window over sorted line numbers
    tier2_surfaced: List[Dict] = []
    if len(tier2) >= TIER2_CLUSTER_SIZE:
        # Sort by line_number for window scan
        sorted_t2 = sorted(tier2, key=lambda f: f.get("line_number", 0))
        line_nums = [f.get("line_number", 0) for f in sorted_t2]

        # Mark which tier-2 findings are in a cluster
        in_cluster = [False] * len(sorted_t2)
        for i in range(len(line_nums)):
            # Count how many tier-2 findings fall within [line_nums[i],
            # line_nums[i] + TIER2_CLUSTER_WINDOW]
            window_end = line_nums[i] + TIER2_CLUSTER_WINDOW
            count_in_window = sum(
                1 for ln in line_nums if line_nums[i] <= ln <= window_end
            )
            if count_in_window >= TIER2_CLUSTER_SIZE:
                # Mark all findings in this window as in_cluster
                for j in range(len(line_nums)):
                    if line_nums[i] <= line_nums[j] <= window_end:
                        in_cluster[j] = True

        tier2_surfaced = [f for f, flag in zip(sorted_t2, in_cluster) if flag]

    # High-confidence structural tells (anaphora, adjective tricolon) are ALWAYS
    # surfaced regardless of clustering — the cluster gate is only for the softer
    # negative-parallelism tier-2 signal.
    always = [f for f in tier2 if f.get("pattern_id") in ALWAYS_SURFACE_IDS]
    seen = {id(f) for f in tier2_surfaced}
    tier2_surfaced.extend(f for f in always if id(f) not in seen)

    # Tier-3 density hint
    wc = max(word_count, 1)
    tier3_density = len(tier3) / wc * 100.0
    tier3_hint = tier3_density >= TIER3_DENSITY_THRESHOLD

    surfaced = tier1 + tier2_surfaced
    # Re-sort surfaced by (file_path, line_number, pattern_id)
    surfaced.sort(
        key=lambda f: (
            f.get("file_path", ""),
            f.get("line_number", 0),
            f.get("pattern_id", ""),
        )
    )

    return {
        "surfaced_findings": surfaced,
        "tier3_density_hint": tier3_hint,
    }


# ---------------------------------------------------------------------------
# Public scoring API
# ---------------------------------------------------------------------------

def score(
    text: str,
    findings: List[Dict],
    threshold: float = DEFAULT_THRESHOLD,
    rhythm_neutral: bool = False,
) -> Dict:
    """Compute a deterministic quality score for *text* given *findings*.

    Parameters
    ----------
    text:
        Raw text content (used for Rhythm/Density calculations).
    findings:
        List of canonical finding dicts (from slop_scanner).
    threshold:
        Minimum overall score to pass (default 35 / 50).

    Returns
    -------
    {
      'dimensions': {
          'directness':    float,  # 1–10
          'rhythm':        float,  # 1–10
          'trust':         float,  # 1–10
          'authenticity':  float,  # 1–10
          'density':       float,  # 1–10
      },
      'overall':   float,    # sum of dimensions, 5–50
      'verdict':   str,      # 'pass' | 'needs-revision'
    }
    """
    wc = max(_word_count(text), 1)

    directness = _score_directness(findings)
    # Fragment-derived text (i18n/data .ts: many independent short strings) yields
    # an artificially high sentence-length variance — concatenated UI strings are
    # not flowing prose, so their "burstiness" is meaningless. In that case rhythm
    # is held NEUTRAL (neither rewarded nor punished) instead of handed a free 10.
    rhythm = NEUTRAL_RHYTHM if rhythm_neutral else _score_rhythm(text)
    trust = _score_trust(findings)
    authenticity = _score_authenticity(findings)
    density = _score_density(findings, wc)

    overall = directness + rhythm + trust + authenticity + density
    # Clamp overall to [5, 50]
    overall = max(5.0, min(50.0, overall))

    verdict = "pass" if overall >= threshold else "needs-revision"

    return {
        "dimensions": {
            "directness": round(directness, 2),
            "rhythm": round(rhythm, 2),
            "trust": round(trust, 2),
            "authenticity": round(authenticity, 2),
            "density": round(density, 2),
        },
        "overall": round(overall, 2),
        "verdict": verdict,
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]

    parser = argparse.ArgumentParser(
        prog="slop_scorer.py",
        description=(
            "Deterministic slop scorer. "
            "Input: text file + findings JSON. "
            "Exit 0 = pass, Exit 1 = needs-revision."
        ),
    )
    parser.add_argument("text_file", help="Path to the text file to score.")
    parser.add_argument(
        "findings_file",
        help="Path to a JSON file containing the findings array.",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=DEFAULT_THRESHOLD,
        help=f"Minimum overall score to pass (default: {DEFAULT_THRESHOLD}).",
    )

    try:
        args = parser.parse_args(argv)
    except SystemExit as e:
        return int(e.code) if e.code is not None else 1

    text_path = Path(args.text_file)
    if not text_path.is_file():
        print(f"Error: text file not found: {text_path}", file=sys.stderr)
        return 2

    findings_path = Path(args.findings_file)
    if not findings_path.is_file():
        print(f"Error: findings file not found: {findings_path}", file=sys.stderr)
        return 2

    with open(text_path, encoding="utf-8", errors="replace") as f:
        text = f.read()

    with open(findings_path, encoding="utf-8") as f:
        raw = json.load(f)

    # Accept both envelope format {language, findings} and plain array
    if isinstance(raw, dict) and "findings" in raw:
        findings = raw["findings"]
    elif isinstance(raw, list):
        findings = raw
    else:
        print("Error: findings JSON must be a list or {language, findings} object.",
              file=sys.stderr)
        return 2

    result = score(text, findings, threshold=args.threshold)
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=False))

    return 0 if result["verdict"] == "pass" else 1


if __name__ == "__main__":
    sys.exit(main())
