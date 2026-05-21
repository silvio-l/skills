"""Setup-Onboarding module — doctor + setup-wizards + verify.

Three modes exposed via `audit.py`:

* `--doctor`             — read-only env / file / probe inspection.
* `--setup <tool>`       — single-tool wizard (indexnow / pagespeed / bing / gsc).
* `--verify`             — one minimal probe call per configured tool.

All operations are dependency-injection-friendly so unit tests stay
fully offline. Real HTTP / shell access lives in `_http.py` and
`_mcp.py`. URL constants live in `urls.py`.
"""
