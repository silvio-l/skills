#!/usr/bin/env python3
"""Google Search Console (GSC) setup wizard.

Emits Markdown instructions to install / authenticate the GSC MCP
server. Does not run `claude mcp call mcp__gsc__reauthenticate` itself
— that is an agent-conversational step (see SKILL.md). The script only
detects whether the CLI is reachable and the GSC server is registered,
then prints the next-step command.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from . import _mcp
from . import urls as URLS


def plan(env: Dict, *, mcp_runner: Optional[Callable] = None) -> Dict:
    mcp_status = _mcp.list_mcp_servers(mcp_runner)
    gsc_present = _mcp.has_gsc(mcp_status)
    return {
        "module": "gsc-setup",
        "ready": True,
        "cli_available": mcp_status["available"],
        "gsc_registered": gsc_present,
        "console_urls": [URLS.GSC_HOME, URLS.GSC_MCP_REPO],
        "docs": URLS.GSC_API_QUOTAS_DOCS,
        "warnings": [],
        "next_step": (
            "claude mcp call mcp__gsc__reauthenticate"
            if mcp_status["available"] and gsc_present
            else f"Install the MCP server first: {URLS.GSC_MCP_REPO}"
        ),
    }


def execute(
    plan_dict: Dict,
    *,
    platform: str = "linux",
    browser_opener: Optional[Callable[[str], None]] = None,
) -> Dict:
    opened: List[str] = []
    if platform == "darwin" and browser_opener is not None:
        # Only open the docs URLs — never auto-fire MCP calls.
        for url in plan_dict.get("console_urls", []):
            try:
                browser_opener(url)
                opened.append(url)
            except Exception as exc:  # pragma: no cover
                return {
                    "module": "gsc-setup",
                    "opened": opened,
                    "errors": [f"could not open {url}: {exc}"],
                }
    return {"module": "gsc-setup", "opened": opened, "errors": []}


def render(plan_dict: Dict, result: Optional[Dict] = None) -> str:
    lines = ["# `--setup gsc` — Google Search Console MCP wizard", ""]
    cli = plan_dict.get("cli_available")
    gsc = plan_dict.get("gsc_registered")
    lines.append(f"- claude CLI available: **{cli}**")
    lines.append(f"- GSC MCP server registered: **{gsc}**")
    lines.append("")
    lines.extend([
        "## Steps",
        "",
        f"1. Verify your GSC property in the Search Console: "
        f"<{URLS.GSC_HOME}>",
        f"2. Install the GSC MCP server: <{URLS.GSC_MCP_REPO}>",
        "3. Once installed, authenticate (the agent runs this — not the "
        "script):",
        "",
        "```bash",
        "claude mcp call mcp__gsc__reauthenticate",
        "```",
        "",
        f"Quotas / docs: {URLS.GSC_API_QUOTAS_DOCS}",
        "",
        f"_Next step: {plan_dict.get('next_step', '')}_",
        "",
    ])
    if result and result.get("opened"):
        lines.append("_Browser opened the docs URLs (darwin)._")
    return "\n".join(lines) + "\n"
