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

  Trust       (1–10):
    Trust = deduction for hedging/filler phrases (tier-2 structure findings).
    raw = 10 - count_tier2
    clamped to [1, 10].

  Authenticity (1–10):
    Deduction for all findings weighted by tier: tier-1 at 0.5, tier-2 at 0.5,
    tier-3+ at 1.0. This ensures that no tier penalises authenticity more than
    the primary tier-1 directness signal.
    Concretely: raw = 10 - (count_tier1 * 0.5 + count_tier2 * 0.5 + count_other * 1.0)
    clamped to [1, 10].

  Density     (1–10):
    Findings density per 100 words.
    raw = 10 - findings_per_100 * 0.5
    clamped to [1, 10].

  Overall = sum of five dimensions (max 50).
  Default threshold = 35 (pass if overall ≥ threshold).

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

DEFAULT_THRESHOLD: float = 35.0   # pass if overall >= threshold (out of 50)
TIER2_CLUSTER_SIZE: int = 3        # ≥N tier-2 findings in a window = cluster
TIER2_CLUSTER_WINDOW: int = 10     # line-window for tier-2 clustering
TIER3_DENSITY_THRESHOLD: float = 3.0  # tier-3 per 100 words → hint

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
    """Authenticity: tier-1 at 0.5 + tier-2 at 0.5 + tier-3+ at 1.0.

    Tier-1 and tier-2 are primary style issues already captured by
    Directness and Trust; weight them at 0.5 so no single tier
    dominates the Authenticity dimension.
    """
    count_t1 = sum(1 for f in findings if f.get("tier") == 1)
    count_t2 = sum(1 for f in findings if f.get("tier") == 2)
    count_other = sum(1 for f in findings if f.get("tier") not in (1, 2))
    raw = 10.0 - (count_t1 * 0.5 + count_t2 * 0.5 + count_other * 1.0)
    return max(1.0, min(10.0, raw))


def _score_density(findings: List[Dict], word_count: int) -> float:
    """Density: findings per 100 words; each unit deducts 0.5 points."""
    wc = max(word_count, 1)
    per_100 = len(findings) / wc * 100.0
    raw = 10.0 - per_100 * 0.5
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
    rhythm = _score_rhythm(text)
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
