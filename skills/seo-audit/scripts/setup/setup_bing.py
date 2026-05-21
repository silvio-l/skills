#!/usr/bin/env python3
"""Bing Webmaster Tools setup wizard.

Emits a Markdown plan describing site verification + API-key fetch.
Optionally opens the Bing Webmaster home on darwin.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from . import urls as URLS


def plan(env: Dict) -> Dict:
    has_key = bool(env.get("BING_WEBMASTER_API_KEY"))
    return {
        "module": "bing-setup",
        "ready": True,
        "already_configured": has_key,
        "console_urls": [URLS.BING_WEBMASTER_HOME],
        "docs": URLS.BING_WEBMASTER_API_DOCS,
        "env_var": "BING_WEBMASTER_API_KEY",
        "warnings": [],
    }


def execute(
    plan_dict: Dict,
    *,
    platform: str = "linux",
    browser_opener: Optional[Callable[[str], None]] = None,
) -> Dict:
    opened: List[str] = []
    if platform == "darwin" and browser_opener is not None:
        for url in plan_dict.get("console_urls", []):
            try:
                browser_opener(url)
                opened.append(url)
            except Exception as exc:  # pragma: no cover
                return {
                    "module": "bing-setup",
                    "opened": opened,
                    "errors": [f"could not open {url}: {exc}"],
                }
    return {"module": "bing-setup", "opened": opened, "errors": []}


def render(plan_dict: Dict, result: Optional[Dict] = None) -> str:
    lines = ["# `--setup bing` — Bing Webmaster wizard", ""]
    if plan_dict.get("already_configured"):
        lines.append("- Status: **BING_WEBMASTER_API_KEY already set** "
                     "— wizard re-shows the console URLs.")
        lines.append("")
    lines.extend([
        "## Steps",
        "",
        f"1. Open Bing Webmaster Tools: <{URLS.BING_WEBMASTER_HOME}>",
        "2. Add your site and verify ownership "
        "(HTML meta-tag or XML key file).",
        "3. Go to **Settings → API access** and copy the API key.",
        "4. Export it in your shell:",
        "",
        "```bash",
        "export BING_WEBMASTER_API_KEY=<your-key>",
        "```",
        "",
        "5. If the site is verified, raise the daily limit:",
        "",
        "```bash",
        "export BING_DAILY_LIMIT=10000",
        "```",
        "",
        f"Docs: {URLS.BING_WEBMASTER_API_DOCS}",
        "",
    ])
    if result and result.get("opened"):
        lines.append("_Browser opened the Webmaster console (darwin)._")
    return "\n".join(lines) + "\n"
