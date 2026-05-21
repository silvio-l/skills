#!/usr/bin/env python3
"""Doctor mode — read-only diagnostic for the seven check areas.

Pure functions, fully dependency-injected. No global `os.environ` reads,
no global `subprocess` calls. The dispatcher in `audit.py` wires up the
real runners; tests inject fakes.

Check areas (deterministic section order, per AC4):

1. npx tools         — npx version, lighthouse, pa11y
2. IndexNow          — env + key-file presence + content match
3. PageSpeed         — env + optional ping
4. Bing Webmaster    — env + optional ping
5. GSC MCP           — claude mcp list contains mcp__gsc__*
6. Domain file       — CONTEXT.md / CLAUDE.md / README.md + anti-vocabulary table
7. public/-path      — exists and is writable

Status icons:
* "✓" — ready
* "⚠" — partial / fallback present
* "✗" — missing / unconfigured

Output:
* `run(env, *, runners)` → DoctorReport dict.
* `render(report)` → deterministic Markdown string.
"""

from __future__ import annotations

import os
import pathlib
import re
from typing import Callable, Dict, List, Optional

from . import _mcp
from . import urls as URLS


SECTION_ORDER = (
    "npx",
    "indexnow",
    "pagespeed",
    "bing",
    "gsc",
    "domain",
    "public",
)

SECTION_TITLES = {
    "npx":        "npx tools (npx / lighthouse / pa11y)",
    "indexnow":   "IndexNow (env + key file)",
    "pagespeed":  "PageSpeed Insights (env + optional ping)",
    "bing":       "Bing Webmaster (env + optional ping)",
    "gsc":        "GSC MCP (claude mcp list)",
    "domain":     "Domain file (CONTEXT.md / CLAUDE.md / README.md)",
    "public":     "public/-path (writable check)",
}

ICON_OK = "✓"
ICON_WARN = "⚠"
ICON_MISSING = "✗"

ANTI_VOCAB_HEADER = re.compile(
    r"\|\s*Begriff\s*\|\s*Stattdessen\s*\|\s*Grund\s*\|",
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# Per-area inspectors. Each returns:
#   {"area": str, "icon": str, "rows": list[(str, str)], "summary": str}
# `rows` is a list of (label, value) pairs rendered as a Markdown table.
# ---------------------------------------------------------------------------


def _default_npx_runner(argv) -> Dict:  # pragma: no cover — live only
    import subprocess
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=10)
        return {"returncode": proc.returncode,
                "stdout": proc.stdout or "",
                "stderr": proc.stderr or ""}
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return {"returncode": 127, "stdout": "", "stderr": "not found"}


def check_npx(runner: Optional[Callable] = None) -> Dict:
    run = runner or _default_npx_runner
    rows: List = []
    icons: List[str] = []

    for label, argv in (
        ("npx --version", ["npx", "--version"]),
        ("lighthouse --version", ["npx", "lighthouse", "--version"]),
        ("pa11y --version", ["npx", "pa11y", "--version"]),
    ):
        result = run(argv)
        if result.get("returncode") == 0 and result.get("stdout", "").strip():
            rows.append((label, result["stdout"].strip().splitlines()[0]))
            icons.append(ICON_OK)
        else:
            rows.append((label, f"{ICON_MISSING} missing"))
            icons.append(ICON_MISSING)

    if all(i == ICON_OK for i in icons):
        icon = ICON_OK
        summary = "Node toolchain ready."
    elif any(i == ICON_OK for i in icons):
        icon = ICON_WARN
        summary = f"Some npx tools missing; install Node ≥ 20 ({URLS.NODE_DOWNLOAD})."
    else:
        icon = ICON_MISSING
        summary = (
            f"No npx tooling reachable. Install Node ≥ 20: {URLS.NODE_DOWNLOAD}"
        )
    return {"area": "npx", "icon": icon, "rows": rows, "summary": summary}


def check_indexnow(env: Dict, public_dir: Optional[pathlib.Path]) -> Dict:
    key = env.get("INDEXNOW_KEY") or ""
    rows: List = [("INDEXNOW_KEY env",
                   f"{ICON_OK} set" if key else f"{ICON_MISSING} not set")]

    if not key:
        rows.append(("Key file", f"{ICON_MISSING} no key to look up"))
        return {
            "area": "indexnow",
            "icon": ICON_MISSING,
            "rows": rows,
            "summary": (
                f"INDEXNOW_KEY not set. Run `--setup indexnow` to generate "
                f"a key and write the key file. Docs: {URLS.INDEXNOW_DOCS}"
            ),
        }

    if public_dir is None:
        rows.append(("Key file", f"{ICON_WARN} public-dir unknown"))
        return {
            "area": "indexnow",
            "icon": ICON_WARN,
            "rows": rows,
            "summary": (
                "INDEXNOW_KEY set but public-dir could not be detected. "
                "Pass --root with a built site or check inventory."
            ),
        }

    key_file = pathlib.Path(public_dir) / f"{key}.txt"
    if not key_file.is_file():
        rows.append(("Key file", f"{ICON_MISSING} missing at {key_file}"))
        return {
            "area": "indexnow",
            "icon": ICON_MISSING,
            "rows": rows,
            "summary": (
                f"Key file missing. Run `--setup indexnow` to write "
                f"{key_file}."
            ),
        }
    actual = key_file.read_text(encoding="utf-8").strip()
    if actual != key:
        rows.append(("Key file content", f"{ICON_MISSING} mismatch with env"))
        return {
            "area": "indexnow",
            "icon": ICON_MISSING,
            "rows": rows,
            "summary": (
                f"Key file content does not match $INDEXNOW_KEY. Re-run "
                f"`--setup indexnow --force` to align."
            ),
        }
    rows.append(("Key file", f"{ICON_OK} present and matches env"))
    return {
        "area": "indexnow",
        "icon": ICON_OK,
        "rows": rows,
        "summary": "IndexNow ready.",
    }


