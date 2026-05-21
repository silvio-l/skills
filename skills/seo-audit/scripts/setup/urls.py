#!/usr/bin/env python3
"""Versioned URL registry for the setup-onboarding module.

Every console-, docs-, MCP-repo- and API-endpoint URL referenced by
the setup wizards lives here as a module-level constant. When an
upstream restructures its console, exactly one file changes.

Invariants enforced by tests (`tests/seo-audit/test_setup_urls.py`):

* Every constant matches `^https://` (no http, no scheme-less).
* No trailing or leading whitespace.
* Consistent trailing-slash policy: API endpoints end without a slash,
  console homes that historically carry a trailing slash keep it.
* Snapshot test asserts the name→URL mapping byte-for-byte against a
  frozen expected — URL changes surface as deliberate test edits.

Free-tier reminder: every URL here points at a free-tier-eligible
service. No paid endpoints.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# PageSpeed Insights
# ---------------------------------------------------------------------------

PAGESPEED_API_CONSOLE = "https://console.cloud.google.com/apis/credentials"
PAGESPEED_API_LIBRARY = (
    "https://console.cloud.google.com/apis/library/pagespeedonline.googleapis.com"
)
PAGESPEED_API_DOCS = (
    "https://developers.google.com/speed/docs/insights/v5/get-started"
)
PAGESPEED_API_ENDPOINT = (
    "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
)


# ---------------------------------------------------------------------------
# Bing Webmaster Tools
# ---------------------------------------------------------------------------

BING_WEBMASTER_HOME = "https://www.bing.com/webmasters/"
BING_WEBMASTER_API_DOCS = (
    "https://learn.microsoft.com/en-us/bingwebmaster/getting-access"
)
BING_WEBMASTER_API_ENDPOINT = (
    "https://ssw.live.com/webmaster/api.svc/json/GetUrlInfo"
)


# ---------------------------------------------------------------------------
# Google Search Console (via MCP)
# ---------------------------------------------------------------------------

GSC_HOME = "https://search.google.com/search-console"
GSC_MCP_REPO = "https://github.com/ahonn/mcp-server-gsc"
GSC_API_QUOTAS_DOCS = (
    "https://developers.google.com/webmaster-tools/limits"
)


# ---------------------------------------------------------------------------
# IndexNow
# ---------------------------------------------------------------------------

INDEXNOW_DOCS = "https://www.indexnow.org/documentation"
INDEXNOW_ENDPOINT = "https://api.indexnow.org/IndexNow"


# ---------------------------------------------------------------------------
# Node / npx tooling
# ---------------------------------------------------------------------------

NODE_DOWNLOAD = "https://nodejs.org/en/download"
LIGHTHOUSE_DOCS = "https://github.com/GoogleChrome/lighthouse"
PA11Y_DOCS = "https://github.com/pa11y/pa11y"


# ---------------------------------------------------------------------------
# Snapshot — single source of truth for the registry test.
# Edit this map together with the constant above; the test enforces parity.
# ---------------------------------------------------------------------------

SNAPSHOT = {
    "BING_WEBMASTER_API_DOCS": BING_WEBMASTER_API_DOCS,
    "BING_WEBMASTER_API_ENDPOINT": BING_WEBMASTER_API_ENDPOINT,
    "BING_WEBMASTER_HOME": BING_WEBMASTER_HOME,
    "GSC_API_QUOTAS_DOCS": GSC_API_QUOTAS_DOCS,
    "GSC_HOME": GSC_HOME,
    "GSC_MCP_REPO": GSC_MCP_REPO,
    "INDEXNOW_DOCS": INDEXNOW_DOCS,
    "INDEXNOW_ENDPOINT": INDEXNOW_ENDPOINT,
    "LIGHTHOUSE_DOCS": LIGHTHOUSE_DOCS,
    "NODE_DOWNLOAD": NODE_DOWNLOAD,
    "PA11Y_DOCS": PA11Y_DOCS,
    "PAGESPEED_API_CONSOLE": PAGESPEED_API_CONSOLE,
    "PAGESPEED_API_DOCS": PAGESPEED_API_DOCS,
    "PAGESPEED_API_ENDPOINT": PAGESPEED_API_ENDPOINT,
    "PAGESPEED_API_LIBRARY": PAGESPEED_API_LIBRARY,
}
