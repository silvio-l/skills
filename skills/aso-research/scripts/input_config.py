#!/usr/bin/env python3
"""Structured-input parsing + validation for aso-research.

The pipeline never free-text-guesses. The orchestrator derives a
structured input (YAML/JSON) *before* the pipeline runs; this module
turns that raw mapping into a validated, defaulted :data:`RunConfig`.

RunConfig keys (echoed verbatim into ``run-config.yaml``):

    app_name          str   required
    description       str   required
    category          str   category guess (default ``"other"``)
    country           str   ISO store country (default ``"de"``)
    language          str   listing language (default ``"de"``)
    own_app_id        str   optional — Modus A self-audit reference
    seed_keywords     list  optional 3–5 seed terms (capped at 5)
    gate_token_limit  int   optional LLM token-budget gate override
    output_dir        str   optional run-output root

YAML support is optional: if PyYAML is importable, ``.yaml``/``.yml``
files parse through it; otherwise the loader rejects YAML with a clear
message and still accepts JSON. This keeps the pure-logic tests
dependency-free (they exercise :func:`parse_input` / :func:`validate`
directly with dicts).
"""

from __future__ import annotations

import json
import os
from typing import List

MAX_SEED_KEYWORDS = 5

CANONICAL_KEYS = (
    "app_name",
    "description",
    "category",
    "country",
    "language",
    "own_app_id",
    "seed_keywords",
    "gate_token_limit",
    "output_dir",
)


def validate(raw: dict) -> List[str]:
    """Return a list of human-readable validation errors (empty = valid)."""
    errors: List[str] = []
    if not isinstance(raw, dict):
        return ["input must be a mapping/object"]

    app_name = raw.get("app_name")
    if not isinstance(app_name, str) or not app_name.strip():
        errors.append("app_name is required and must be a non-empty string")

    description = raw.get("description")
    if not isinstance(description, str) or not description.strip():
        errors.append("description is required and must be a non-empty string")

    country = raw.get("country", "de")
    if not isinstance(country, str) or not country.strip():
        errors.append("country must be a non-empty string")

    language = raw.get("language", "de")
    if not isinstance(language, str) or not language.strip():
        errors.append("language must be a non-empty string")

    seeds = raw.get("seed_keywords")
    if seeds is not None:
        if not isinstance(seeds, list):
            errors.append("seed_keywords must be a list of strings")
        elif not all(isinstance(s, str) and s.strip() for s in seeds):
            errors.append("seed_keywords must contain only non-empty strings")

    own = raw.get("own_app_id")
    if own is not None and not (isinstance(own, str) and own.strip()):
        errors.append("own_app_id must be a non-empty string when present")

    gtl = raw.get("gate_token_limit")
    if gtl is not None and not isinstance(gtl, int):
        errors.append("gate_token_limit must be an integer when present")

    out = raw.get("output_dir")
    if out is not None and not (isinstance(out, str) and out.strip()):
        errors.append("output_dir must be a non-empty string when present")

    return errors


def parse_input(raw: dict) -> dict:
    """Validate ``raw`` and return a defaulted RunConfig dict.

    Raises ``ValueError`` listing every error when the input is invalid.
    """
    errors = validate(raw)
    if errors:
        raise ValueError("invalid aso-research input:\n  - " + "\n  - ".join(errors))

    seeds = raw.get("seed_keywords") or []
    seeds = [s.strip() for s in seeds if isinstance(s, str) and s.strip()]
    if len(seeds) > MAX_SEED_KEYWORDS:
        seeds = seeds[:MAX_SEED_KEYWORDS]

    config = {
        "app_name": raw["app_name"].strip(),
        "description": raw["description"].strip(),
        "category": (raw.get("category") or "other").strip() or "other",
        "country": (raw.get("country") or "de").strip(),
        "language": (raw.get("language") or "de").strip(),
        "own_app_id": (raw["own_app_id"].strip() if raw.get("own_app_id") else None),
        "seed_keywords": seeds,
        "gate_token_limit": raw.get("gate_token_limit"),
        "output_dir": (raw["output_dir"].strip() if raw.get("output_dir") else None),
    }
    return config


def load_input_file(path: str) -> dict:
    """Load a structured input file (JSON always; YAML when PyYAML present).

    Returns the raw mapping; pass it through :func:`parse_input` to
    validate + default. Raises ``FileNotFoundError`` / ``ValueError`` on
    problems.
    """
    if not os.path.isfile(path):
        raise FileNotFoundError(f"input file not found: {path}")
    with open(path, "r", encoding="utf-8") as fh:
        text = fh.read()
    lower = path.lower()
    if lower.endswith(".json"):
        return json.loads(text)
    if lower.endswith((".yaml", ".yml")):
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ValueError(
                "YAML input requires PyYAML (run via 'uv run' or 'pip install pyyaml')"
            ) from exc
        loaded = yaml.safe_load(text)
        return loaded if loaded is not None else {}
    # Unknown extension: try JSON, then YAML as a tolerant fallback.
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore
        except ImportError as exc:
            raise ValueError(f"could not parse input file (not JSON): {path}") from exc
        loaded = yaml.safe_load(text)
        return loaded if loaded is not None else {}
