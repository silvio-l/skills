#!/usr/bin/env python3
"""Core Web Vitals + Lighthouse check via Google's public PageSpeed Insights
API. Verified by live testing (2026-08): the anonymous, keyless quota is 0
requests/day — a free API key is required for every call, not just high
volume. Get one at https://console.cloud.google.com/apis/credentials (enable
"PageSpeed Insights API", no billing account needed), then set it:
    export PAGESPEED_API_KEY=...

Findings-first output like audit_site.py: category scores, each Core Web
Vital against Google's official "good" threshold, and the top opportunities
Lighthouse flagged — not the raw multi-hundred-KB response.

Usage:
    python3 pagespeed_check.py https://example.com/ [--strategy mobile|desktop]
"""
import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

API = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
CATEGORIES = ["performance", "seo", "accessibility", "best-practices"]

# Google's official "good" thresholds (web.dev/vitals) for lab/field metrics.
THRESHOLDS = {
    "largest-contentful-paint": ("LCP", 2500, "ms"),
    "cumulative-layout-shift": ("CLS", 0.1, ""),
    "total-blocking-time": ("TBT (INP proxy)", 200, "ms"),
    "first-contentful-paint": ("FCP", 1800, "ms"),
    "speed-index": ("Speed Index", 3400, "ms"),
}


def fetch_pagespeed(url, strategy):
    params = [("url", url), ("strategy", strategy)]
    params += [("category", c) for c in CATEGORIES]
    key = os.environ.get("PAGESPEED_API_KEY")
    if key:
        params.append(("key", key))
    full_url = API + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(full_url, headers={"User-Agent": "seo-aso-optimizer/1.0"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def render(data, url, strategy):
    lines = [f"# PageSpeed Insights — {url} ({strategy})", ""]
    lr = data.get("lighthouseResult", {})
    categories = lr.get("categories", {})
    for cat in CATEGORIES:
        c = categories.get(cat)
        if c:
            score = round(c["score"] * 100)
            flag = "OK" if score >= 90 else ("WARN" if score >= 50 else "FAIL")
            lines.append(f"- {c['title']}: {score}/100 [{flag}]")
    lines.append("")

    lines.append("## Core Web Vitals (lab data, this run)")
    audits = lr.get("audits", {})
    for key, (label, good_max, unit) in THRESHOLDS.items():
        a = audits.get(key)
        if not a or a.get("numericValue") is None:
            continue
        val = a["numericValue"]
        passed = val <= good_max
        shown = f"{val:.2f}" if unit == "" else f"{val:.0f}{unit}"
        lines.append(f"- {label}: {shown} — {'within' if passed else 'ABOVE'} Google's good threshold ({good_max}{unit})")

    field = data.get("loadingExperience", {}).get("metrics")
    if field:
        lines.append("")
        lines.append("## Field data (real Chrome users, last 28 days — CrUX)")
        for k, v in field.items():
            lines.append(f"- {k}: category={v.get('category')}")
    else:
        lines.append("")
        lines.append("## Field data: none — not enough real-user Chrome traffic in CrUX for this URL yet (lab data above is the only signal so far).")

    lines.append("")
    lines.append("## Top opportunities (Lighthouse, lowest-scoring first)")
    scored = [
        (a["score"], a.get("title", k))
        for k, a in audits.items()
        if a.get("scoreDisplayMode") == "numeric" and a.get("score") is not None and a["score"] < 0.9
    ]
    scored.sort()
    for score, title in scored[:8]:
        lines.append(f"- [{round(score * 100)}/100] {title}")
    if not scored:
        lines.append("- none below 90/100")

    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("url")
    ap.add_argument("--strategy", choices=["mobile", "desktop"], default="mobile")
    args = ap.parse_args()

    try:
        data = fetch_pagespeed(args.url, args.strategy)
    except urllib.error.HTTPError as e:
        if e.code == 429 and not os.environ.get("PAGESPEED_API_KEY"):
            print(
                "PageSpeed Insights: 429 quota exceeded — the anonymous quota is 0/day.\n"
                "Set PAGESPEED_API_KEY (free, no billing account needed):\n"
                "https://console.cloud.google.com/apis/credentials",
                file=sys.stderr,
            )
        else:
            print(f"PageSpeed Insights request failed: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"PageSpeed Insights request failed: {e}", file=sys.stderr)
        sys.exit(1)

    print(render(data, args.url, args.strategy))


if __name__ == "__main__":
    main()
