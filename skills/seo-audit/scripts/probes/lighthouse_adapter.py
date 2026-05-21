#!/usr/bin/env python3
"""Lighthouse adapter — normaliser + thin shell-out.

Shell-out: `npx lighthouse <url> --output=json --quiet`.
The shell-out is intentionally untested; the live whispaste.de smoke
command in skills/seo-audit/probes.md §Live-Smoke exercises it.

Normaliser: maps Lighthouse JSON → list[Finding-dict] (see
probes/__init__.py for the shape).
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Dict, List, Optional


# Category scores < this threshold produce a finding ("not yet good").
CATEGORY_GOOD_THRESHOLD = 0.9
# Category scores below this threshold are flagged as high severity.
CATEGORY_POOR_THRESHOLD = 0.5

# Map Lighthouse category id → seo-audit `category` and user_impact.
CATEGORY_MAP = {
    "performance":    ("performance", 3),
    "accessibility":  ("a11y",        3),
    "best-practices": ("best-practices", 2),
    "seo":            ("seo",         3),
}


def _severity_for_category_score(score: float) -> str:
    if score is None:
        return "low"
    if score < CATEGORY_POOR_THRESHOLD:
        return "high"
    if score < CATEGORY_GOOD_THRESHOLD:
        return "med"
    return "low"


def _severity_for_audit_score(score) -> str:
    if score is None:
        return "low"
    if score == 0:
        return "high"
    if score < 0.5:
        return "high"
    if score < 0.9:
        return "med"
    return "low"


def normalise(raw: Dict, url: str) -> List[Dict]:
    """Lighthouse JSON dict → list of Finding-shaped dicts."""
    findings: List[Dict] = []

    # 1. Category-level findings: every category whose score < 0.9.
    cats = (raw or {}).get("categories") or {}
    for cat_id, meta in sorted(cats.items()):
        score = meta.get("score")
        if score is None or score >= CATEGORY_GOOD_THRESHOLD:
            continue
        cat_label, impact = CATEGORY_MAP.get(cat_id, (cat_id, 2))
        findings.append({
            "category":    cat_label,
            "severity":    _severity_for_category_score(score),
            "user_impact": impact,
            "fix_effort":  3,  # category-wide work is multi-step
            "file_path":   url,
            "line_number": 0,
            "match":       f"category:{cat_id}",
            "rationale": (
                f"Lighthouse {meta.get('title', cat_id)} score: "
                f"{round(score, 2)} (target ≥ 0.9)"
            ),
            "suggested_replacement": (
                f"Open the Lighthouse report and address the highest-"
                f"impact failures in `{cat_id}`."
            ),
        })

    # 2. Audit-level findings: every audit whose score is numeric and < 0.9.
    audits = (raw or {}).get("audits") or {}
    for aid, audit in sorted(audits.items()):
        mode = audit.get("scoreDisplayMode")
        if mode in ("notApplicable", "manual", "informative"):
            continue
        score = audit.get("score")
        if score is None or score >= 0.9:
            continue
        cat_for_audit = _audit_category(aid)
        findings.append({
            "category":    cat_for_audit,
            "severity":    _severity_for_audit_score(score),
            "user_impact": 2,
            "fix_effort":  2,
            "file_path":   url,
            "line_number": 0,
            "match":       f"audit:{aid}",
            "rationale":   audit.get("title", aid),
            "suggested_replacement": audit.get("displayValue", "") or "",
        })

    return findings


def _audit_category(audit_id: str) -> str:
    """Best-effort category guess from audit-id naming convention."""
    aid = audit_id.lower()
    if aid in {
        "largest-contentful-paint", "first-contentful-paint", "speed-index",
        "interactive", "total-blocking-time", "cumulative-layout-shift",
        "render-blocking-resources", "uses-text-compression",
        "uses-responsive-images", "uses-rel-preconnect", "server-response-time",
    }:
        return "performance"
    if aid in {
        "color-contrast", "image-alt", "label", "link-name", "html-has-lang",
        "document-title", "meta-viewport", "bypass",
    }:
        return "a11y"
    if aid in {
        "meta-description", "canonical", "hreflang", "robots-txt",
        "structured-data", "is-crawlable",
    }:
        return "seo"
    return "best-practices"


# ---------------------------------------------------------------------------
# Thin shell-out (NOT unit-tested — covered by the live smoke command).
# ---------------------------------------------------------------------------

def shell_out(url: str, timeout: int = 120) -> Optional[Dict]:
    """Run `npx lighthouse <url> --output=json --quiet` and parse stdout."""
    try:
        proc = subprocess.run(
            ["npx", "--yes", "lighthouse", url,
             "--output=json", "--quiet",
             "--chrome-flags=--headless=new --no-sandbox"],
            capture_output=True, text=True, timeout=timeout,
            env=dict(os.environ),
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return None
    if proc.returncode != 0 or not proc.stdout:
        return None
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return None


def run(url: str, timeout: int = 120) -> List[Dict]:
    raw = shell_out(url, timeout=timeout)
    if raw is None:
        return []
    return normalise(raw, url=url)
