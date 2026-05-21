#!/usr/bin/env python3
"""URL-registry invariants and snapshot.

A URL change in the registry surfaces here as a deliberate test edit,
so reviewers see exactly which console the upstream restructured.
"""

import pathlib
import re
import sys
import unittest

sys.dont_write_bytecode = True

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "skills" / "seo-audit" / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

from setup import urls as URLS  # noqa: E402


HTTPS_PREFIX = re.compile(r"^https://")
WHITESPACE = re.compile(r"\s")


class Invariants(unittest.TestCase):
    def test_snapshot_is_non_empty(self):
        self.assertTrue(URLS.SNAPSHOT)

    def test_every_constant_is_https(self):
        for name, value in URLS.SNAPSHOT.items():
            with self.subTest(name=name):
                self.assertRegex(
                    value, HTTPS_PREFIX,
                    msg=f"{name} must be https:// (got {value!r})",
                )

    def test_no_whitespace_inside_urls(self):
        for name, value in URLS.SNAPSHOT.items():
            with self.subTest(name=name):
                self.assertIsNone(
                    WHITESPACE.search(value),
                    msg=f"{name} contains whitespace: {value!r}",
                )

    def test_no_trailing_or_leading_whitespace(self):
        for name, value in URLS.SNAPSHOT.items():
            with self.subTest(name=name):
                self.assertEqual(value, value.strip(),
                                 msg=f"{name} has surrounding whitespace")

    def test_api_endpoints_have_no_trailing_slash(self):
        # API endpoints that get a path/query appended must not double-slash.
        for name in ("PAGESPEED_API_ENDPOINT",
                     "BING_WEBMASTER_API_ENDPOINT",
                     "INDEXNOW_ENDPOINT"):
            with self.subTest(name=name):
                value = URLS.SNAPSHOT[name]
                self.assertFalse(value.endswith("/"),
                                 msg=f"{name} should not end in '/'")

    def test_snapshot_matches_module_constants(self):
        # Every key in SNAPSHOT must equal the module-level constant.
        for name, value in URLS.SNAPSHOT.items():
            with self.subTest(name=name):
                self.assertEqual(getattr(URLS, name), value,
                                 msg=f"{name} drifted from module constant")


class Snapshot(unittest.TestCase):
    """Frozen expected — edit alongside any deliberate URL change."""

    EXPECTED = {
        "BING_WEBMASTER_API_DOCS":
            "https://learn.microsoft.com/en-us/bingwebmaster/getting-access",
        "BING_WEBMASTER_API_ENDPOINT":
            "https://ssw.live.com/webmaster/api.svc/json/GetUrlInfo",
        "BING_WEBMASTER_HOME":
            "https://www.bing.com/webmasters/",
        "GSC_API_QUOTAS_DOCS":
            "https://developers.google.com/webmaster-tools/limits",
        "GSC_HOME":
            "https://search.google.com/search-console",
        "GSC_MCP_REPO":
            "https://github.com/ahonn/mcp-server-gsc",
        "INDEXNOW_DOCS":
            "https://www.indexnow.org/documentation",
        "INDEXNOW_ENDPOINT":
            "https://api.indexnow.org/IndexNow",
        "LIGHTHOUSE_DOCS":
            "https://github.com/GoogleChrome/lighthouse",
        "NODE_DOWNLOAD":
            "https://nodejs.org/en/download",
        "PA11Y_DOCS":
            "https://github.com/pa11y/pa11y",
        "PAGESPEED_API_CONSOLE":
            "https://console.cloud.google.com/apis/credentials",
        "PAGESPEED_API_DOCS":
            "https://developers.google.com/speed/docs/insights/v5/get-started",
        "PAGESPEED_API_ENDPOINT":
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed",
        "PAGESPEED_API_LIBRARY":
            "https://console.cloud.google.com/apis/library/"
            "pagespeedonline.googleapis.com",
    }

    def test_snapshot_byte_for_byte(self):
        self.assertEqual(URLS.SNAPSHOT, self.EXPECTED)


if __name__ == "__main__":
    unittest.main(verbosity=2)
