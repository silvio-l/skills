#!/usr/bin/env python3
"""Repository inventory for seo-audit.

Detects the web framework, locates the domain document, and notes
which SEO assets and app-store listings are present. Pure filesystem
inspection — no parsing of source code, no shell-outs.

Returns an `InventoryReport` dict that the report-writer turns into
the *Inventory* section of the audit report.
"""

from __future__ import annotations

import json
import os
import sys
from typing import Dict, List


DOMAIN_DOC_CANDIDATES = ("CONTEXT.md", "CLAUDE.md", "README.md")

SEO_ASSET_NAMES = (
    "robots.txt", "sitemap.xml", "sitemap-index.xml",
    "llms.txt", "llms-full.txt", "ai.txt",
)

APP_STORE_INDICATORS = (
    "store",                 # store/ subdirectory
    "package.appxmanifest",  # MS Store
    "Info.plist",            # Apple
)


def _detect_framework(root: str) -> str:
    # Astro: astro.config.{mjs,ts,js}
    for name in ("astro.config.mjs", "astro.config.ts",
                 "astro.config.js", "astro.config.cjs"):
        if os.path.isfile(os.path.join(root, name)):
            return "astro"
    # Next: next.config.{mjs,ts,js}
    for name in ("next.config.mjs", "next.config.ts",
                 "next.config.js", "next.config.cjs"):
        if os.path.isfile(os.path.join(root, name)):
            return "next"
    # Static site: a top-level index.html with no JS framework config.
    if os.path.isfile(os.path.join(root, "index.html")):
        return "static"
    return "unknown"


def _find_domain_doc(root: str) -> str:
    for name in DOMAIN_DOC_CANDIDATES:
        path = os.path.join(root, name)
        if os.path.isfile(path):
            return name
    return ""


def _scan_seo_assets(root: str) -> List[str]:
    found = []
    for name in SEO_ASSET_NAMES:
        for base in (root, os.path.join(root, "public"),
                     os.path.join(root, "static"),
                     os.path.join(root, "dist")):
            path = os.path.join(base, name)
            if os.path.isfile(path):
                found.append(os.path.relpath(path, root))
                break
    return sorted(found)


def _scan_app_store_listings(root: str) -> List[str]:
    out = []
    for indicator in APP_STORE_INDICATORS:
        # Walk shallowly — these live in well-known places.
        for dirpath, dirs, files in os.walk(root):
            # Skip noisy paths.
            depth = dirpath[len(root):].count(os.sep)
            if depth > 3:
                dirs[:] = []
                continue
            if indicator == "store" and "store" in dirs:
                out.append(os.path.relpath(os.path.join(dirpath, "store"), root))
                dirs.remove("store")
            elif indicator in files:
                out.append(os.path.relpath(os.path.join(dirpath, indicator), root))
    return sorted(set(out))


def _list_html_pages(root: str) -> List[str]:
    """List relative HTML page paths from a dist/ tree if one exists."""
    dist = os.path.join(root, "dist")
    if not os.path.isdir(dist):
        return []
    pages = []
    for dirpath, _dirs, files in os.walk(dist):
        for name in files:
            if name.lower().endswith((".html", ".htm")):
                pages.append(os.path.relpath(
                    os.path.join(dirpath, name), root))
    return sorted(pages)


def inventory(root: str) -> Dict:
    return {
        "root": os.path.abspath(root),
        "framework": _detect_framework(root),
        "domain_doc": _find_domain_doc(root),
        "seo_assets": _scan_seo_assets(root),
        "app_store_listings": _scan_app_store_listings(root),
        "pages": _list_html_pages(root),
    }


def main() -> int:
    if len(sys.argv) < 2:
        sys.exit("usage: inventory.py <root>")
    print(json.dumps(inventory(sys.argv[1]), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