def check_pagespeed(
    env: Dict,
    pinger: Optional[Callable] = None,
) -> Dict:
    key = env.get("PAGESPEED_API_KEY") or ""
    rows: List = [("PAGESPEED_API_KEY env",
                   f"{ICON_OK} set" if key else f"{ICON_MISSING} not set")]
    if not key:
        return {
            "area": "pagespeed",
            "icon": ICON_MISSING,
            "rows": rows,
            "summary": (
                f"PAGESPEED_API_KEY not set. Run `--setup pagespeed` for the "
                f"wizard. Console: {URLS.PAGESPEED_API_CONSOLE}"
            ),
        }
    if pinger is None:
        rows.append(("Probe call", f"{ICON_WARN} skipped (no probe in doctor)"))
        return {
            "area": "pagespeed",
            "icon": ICON_OK,
            "rows": rows,
            "summary": "PageSpeed key set. Run `--verify` for a live ping.",
        }
    status = pinger(key)
    icon = ICON_OK if 200 <= status < 300 else ICON_WARN if status else ICON_MISSING
    rows.append(("Probe call", f"{icon} HTTP {status}"))
    return {
        "area": "pagespeed",
        "icon": icon,
        "rows": rows,
        "summary": "PageSpeed reachable." if icon == ICON_OK
        else "PageSpeed key set but probe returned an error.",
    }


def check_bing(
    env: Dict,
    pinger: Optional[Callable] = None,
) -> Dict:
    key = env.get("BING_WEBMASTER_API_KEY") or ""
    rows: List = [("BING_WEBMASTER_API_KEY env",
                   f"{ICON_OK} set" if key else f"{ICON_MISSING} not set")]
    if not key:
        return {
            "area": "bing",
            "icon": ICON_MISSING,
            "rows": rows,
            "summary": (
                f"BING_WEBMASTER_API_KEY not set. Run `--setup bing` "
                f"for the wizard. Console: {URLS.BING_WEBMASTER_HOME}"
            ),
        }
    if pinger is None:
        rows.append(("Probe call", f"{ICON_WARN} skipped (no probe in doctor)"))
        return {
            "area": "bing",
            "icon": ICON_OK,
            "rows": rows,
            "summary": "Bing key set. Run `--verify` for a live ping.",
        }
    status = pinger(key)
    icon = ICON_OK if 200 <= status < 300 else ICON_WARN if status else ICON_MISSING
    rows.append(("Probe call", f"{icon} HTTP {status}"))
    return {
        "area": "bing",
        "icon": icon,
        "rows": rows,
        "summary": "Bing reachable." if icon == ICON_OK
        else "Bing key set but probe returned an error.",
    }


def check_gsc(runner: Optional[Callable] = None) -> Dict:
    result = _mcp.list_mcp_servers(runner)
    rows: List = []
    if not result["available"]:
        rows.append(("claude CLI", f"{ICON_MISSING} {result.get('reason', 'unavailable')}"))
        return {
            "area": "gsc",
            "icon": ICON_MISSING,
            "rows": rows,
            "summary": (
                f"`claude mcp list` not available. Install the MCP server: "
                f"{URLS.GSC_MCP_REPO}"
            ),
        }
    rows.append(("claude mcp list",
                 f"{ICON_OK} ran ({len(result['servers'])} servers)"))
    if _mcp.has_gsc(result):
        rows.append(("mcp__gsc__* tools", f"{ICON_OK} present"))
        icon = ICON_OK
        summary = "GSC MCP installed."
    else:
        rows.append(("mcp__gsc__* tools", f"{ICON_MISSING} not registered"))
        icon = ICON_MISSING
        summary = (
            f"GSC MCP server not registered. Setup repo: {URLS.GSC_MCP_REPO}"
        )
    return {"area": "gsc", "icon": icon, "rows": rows, "summary": summary}


