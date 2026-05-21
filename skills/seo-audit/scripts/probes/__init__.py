# seo-audit external-probes package.
#
# Each adapter exposes:
#   * a thin shell-out (NOT unit-tested — covered by the live whispaste.de
#     smoke command documented in skills/seo-audit/probes.md §Live-Smoke).
#   * a `normalise(raw) -> list[dict]` function that turns the raw tool
#     output into Finding-shaped dicts. THIS is what the unit tests
#     exercise against the frozen fixtures under
#     `tests/seo-audit/fixtures/probes/<adapter>/`.
#
# `Finding` shape (compatible with synthesis.synthesize input):
#   {
#     "category":     str,             # e.g. "performance", "a11y", "html", …
#     "severity":     "high"|"med"|"low",
#     "user_impact":  int (1..3),
#     "fix_effort":   int (>=1),
#     "file_path":    str,             # for probes: a URL or "<probe>:<key>"
#     "line_number":  int,
#     "match":        str,             # short identifier (audit id / rule)
#     "rationale":    str,             # human-readable explanation
#     "suggested_replacement": str,    # optional fix hint
#   }
#
# `score` is filled in by synthesis.synthesize — adapters must NOT set it.
