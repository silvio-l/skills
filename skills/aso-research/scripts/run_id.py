#!/usr/bin/env python3
"""Run-identity for aso-research.

Run-ID format: ``YYYYMMDD-HHMMSS-<app-slug>`` (PRD "File layout, cache,
resumability"). The timestamp makes re-runs of the same seed produce a
*new* run directory (never clobbering), while the app-slug makes runs
diffable across ideas.

Pure logic — no I/O, no clock. The caller injects ``now`` so tests are
deterministic.
"""

from __future__ import annotations

import datetime
import re

SLUG_MAX = 40
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    """Turn a free-form app name into a URL/filesystem-safe slug.

    Lowercase, non-alphanumerics collapsed to single hyphens, leading /
    trailing hyphens stripped, truncated to :data:`SLUG_MAX`. An empty
    result (e.g. name was all punctuation) falls back to ``"app"`` so a
    run directory is always addressable.
    """
    if not name:
        return "app"
    slug = _SLUG_RE.sub("-", name.strip().lower()).strip("-")
    if not slug:
        return "app"
    return slug[:SLUG_MAX].rstrip("-")


def generate_run_id(now: datetime.datetime, app_name: str) -> str:
    """Build ``YYYYMMDD-HHMMSS-<app-slug>`` from an injected ``now``."""
    return now.strftime("%Y%m%d-%H%M%S") + "-" + slugify(app_name)
