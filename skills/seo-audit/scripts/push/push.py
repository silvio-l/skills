#!/usr/bin/env python3
"""Push module orchestrator.

`plan_all(...)` aggregates plans from the three push adapters.
`execute_all(...)` runs each adapter for which the caller passed
`confirmations[module] is True`. Modules without a confirmation entry
are skipped (no-op, "not confirmed").
`render_dry_run(plans)` returns a side-effect-free Markdown checklist
describing what *would* happen.

The agent (a future Claude Code session) is responsible for asking the
user to confirm each operation — this orchestrator does NOT prompt.
"""

from __future__ import annotations

import pathlib
from typing import Callable, Dict, List, Optional

from . import indexnow
from . import bing_webmaster
from . import llms_generator


MODULES = ("indexnow", "bing", "llms")


def plan_all(
    *,
    public_dir,
    urls: List[str],
    site_url: str,
    context_path,
    state_dir,
    env: Optional[Dict] = None,
) -> List[Dict]:
    """Return a list of plan dicts (one per module, in stable order).

    Each plan has at least `{"module": str, "ready": bool, "reason": str}`.
    """
    env = env if env is not None else {}
    plans: List[Dict] = []
    plans.append(indexnow.plan(public_dir, urls, env=env))
    plans.append(bing_webmaster.plan(
        site_url=site_url,
        urls=urls,
        state_dir=state_dir,
        env=env,
    ))
    plans.append(_llms_plan(
        context_path=context_path,
        output_dir=public_dir,
    ))
    return plans


def _llms_plan(*, context_path, output_dir) -> Dict:
    """Build a structured plan for the llms.txt generator."""
    context_path = pathlib.Path(context_path)
    output_dir = pathlib.Path(output_dir)
    ready = context_path.is_file() and output_dir.is_dir()
    return {
        "module": "llms",
        "ready": ready,
        "reason": (
            "Generate llms.txt and llms-full.txt from the domain doc."
            if ready else
            f"Context file or output dir missing: {context_path} / {output_dir}"
        ),
        "items": ["llms.txt", "llms-full.txt"],
        "context_path": str(context_path),
        "output_dir": str(output_dir),
        "warnings": [],
    }


def execute_all(
    plans: List[Dict],
    *,
    clients: Dict[str, Callable],
    confirmations: Dict[str, bool],
) -> List[Dict]:
    """Execute confirmed operations.

    `clients` maps `"indexnow"` and `"bing"` to a `(method,url,headers,body)
    -> (status,text)` callable. `llms` does not need a client.

    Each unconfirmed module returns a result with `submitted=False`.
    """
    results: List[Dict] = []
    for p in plans:
        mod = p["module"]
        confirmed = bool(confirmations.get(mod, False))
        if mod == "indexnow":
            results.append(indexnow.execute(
                p, client=clients.get("indexnow"), confirmed=confirmed,
            ))
        elif mod == "bing":
            results.append(bing_webmaster.execute(
                p, client=clients.get("bing"), confirmed=confirmed,
            ))
        elif mod == "llms":
            results.append(_execute_llms(p, confirmed=confirmed))
        else:  # pragma: no cover — defensive
            results.append({
                "module": mod,
                "submitted": False,
                "responses": [],
                "errors": [f"unknown module {mod}"],
            })
    return results


def _execute_llms(plan_dict: Dict, *, confirmed: bool) -> Dict:
    if not plan_dict.get("ready"):
        return {
            "module": "llms",
            "submitted": False,
            "responses": [],
            "errors": [plan_dict.get("reason", "plan not ready")],
        }
    if not confirmed:
        return {
            "module": "llms",
            "submitted": False,
            "responses": [],
            "errors": ["not confirmed by user"],
        }
    ctx = pathlib.Path(plan_dict["context_path"])
    out = pathlib.Path(plan_dict["output_dir"])
    errors: List[str] = []
    written: List[str] = []
    try:
        written.append(str(llms_generator.generate(ctx, out, full=False)))
    except Exception as exc:  # pragma: no cover
        errors.append(f"llms.txt generation failed: {exc}")
    try:
        written.append(str(llms_generator.generate(ctx, out, full=True)))
    except Exception as exc:  # pragma: no cover
        errors.append(f"llms-full.txt generation failed: {exc}")
    return {
        "module": "llms",
        "submitted": bool(written) and not errors,
        "responses": [{"path": p, "status": 0, "body": ""} for p in written],
        "errors": errors,
    }


def render_dry_run(plans: List[Dict]) -> str:
    """Render a Markdown checklist of planned operations. No side effects."""
    lines: List[str] = ["# seo-audit push — dry-run plan", ""]
    for p in plans:
        mod = p["module"]
        ready = p.get("ready", False)
        label = {
            "indexnow": "IndexNow URL submission",
            "bing":     "Bing Webmaster URL submission",
            "llms":     "llms.txt / llms-full.txt generation",
        }.get(mod, mod)
        lines.append(f"## {label}")
        lines.append("")
        lines.append(f"- [ ] confirm and run `{mod}` ({'ready' if ready else 'NOT READY'})")
        if p.get("reason"):
            lines.append(f"  - reason: {p['reason']}")
        if p.get("first_setup_hint"):
            lines.append(f"  - setup: {p['first_setup_hint']}")
        items = p.get("items") or []
        if items:
            lines.append(f"  - items ({len(items)}):")
            for item in items[:10]:
                lines.append(f"    - {item}")
            if len(items) > 10:
                lines.append(f"    - (+{len(items) - 10} more)")
        if p.get("warnings"):
            for w in p["warnings"]:
                lines.append(f"  - warning: {w}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
