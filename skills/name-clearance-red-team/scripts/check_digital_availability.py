#!/usr/bin/env python3
"""
Deterministic digital-availability check: domains via RDAP (IANA's official
bootstrap registry, RFC 7482/9224 — never socket.gethostbyname, which gives
false "taken" for parked-but-unregistered names and false "available" for
registered-but-unresolving ones), plus GitHub/npm/PyPI existence checks via
their public JSON APIs.

Many common TLDs (.de, .io, .eu among them — verified against IANA's live
bootstrap file) have NO entry in the RDAP bootstrap at all. For those, this
script always reports "unknown", never a guessed "available" — see
classify_rdap(). App-store names and social-media handles have no reliable
public existence API and are out of scope here by design; the agent records
those as manual_verification_required rows in the search log instead of
scraping them.

Usage: python3 check_digital_availability.py "<name>" --tlds de,com,eu,io
       [--platforms github,npm,pypi] [--out <path>]
"""
import argparse
import datetime
import json
import re
import sys
import urllib.error
import urllib.request

IANA_BOOTSTRAP_URL = "https://data.iana.org/rdap/dns.json"
USER_AGENT = "name-clearance-red-team/1.0 (RDAP domain-availability check)"
SUPPORTED_PLATFORMS = ("github", "npm", "pypi")


def slugify(name):
    return re.sub(r"[^a-z0-9]", "", name.lower())


def http_get(url, headers=None, timeout=10):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, **(headers or {})})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode(), resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body
    except (urllib.error.URLError, TimeoutError, OSError):
        return None, ""


def fetch_rdap_bootstrap(timeout=10):
    """tld -> RDAP base URL, per IANA's live registry. Empty dict on fetch failure."""
    status, body = http_get(IANA_BOOTSTRAP_URL, timeout=timeout)
    if status != 200:
        return {}
    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return {}
    mapping = {}
    for entry in data.get("services", []):
        if len(entry) < 2:
            continue
        tlds, urls = entry[0], entry[1]
        base = next((u for u in urls if u.startswith("https://")), urls[0] if urls else None)
        if not base:
            continue
        if not base.endswith("/"):
            base += "/"
        for tld in tlds:
            mapping[tld.lower()] = base
    return mapping


def classify_rdap(status_code, body, tld_supported=True):
    """Pure classifier — see tests/name-clearance-red-team/test_check_digital_availability.py."""
    if not tld_supported:
        return "unknown", "rdap_not_supported_for_tld"
    if status_code == 404:
        return "available", "rdap_returned_404_not_found"
    if status_code == 200:
        try:
            parsed = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            return "unknown", "rdap_200_but_unparseable_body"
        if isinstance(parsed, dict) and parsed.get("ldhName"):
            return "taken", "rdap_200_with_ldhName"
        return "unknown", "rdap_200_but_no_ldhName"
    if status_code is None:
        return "unknown", "network_error"
    if status_code in (429, 503):
        return "unknown", "rate_limited_or_unavailable"
    return "unknown", f"unexpected_http_status_{status_code}"


def classify_by_http_existence(status_code, source_label):
    """Pure classifier shared by the GitHub/npm/PyPI checks."""
    if status_code == 404:
        return "available", f"{source_label}_404"
    if status_code == 200:
        return "taken", f"{source_label}_200"
    if status_code is None:
        return "unknown", f"{source_label}_network_error"
    return "unknown", f"{source_label}_status_{status_code}"


def check_domain(name, tld, bootstrap):
    domain = f"{slugify(name)}.{tld}"
    base = bootstrap.get(tld.lower())
    if not base:
        status, reason = classify_rdap(None, "", tld_supported=False)
        return {
            "kind": "domain", "identifier": domain, "status": status, "method": "rdap",
            "evidence": {"tld_in_bootstrap": False},
            "checked_at": now_iso(), "reason": reason,
        }
    status_code, body = http_get(base + "domain/" + domain, headers={"Accept": "application/rdap+json"})
    status, reason = classify_rdap(status_code, body, tld_supported=True)
    return {
        "kind": "domain", "identifier": domain, "status": status, "method": "rdap",
        "evidence": {"tld_in_bootstrap": True, "http_status": status_code, "rdap_base": base},
        "checked_at": now_iso(), "reason": reason,
    }


def check_github(name):
    slug = slugify(name)
    org_status, _ = http_get(f"https://api.github.com/orgs/{slug}")
    if org_status == 200:
        status, reason = "taken", "github_org_200"
    else:
        user_status, _ = http_get(f"https://api.github.com/users/{slug}")
        status, reason = classify_by_http_existence(user_status, "github_user")
    return {
        "kind": "platform", "identifier": f"github:{slug}", "status": status, "method": "github_api",
        "evidence": {"checked": ["orgs", "users"]}, "checked_at": now_iso(), "reason": reason,
    }


def check_npm(name):
    slug = slugify(name)
    status_code, _ = http_get(f"https://registry.npmjs.org/{slug}")
    status, reason = classify_by_http_existence(status_code, "npm")
    return {
        "kind": "platform", "identifier": f"npm:{slug}", "status": status, "method": "npm_api",
        "evidence": {"http_status": status_code}, "checked_at": now_iso(), "reason": reason,
    }


def check_pypi(name):
    slug = slugify(name)
    status_code, _ = http_get(f"https://pypi.org/pypi/{slug}/json")
    status, reason = classify_by_http_existence(status_code, "pypi")
    return {
        "kind": "platform", "identifier": f"pypi:{slug}", "status": status, "method": "pypi_api",
        "evidence": {"http_status": status_code}, "checked_at": now_iso(), "reason": reason,
    }


def now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def render_summary(records):
    lines = ["# Digital availability"]
    for kind in ("domain", "platform"):
        rows = [r for r in records if r["kind"] == kind]
        if not rows:
            continue
        lines.append(f"\n## {kind}s ({len(rows)})")
        for r in rows:
            lines.append(f"- {r['identifier']}: {r['status']} ({r['reason']})")
    unknown = [r for r in records if r["status"] == "unknown"]
    if unknown:
        lines.append(f"\n{len(unknown)} check(s) inconclusive — never treat 'unknown' as 'available'.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name")
    parser.add_argument("--tlds", default="de,com,eu")
    parser.add_argument("--platforms", default="github,npm,pypi")
    parser.add_argument("--out")
    args = parser.parse_args()

    tlds = [t.strip() for t in args.tlds.split(",") if t.strip()]
    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    unsupported = [p for p in platforms if p not in SUPPORTED_PLATFORMS]
    if unsupported:
        parser.error(
            f"unsupported platform(s): {', '.join(unsupported)} — only {', '.join(SUPPORTED_PLATFORMS)} have a "
            "reliable public existence API in this script. App-store names and social handles are "
            "manual_verification_required by design; add them as search-log rows instead."
        )

    bootstrap = fetch_rdap_bootstrap()
    records = [check_domain(args.name, tld, bootstrap) for tld in tlds]
    checkers = {"github": check_github, "npm": check_npm, "pypi": check_pypi}
    records += [checkers[p](args.name) for p in platforms]

    print(render_summary(records))

    result = {"input": args.name, "generated_at": now_iso(), "records": records}
    if args.out:
        with open(args.out, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
    else:
        print("\n---\n")
        print(json.dumps(result, ensure_ascii=False, indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
