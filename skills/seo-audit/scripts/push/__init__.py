# seo-audit push package.
#
# Three opt-in push operations:
#   * indexnow      — POST URL list to IndexNow.
#   * bing_webmaster — POST per-URL to Bing Webmaster API.
#   * llms_generator — write llmstxt.org-shaped llms.txt / llms-full.txt.
#
# Each adapter exposes:
#   * `plan(...)` — pure function building a structured plan dict.
#     Returns:
#       {
#         "module": str,                 # "indexnow" | "bing" | "llms"
#         "ready":  bool,                # ready to execute
#         "reason": str,                 # skip / hint reason if not ready
#         "items":  list,                # what would be pushed/written
#         "first_setup_hint": str,       # only if not ready due to setup
#         "warnings": list[str],
#         ...module-specific keys
#       }
#   * `execute(plan, *, client, confirmed)` — performs the work if
#     `confirmed` is truthy AND `plan["ready"]`. Returns a result dict
#     with `submitted`, `responses`, `errors`.
#
# Confirmation is the agent's job (per SKILL.md), not the script's.
# No `input()` calls live in this package — the caller passes a
# pre-computed confirmations dict to `push.execute`.
#
# The real HTTP client lives in `_http.py` and is injected during tests.
