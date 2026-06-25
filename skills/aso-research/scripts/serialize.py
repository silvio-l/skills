#!/usr/bin/env python3
"""Stable serialization for aso-research artefacts.

Determinism is an acceptance criterion: two runs with identical input +
warm cache must produce byte-identical ``keywords.json`` /
``competition.json``. That only holds if JSON is emitted with sorted
keys, fixed separators, no non-deterministic whitespace, and a trailing
newline. This module is the single place that contract lives.
"""

from __future__ import annotations

import json
from typing import Any

# Fixed separators (no trailing whitespace) + sorted keys + ASCII-passthrough
# for Umlauts (more diff-friendly) + indent for human review.
_SEPARATORS = (",", ": ")


def dumps_json(obj: Any) -> str:
    """Serialize ``obj`` to a stable JSON string (sorted keys, trailing newline)."""
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        indent=2,
        separators=_SEPARATORS,
    ) + "\n"


def dump_json(obj: Any, path: str) -> None:
    """Write ``obj`` to ``path`` as stable JSON (atomic-ish overwrite)."""
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(dumps_json(obj))


def dumps_yaml(mapping: dict) -> str:
    """Serialize a flat-ish mapping to a deterministic YAML-ish string.

    Hand-rolled (no PyYAML dependency) so ``run-config.yaml`` is stable
    and the dispatcher stays importable by plain ``python3``. Values are
    scalars or lists of scalars; keys emitted in sorted order.
    """
    lines = []
    for key in sorted(mapping.keys()):
        value = mapping[key]
        if value is None:
            lines.append(f"{key}: null")
        elif isinstance(value, bool):
            lines.append(f"{key}: {'true' if value else 'false'}")
        elif isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {_yaml_scalar(item)}")
        else:
            lines.append(f"{key}: {_yaml_scalar(value)}")
    return "\n".join(lines) + "\n"


def _yaml_scalar(value) -> str:
    text = str(value)
    if text == "":
        return '""'
    needs_quote = any(c in text for c in (":", "#", "'", '"', "\n", "{", "}", "[", "]", ",", "&", "*", "?", "|", ">", "@", "`", "%", "!")) or text.strip() != text
    if needs_quote:
        escaped = text.replace('"', '\\"')
        return f'"{escaped}"'
    return text