def check_domain_doc(root: pathlib.Path) -> Dict:
    root = pathlib.Path(root)
    candidates = ("CONTEXT.md", "CLAUDE.md", "README.md")
    rows: List = []
    found: Optional[pathlib.Path] = None
    for name in candidates:
        p = root / name
        if p.is_file():
            found = p
            rows.append((name, f"{ICON_OK} present"))
            break
        rows.append((name, f"{ICON_MISSING} missing"))
    if not found:
        return {
            "area": "domain",
            "icon": ICON_MISSING,
            "rows": rows,
            "summary": (
                "No domain doc found. Create CONTEXT.md with an "
                "Anti-Vokabular table (`Begriff | Stattdessen | Grund`)."
            ),
        }
    text = found.read_text(encoding="utf-8", errors="replace")
    if ANTI_VOCAB_HEADER.search(text):
        rows.append(("Anti-Vokabular-Tabelle", f"{ICON_OK} found in {found.name}"))
        return {
            "area": "domain",
            "icon": ICON_OK,
            "rows": rows,
            "summary": f"Domain doc {found.name} has an Anti-Vokabular table.",
        }
    rows.append(("Anti-Vokabular-Tabelle", f"{ICON_WARN} not in {found.name}"))
    return {
        "area": "domain",
        "icon": ICON_WARN,
        "rows": rows,
        "summary": (
            f"{found.name} present but contains no `Begriff | Stattdessen | "
            f"Grund` table — brand-scan will report no glossary."
        ),
    }


def check_public(public_dir: Optional[pathlib.Path]) -> Dict:
    rows: List = []
    if public_dir is None:
        rows.append(("Detected public/", f"{ICON_MISSING} unknown"))
        return {
            "area": "public",
            "icon": ICON_MISSING,
            "rows": rows,
            "summary": "Public directory not detected. Build the site first.",
        }
    p = pathlib.Path(public_dir)
    rows.append(("Detected public/", f"{ICON_OK} {p}"))
    if not p.is_dir():
        rows.append(("Exists", f"{ICON_MISSING} no"))
        return {
            "area": "public",
            "icon": ICON_MISSING,
            "rows": rows,
            "summary": f"Public dir {p} does not exist. Run the build.",
        }
    rows.append(("Exists", f"{ICON_OK} yes"))
    writable = os.access(str(p), os.W_OK)
    rows.append(("Writable", f"{ICON_OK} yes" if writable else f"{ICON_MISSING} no"))
    if writable:
        return {
            "area": "public",
            "icon": ICON_OK,
            "rows": rows,
            "summary": f"Public dir {p} is writable.",
        }
    return {
        "area": "public",
        "icon": ICON_WARN,
        "rows": rows,
        "summary": f"Public dir {p} is not writable — push outputs will fail.",
    }


# ---------------------------------------------------------------------------
# Orchestrator + renderer.
# ---------------------------------------------------------------------------


def run(
    env: Optional[Dict] = None,
    *,
    root: Optional[pathlib.Path] = None,
    public_dir: Optional[pathlib.Path] = None,
    runners: Optional[Dict[str, Callable]] = None,
) -> Dict:
    """Build a DoctorReport dict over all seven check areas.

    `runners` is a dict of injectable callables:
      * "npx"        — argv → {returncode, stdout, stderr}
      * "mcp"        — argv → {returncode, stdout, stderr}
      * "pagespeed_ping" — key → http_status_int (optional)
      * "bing_ping"      — key → http_status_int (optional)
    """
    env = env if env is not None else {}
    runners = runners or {}
    sections: List[Dict] = []
    sections.append(check_npx(runners.get("npx")))
    sections.append(check_indexnow(env, public_dir))
    sections.append(check_pagespeed(env, runners.get("pagespeed_ping")))
    sections.append(check_bing(env, runners.get("bing_ping")))
    sections.append(check_gsc(runners.get("mcp")))
    sections.append(check_domain_doc(root or pathlib.Path(".")))
    sections.append(check_public(public_dir))

    top_fix_first = [s["area"] for s in sections if s["icon"] == ICON_MISSING]
    return {
        "sections": sections,
        "top_fix_first": top_fix_first,
        "section_order": list(SECTION_ORDER),
    }


def render(report: Dict) -> str:
    """Render the DoctorReport as deterministic Markdown."""
    out: List[str] = ["# seo-audit doctor", ""]
    if report["top_fix_first"]:
        out.append("## Top fix-first")
        out.append("")
        for area in report["top_fix_first"]:
            title = SECTION_TITLES.get(area, area)
            out.append(f"- {ICON_MISSING} {title}")
        out.append("")
    else:
        out.append("_Nothing missing — onboarding complete._")
        out.append("")

    for section in report["sections"]:
        title = SECTION_TITLES.get(section["area"], section["area"])
        out.append(f"### {section['icon']} {title}")
        out.append("")
        out.append("| Check | Status |")
        out.append("| ----- | ------ |")
        for label, value in section["rows"]:
            out.append(f"| {label} | {value} |")
        out.append("")
        out.append(f"_{section['summary']}_")
        out.append("")
    return "\n".join(out).rstrip() + "\n"
