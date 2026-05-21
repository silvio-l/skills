#!/usr/bin/env python3
"""PageSpeed Insights setup wizard.

Emits a Markdown plan describing how to:

1. Create an API key in the Cloud Console.
2. Enable the PageSpeed Insights API for the project.
3. Export `PAGESPEED_API_KEY` in the shell / `.envrc`.

Side-effect: on darwin, calls `subprocess.run(["open", url])` for the
two console URLs (injected via `browser_opener`). On other platforms,
only the URLs are emitted to the plan output.
"""

from __future__ import annotations

from typing import Callable, Dict, List, Optional

from . import urls as URLS


def plan(env: Dict) -> Dict:
    has_key = bool(env.get("PAGESPEED_API_KEY"))
    return {
        "module": "pagespeed-setup",
        "ready": True,
        "already_configured": has_key,
        "console_urls": [
            URLS.PAGESPEED_API_CONSOLE,
            URLS.PAGESPEED_API_LIBRARY,
        ],
        "docs": URLS.PAGESPEED_API_DOCS,
        "env_var": "PAGESPEED_API_KEY",
        "warnings": [],
    }


def execute(
    plan_dict: Dict,
    *,
    platform: str = "linux",
    browser_opener: Optional[Callable[[str], None]] = None,
) -> Dict:
    """Open the console URLs in a browser on darwin.

    Platform string is passed in so the test stays clean (no
    monkey-patching of sys.platform). Production wiring passes
    `sys.platform`.
    """
    opened: List[str] = []
    if not plan_dict.get("ready"):
        return {"module": "pagespeed-setup", "opened": opened, "errors": []}
    if platform == "darwin" and browser_opener is not None:
        for url in plan_dict.get("console_urls", []):
            try:
                browser_opener(url)
                opened.append(url)
            except Exception as exc:  # pragma: no cover
                return {
                    "module": "pagespeed-setup",
                    "opened": opened,
                    "errors": [f"could not open {url}: {exc}"],
                }
    return {"module": "pagespeed-setup", "opened": opened, "errors": []}


def render(plan_dict: Dict, result: Optional[Dict] = None) -> str:
    lines = ["# `--setup pagespeed` — PageSpeed Insights wizard", ""]
    if plan_dict.get("already_configured"):
        lines.append("- Status: **PAGESPEED_API_KEY already set** "
                     "— wizard re-shows the console URLs for re-issuing.")
        lines.append("")
    lines.extend([
        "## Steps",
        "",
        f"1. Open the credentials console: <{URLS.PAGESPEED_API_CONSOLE}>",
        "2. Click **Create credentials → API key**.",
        f"3. Open the API library and enable the PageSpeed Insights API: "
        f"<{URLS.PAGESPEED_API_LIBRARY}>",
        "4. Copy the key into your shell:",
        "",
        "```bash",
        "export PAGESPEED_API_KEY=<your-key>",
        "```",
        "",
        f"Docs: {URLS.PAGESPEED_API_DOCS}",
        "",
    ])
    if result and result.get("opened"):
        lines.append("_Browser opened the console URLs (darwin)._")
    return "\n".join(lines) + "\n"
