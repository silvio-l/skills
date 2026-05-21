#!/usr/bin/env python3
"""IndexNow setup wizard.

Side-effects:
* Generates a UUID-shaped key (hex, lowercase) if none exists.
* Writes `<public_dir>/<key>.txt` containing exactly the key.
* Emits a `.env`-snippet on stdout.

Idempotency:
* If both the env key and the matching key file already exist, the
  wizard is a no-op (`already_configured: True`).
* `--force` (propagated by audit.py via `force=True`) overrides:
  generates a new key and overwrites the file.

The script does not call `input()`. Confirmation happens in the agent
prose layer.
"""

from __future__ import annotations

import pathlib
import uuid
from typing import Callable, Dict, Optional

from . import urls as URLS


def _default_uuid_gen() -> str:
    return uuid.uuid4().hex.lower()


def plan(
    env: Dict,
    *,
    public_dir: Optional[pathlib.Path],
    force: bool = False,
    uuid_gen: Optional[Callable[[], str]] = None,
) -> Dict:
    """Build a structured plan dict.

    Returns:
        {
          "module": "indexnow-setup",
          "ready": bool,
          "already_configured": bool,
          "public_dir": str|None,
          "key": str,             # the key the wizard will use
          "key_file": str|None,   # absolute destination path
          "reason": str,
          "warnings": list[str],
        }
    """
    uuid_gen = uuid_gen or _default_uuid_gen
    warnings = []
    if public_dir is None:
        return {
            "module": "indexnow-setup",
            "ready": False,
            "already_configured": False,
            "public_dir": None,
            "key": "",
            "key_file": None,
            "reason": (
                "Public directory not detected. Run a build first or "
                "pass --dist so inventory.py can locate it."
            ),
            "warnings": warnings,
        }
    public = pathlib.Path(public_dir)
    existing_key = env.get("INDEXNOW_KEY") or ""

    if existing_key and not force:
        key_file = public / f"{existing_key}.txt"
        if key_file.is_file():
            actual = key_file.read_text(encoding="utf-8").strip()
            if actual == existing_key:
                return {
                    "module": "indexnow-setup",
                    "ready": True,
                    "already_configured": True,
                    "public_dir": str(public),
                    "key": existing_key,
                    "key_file": str(key_file),
                    "reason": (
                        "INDEXNOW_KEY set and key file matches. Nothing to do "
                        "(use --force to regenerate)."
                    ),
                    "warnings": warnings,
                }
            warnings.append(
                f"Key file content mismatch at {key_file}; will be overwritten."
            )

    key = existing_key if (existing_key and not force) else uuid_gen()
    key_file = public / f"{key}.txt"
    return {
        "module": "indexnow-setup",
        "ready": True,
        "already_configured": False,
        "public_dir": str(public),
        "key": key,
        "key_file": str(key_file),
        "reason": (
            f"Write {key_file} containing the key, then `export "
            f"INDEXNOW_KEY={key}` in your shell."
        ),
        "warnings": warnings,
    }


def execute(
    plan_dict: Dict,
    *,
    file_writer: Optional[Callable] = None,
) -> Dict:
    """Write the key file (unless already_configured)."""
    if not plan_dict.get("ready"):
        return {
            "module": "indexnow-setup",
            "applied": False,
            "errors": [plan_dict.get("reason", "plan not ready")],
        }
    if plan_dict.get("already_configured"):
        return {
            "module": "indexnow-setup",
            "applied": False,
            "errors": [],
            "note": "already configured",
        }
    key_file = pathlib.Path(plan_dict["key_file"])
    key = plan_dict["key"]

    def _default_writer(path: pathlib.Path, content: str) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    writer = file_writer or _default_writer
    try:
        writer(key_file, key)
    except Exception as exc:  # pragma: no cover — defensive
        return {
            "module": "indexnow-setup",
            "applied": False,
            "errors": [f"could not write {key_file}: {exc}"],
        }
    return {
        "module": "indexnow-setup",
        "applied": True,
        "errors": [],
        "key": key,
        "key_file": str(key_file),
    }


def render(plan_dict: Dict, result: Optional[Dict] = None) -> str:
    """Render the wizard output as Markdown."""
    lines = ["# `--setup indexnow` — IndexNow wizard", ""]
    if not plan_dict.get("ready"):
        lines.append(f"_{plan_dict.get('reason', 'not ready')}_")
        return "\n".join(lines) + "\n"

    if plan_dict.get("already_configured"):
        lines.append("- Status: **already configured**, no changes made.")
        lines.append(f"- Key file: `{plan_dict['key_file']}`")
        lines.append("- Run with `--force` to regenerate.")
        return "\n".join(lines) + "\n"

    lines.extend([
        f"- Generated key: `{plan_dict['key']}`",
        f"- Key file: `{plan_dict['key_file']}`",
        "",
        "## .env snippet",
        "",
        "```bash",
        f"export INDEXNOW_KEY={plan_dict['key']}",
        "```",
        "",
        f"## Docs",
        "",
        f"- IndexNow: {URLS.INDEXNOW_DOCS}",
    ])
    for w in plan_dict.get("warnings", []) or []:
        lines.append(f"- warning: {w}")
    if result and not result.get("applied") and not plan_dict.get("already_configured"):
        for err in result.get("errors") or []:
            lines.append(f"- error: {err}")
    return "\n".join(lines) + "\n"
