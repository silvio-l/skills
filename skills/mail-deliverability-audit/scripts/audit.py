#!/usr/bin/env python3
"""Mail deliverability auditor: SPF/DKIM/DMARC/MX/reverse-DNS/TLS/DNSBL
checks against current best practices, with Netcup shared-webhosting-
aware fix snippets. See ../SKILL.md, ../CHECKS.md, ../NETCUP.md."""

import argparse
import json
import re
import shutil
import smtplib
import socket
import ssl
import subprocess
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path

DEFAULT_DKIM_SELECTORS = [
    "key1", "key2", "default", "selector1", "selector2", "google", "k1", "dkim",
]

NETCUP_MX_RE = re.compile(r"^mx[a-f0-9]+\.netcup\.net\.?$", re.IGNORECASE)
NETCUP_SPF_TARGET = "v=spf1 mx a include:_spf.webhosting.systems ~all"
NETCUP_DKIM_TARGETS = {
    "key1": "key1._domainkey.webhosting.systems",
    "key2": "key2._domainkey.webhosting.systems",
}

STATUS_ICON = {"pass": "✅", "warn": "⚠️", "fail": "❌", "n_a": "➖", "info": "ℹ️"}


@dataclass
class Finding:
    category: str  # "critical" | "advanced" | "netcup"
    check: str
    status: str  # pass | warn | fail | n_a | info
    detail: str
    fix: str = ""


# --- DNS plumbing -----------------------------------------------------

def dig(name, rtype, timeout=5):
    """`dig +short <rtype> <name>` output lines, or None if dig is missing."""
    if shutil.which("dig") is None:
        return None
    try:
        proc = subprocess.run(
            ["dig", "+short", "+time=" + str(timeout), "+tries=1", rtype, name],
            capture_output=True, text=True, timeout=timeout + 3,
        )
    except subprocess.TimeoutExpired:
        return []
    return [line.strip() for line in proc.stdout.splitlines() if line.strip()]


def dig_ptr(ip, timeout=5):
    if shutil.which("dig") is None:
        return None
    try:
        proc = subprocess.run(
            ["dig", "-x", ip, "+short", "+time=" + str(timeout), "+tries=1"],
            capture_output=True, text=True, timeout=timeout + 3,
        )
    except subprocess.TimeoutExpired:
        return []
    return [line.strip().rstrip(".") for line in proc.stdout.splitlines() if line.strip()]


def parse_txt_values(lines):
    """Join multi-segment quoted TXT lines into one string per record."""
    values = []
    for line in lines:
        parts = re.findall(r'"((?:[^"\\]|\\.)*)"', line)
        values.append("".join(parts) if parts else line.strip('"'))
    return values


def find_spf_records(txt_values):
    return [v for v in txt_values if v.lower().startswith("v=spf1")]


def resolve_mx(domain):
    lines = dig(domain, "MX")
    if lines is None:
        return None
    records = []
    for line in lines:
        parts = line.split()
        if len(parts) == 2:
            try:
                prio = int(parts[0])
            except ValueError:
                continue
            records.append((prio, parts[1].rstrip(".")))
    records.sort(key=lambda r: r[0])
    return records


def resolve_a(host):
    return dig(host, "A") or []


# --- SPF logic (pure, unit-tested) ------------------------------------

def _strip_qualifier(token):
    if token and token[0] in "+-~?":
        return token[0], token[1:]
    return "+", token


def _is_lookup_mech(mech_lower):
    if mech_lower in ("a", "mx", "ptr"):
        return True
    return any(mech_lower.startswith(p) for p in ("include:", "a:", "a/", "mx:", "mx/", "ptr:", "exists:"))


def spf_syntax_issues(record):
    issues = []
    tokens = record.split()
    if not tokens or tokens[0].lower() != "v=spf1":
        issues.append(("fail", "record does not start with v=spf1"))
        return issues
    all_tokens = [t for t in tokens if _strip_qualifier(t)[1].lower() == "all"]
    if not all_tokens:
        issues.append(("warn", "no 'all' mechanism — undefined fallback for unlisted senders"))
    else:
        last_q, last_mech = _strip_qualifier(tokens[-1])
        if last_mech.lower() != "all":
            issues.append(("warn", "'all' mechanism is not the last term — everything after it is unreachable"))
        elif last_q in ("+",):
            issues.append(("fail", f"'{tokens[-1]}' allows anyone to spoof this domain — use ~all or -all"))
    if any(_strip_qualifier(t)[1].lower().startswith("ptr") for t in tokens):
        issues.append(("warn", "'ptr' mechanism is discouraged by RFC 7208 §5.5 (expensive, unreliable)"))
    return issues


def count_spf_lookups(record, resolver, _seen=None, _depth=0):
    """Approximate RFC 7208 §4.6.4: each include/a/mx/ptr/exists mechanism
    and the redirect modifier counts as one lookup, recursing into
    include:/redirect= targets. resolver(domain) -> list[str] of TXT values."""
    if _seen is None:
        _seen = set()
    if _depth > 10:
        return 999
    total = 0
    for token in record.split():
        _, mech = _strip_qualifier(token)
        mech_lower = mech.lower()
        is_redirect = mech_lower.startswith("redirect=")
        if not (_is_lookup_mech(mech_lower) or is_redirect):
            continue
        total += 1
        target = None
        if mech_lower.startswith("include:"):
            target = mech.split(":", 1)[1]
        elif is_redirect:
            target = mech.split("=", 1)[1]
        if target and target not in _seen:
            _seen.add(target)
            sub_spf = find_spf_records(resolver(target))
            if sub_spf:
                total += count_spf_lookups(sub_spf[0], resolver, _seen, _depth + 1)
    return total


# --- Netcup comparison (pure, unit-tested) -----------------------------

def is_netcup_mx(hostname):
    return bool(NETCUP_MX_RE.match(hostname.rstrip(".")))


def compare_netcup_spf(record):
    return record.strip().rstrip(".") == NETCUP_SPF_TARGET


def compare_netcup_dkim(selector, cname_target):
    expected = NETCUP_DKIM_TARGETS.get(selector)
    if expected is None:
        return None
    return cname_target.rstrip(".").lower() == expected.lower()


# --- Network checks -----------------------------------------------------

def check_dkim(domain, selectors):
    found = []
    for sel in selectors:
        name = f"{sel}._domainkey.{domain}"
        cname = dig(name, "CNAME")
        if cname:
            target = cname[0].rstrip(".")
            found.append({"selector": sel, "kind": "cname", "target": target,
                          "netcup_match": compare_netcup_dkim(sel, target)})
            continue
        txt = dig(name, "TXT")
        if txt:
            values = parse_txt_values(txt)
            dkim_values = [v for v in values if "v=dkim1" in v.lower() or "p=" in v.lower()]
            if dkim_values:
                found.append({"selector": sel, "kind": "txt", "value": dkim_values[0]})
    return found


def check_fcrdns(ip):
    ptr_hosts = dig_ptr(ip)
    if ptr_hosts is None:
        return {"status": "n_a", "detail": "dig not installed"}
    if not ptr_hosts:
        return {"status": "fail", "detail": f"no PTR record for {ip}"}
    for host in ptr_hosts:
        forward = resolve_a(host)
        if ip in forward:
            return {"status": "pass", "detail": f"{ip} -> {host} -> {ip} (forward-confirmed)"}
    return {"status": "warn", "detail": f"PTR {ptr_hosts} does not forward-confirm back to {ip}"}


def check_mx_tls(host, timeout=8):
    try:
        with smtplib.SMTP(host, 25, timeout=timeout) as s:
            s.ehlo()
            if not s.has_extn("starttls"):
                return {"status": "fail", "detail": f"{host}:25 does not offer STARTTLS"}
            s.starttls(context=ssl.create_default_context())
            return {"status": "pass", "detail": f"{host}:25 STARTTLS OK, certificate hostname verified"}
    except ssl.SSLCertVerificationError as e:
        return {"status": "fail", "detail": f"{host}:25 STARTTLS certificate mismatch: {e}"}
    except (OSError, smtplib.SMTPException) as e:
        return {"status": "n_a", "detail": f"could not reach {host}:25 from here ({e}) — port 25 outbound is often firewalled locally"}


def check_submission_tls(host, timeout=8):
    result_465 = None
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 465), timeout=timeout) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as tls_sock:
                tls_sock.getpeercert()
        result_465 = "ok"
    except ssl.SSLCertVerificationError as e:
        result_465 = f"cert-mismatch: {e}"
    except OSError as e:
        result_465 = f"unreachable: {e}"

    if result_465 == "ok":
        return {"status": "pass", "detail": f"{host}:465 implicit TLS OK, certificate hostname verified"}

    result_587 = None
    try:
        with smtplib.SMTP(host, 587, timeout=timeout) as s:
            s.ehlo()
            if s.has_extn("starttls"):
                s.starttls(context=ssl.create_default_context())
                result_587 = "ok"
            else:
                result_587 = "no-starttls-offered"
    except ssl.SSLCertVerificationError as e:
        result_587 = f"cert-mismatch: {e}"
    except (OSError, smtplib.SMTPException) as e:
        result_587 = f"unreachable: {e}"

    if result_587 == "ok":
        return {"status": "warn",
                "detail": f"{host}:465 failed ({result_465}), but {host}:587 STARTTLS works — "
                          "confirm your provider actually supports 587 (Netcup shared hosting does not, see NETCUP.md)"}
    return {"status": "fail", "detail": f"{host}:465 failed ({result_465}) and {host}:587 failed ({result_587})"}


def check_dnsbl(ip):
    rev = ".".join(reversed(ip.split(".")))
    result = dig(f"{rev}.zen.spamhaus.org", "A")
    if result is None:
        return {"status": "n_a", "detail": "dig not installed"}
    if result:
        return {"status": "fail", "detail": f"{ip} is listed on Spamhaus ZEN ({result[0]})"}
    return {"status": "pass", "detail": f"{ip} not listed on Spamhaus ZEN"}


def check_presence_txt(name):
    lines = dig(name, "TXT")
    if lines is None:
        return {"status": "n_a", "detail": "dig not installed"}
    values = parse_txt_values(lines)
    if values:
        return {"status": "info", "detail": f"present: {values[0][:120]}"}
    return {"status": "info", "detail": "not present"}


# --- Orchestration -------------------------------------------------------

def run_audit(domain, mailbox, selectors, client_host, force_netcup):
    domain = domain.rstrip(".")
    findings = []

    mx_records = resolve_mx(domain)
    mx_host = None
    if not mx_records:
        findings.append(Finding("critical", "MX", "fail", f"no MX record resolves for {domain}",
                                 fix=f"Add an MX record for {domain} pointing at your mail provider's canonical hostname."))
    else:
        mx_host = mx_records[0][1]
        if re.match(r"^\d+\.\d+\.\d+\.\d+$", mx_host):
            findings.append(Finding("critical", "MX", "warn",
                                     f"MX points directly at an IP ({mx_host}) — invalid per RFC 5321 §5, some MTAs reject it"))
        else:
            extra = f" (+{len(mx_records) - 1} more)" if len(mx_records) > 1 else ""
            findings.append(Finding("critical", "MX", "pass", f"{domain} -> {mx_records[0][0]} {mx_host}{extra}"))

    netcup_mode = force_netcup or bool(mx_host and is_netcup_mx(mx_host))

    apex_txt = parse_txt_values(dig(domain, "TXT") or [])
    spf_records = find_spf_records(apex_txt)
    default_spf_hint = NETCUP_SPF_TARGET if netcup_mode else "v=spf1 mx a ~all"
    if len(spf_records) == 0:
        findings.append(Finding("critical", "SPF", "fail", f"no SPF (v=spf1) TXT record at {domain}",
                                 fix=f"Add TXT record `{domain}` -> `{default_spf_hint}`"))
    elif len(spf_records) > 1:
        findings.append(Finding("critical", "SPF", "fail",
                                 f"{len(spf_records)} SPF records found — RFC 7208 requires exactly one, extras cause permerror",
                                 fix="Delete all but one SPF TXT record."))
    else:
        record = spf_records[0]
        issues = spf_syntax_issues(record)
        lookups = count_spf_lookups(record, lambda d: parse_txt_values(dig(d, "TXT") or []))
        status = "pass"
        details = [f"`{record}` ({lookups} DNS lookups)"]
        for level, msg in issues:
            details.append(msg)
            if level == "fail":
                status = "fail"
            elif level == "warn" and status == "pass":
                status = "warn"
        if lookups > 10:
            status = "fail"
            details.append(f"{lookups} lookups exceeds the RFC 7208 §4.6.4 hard limit of 10 (permerror)")
        elif lookups >= 8 and status == "pass":
            status = "warn"
            details.append(f"{lookups}/10 lookups used — little headroom left")
        findings.append(Finding("critical", "SPF", status, "; ".join(details)))

    dkim_found = check_dkim(domain, selectors)
    if not dkim_found:
        findings.append(Finding("critical", "DKIM", "fail",
                                 f"none of the probed selectors ({', '.join(selectors)}) resolve under _domainkey.{domain}",
                                 fix="Enable DKIM for this domain in your mail provider's panel, then pass the real selector via --dkim-selectors."))
    else:
        parts, overall = [], "pass"
        for f in dkim_found:
            if f["kind"] == "cname":
                nm = f["netcup_match"]
                if nm is False:
                    overall = "warn"
                    parts.append(f"{f['selector']} -> {f['target']} (does NOT match Netcup's expected target)")
                else:
                    parts.append(f"{f['selector']} -> {f['target']}" + (" (matches Netcup)" if nm else ""))
            else:
                parts.append(f"{f['selector']}: TXT key present")
        findings.append(Finding("critical", "DKIM", overall, "; ".join(parts)))

    dmarc_txt = parse_txt_values(dig(f"_dmarc.{domain}", "TXT") or [])
    dmarc_records = [v for v in dmarc_txt if v.lower().startswith("v=dmarc1")]
    if not dmarc_records:
        findings.append(Finding("critical", "DMARC", "fail", f"no DMARC record at _dmarc.{domain}",
                                 fix=f"Add TXT record `_dmarc.{domain}` -> `v=DMARC1; p=none; rua=mailto:postmaster@{domain}`"))
    else:
        record = dmarc_records[0]
        has_rua = "rua=" in record
        status = "pass" if has_rua else "warn"
        detail = f"`{record}`"
        if not has_rua:
            detail += " — no rua= reporting address, zero visibility into spoofing"
        findings.append(Finding("critical", "DMARC", status, detail))

    if mx_host:
        mx_ips = resolve_a(mx_host)
        if not mx_ips:
            findings.append(Finding("critical", "Reverse DNS", "n_a", f"could not resolve {mx_host} to an IP"))
        else:
            r = check_fcrdns(mx_ips[0])
            findings.append(Finding("critical", "Reverse DNS", r["status"], r["detail"]))
    else:
        findings.append(Finding("critical", "Reverse DNS", "n_a", "skipped, no MX resolved"))

    if mx_host:
        r = check_mx_tls(mx_host)
        findings.append(Finding("advanced", "STARTTLS (MX, port 25)", r["status"], r["detail"]))
        r = check_submission_tls(mx_host)
        findings.append(Finding("advanced", "Submission TLS (465/587)", r["status"], r["detail"]))
        mx_ips = resolve_a(mx_host)
        if mx_ips:
            r = check_dnsbl(mx_ips[0])
            findings.append(Finding("advanced", "DNSBL (Spamhaus ZEN)", r["status"], r["detail"]))

    if client_host:
        r = check_submission_tls(client_host)
        findings.append(Finding("advanced", f"Submission TLS ({client_host})", r["status"], r["detail"]))

    for label, name in (("MTA-STS", f"_mta-sts.{domain}"), ("TLS-RPT", f"_smtp._tls.{domain}"),
                         ("BIMI", f"default._bimi.{domain}")):
        r = check_presence_txt(name)
        findings.append(Finding("advanced", label, r["status"], r["detail"]))

    if netcup_mode:
        if spf_records:
            match = compare_netcup_spf(spf_records[0])
            findings.append(Finding(
                "netcup", "SPF matches Netcup target", "pass" if match else "warn",
                "matches" if match else f"live: `{spf_records[0]}` vs expected `{NETCUP_SPF_TARGET}`",
                fix="" if match else f"Set TXT `{domain}` -> `{NETCUP_SPF_TARGET}`"))
        for sel, expected in NETCUP_DKIM_TARGETS.items():
            live = next((f for f in dkim_found if f["selector"] == sel and f["kind"] == "cname"), None)
            if live is None:
                findings.append(Finding("netcup", f"DKIM {sel} present", "fail",
                                         f"missing CNAME {sel}._domainkey.{domain}",
                                         fix=f"Add CNAME `{sel}._domainkey.{domain}` -> `{expected}`"))
            elif not live["netcup_match"]:
                findings.append(Finding("netcup", f"DKIM {sel} matches Netcup target", "warn",
                                         f"live target `{live['target']}` != expected `{expected}`",
                                         fix=f"Fix CNAME `{sel}._domainkey.{domain}` -> `{expected}`"))
            else:
                findings.append(Finding("netcup", f"DKIM {sel} matches Netcup target", "pass", "matches"))

    return findings


def render_report(domain, mailbox, findings):
    critical = [f for f in findings if f.category == "critical"]
    critical_fail = any(f.status == "fail" for f in critical)
    critical_warn = any(f.status == "warn" for f in critical)
    verdict = "NEEDS FIXES" if critical_fail else ("PARTIAL" if critical_warn else "READY")

    def section(title, category):
        rows = [f for f in findings if f.category == category]
        if not rows:
            return ""
        lines = [f"## {title}\n", "| Check | Status | Detail |", "|---|---|---|"]
        for f in rows:
            icon = STATUS_ICON.get(f.status, "")
            lines.append(f"| {f.check} | {icon} {f.status} | {f.detail} |")
        return "\n".join(lines) + "\n"

    lines = [f"# Mail Deliverability Audit — {domain}"]
    header = f"Date: {date.today().isoformat()}  Verdict: **{verdict}**"
    if mailbox:
        header = f"Mailbox: `{mailbox}`  {header}"
    lines.append(f"\n{header}\n")
    for title, category in (("Critical Checks", "critical"), ("Advanced Checks", "advanced"),
                             ("Netcup Comparison", "netcup")):
        rendered = section(title, category)
        if rendered:
            lines.append(rendered)

    fixes = [f for f in findings if f.fix]
    if fixes:
        lines.append("## Fix Snippets\n")
        for f in fixes:
            lines.append(f"- **{f.check}**: {f.fix}")
        lines.append("")

    verdict_text = {
        "NEEDS FIXES": "one or more critical checks failed — fix before relying on this domain for mail.",
        "PARTIAL": "critical checks pass with warnings — review before considering this fully hardened.",
        "READY": "all critical checks pass.",
    }[verdict]
    lines.append(f"## Verdict\n\n{verdict} — {verdict_text}")
    return "\n".join(lines) + "\n", verdict


def main():
    parser = argparse.ArgumentParser(description="Mail deliverability auditor")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--mailbox", default="")
    parser.add_argument("--dkim-selectors", default=",".join(DEFAULT_DKIM_SELECTORS))
    parser.add_argument("--client-host", default="")
    parser.add_argument("--netcup", action="store_true")
    parser.add_argument("--report-dir", default=".scratch/mail-deliverability-audit")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    if shutil.which("dig") is None:
        print("ERROR: `dig` is required (bind-utils / dnsutils, preinstalled on macOS) and was not found on PATH.",
              file=sys.stderr)
        sys.exit(1)

    selectors = [s.strip() for s in args.dkim_selectors.split(",") if s.strip()]
    findings = run_audit(args.domain, args.mailbox, selectors, args.client_host, args.netcup)
    report, _verdict = render_report(args.domain, args.mailbox, findings)

    report_dir = Path(args.report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    base_name = f"{args.domain.rstrip('.')}-{date.today().isoformat()}"
    md_path = report_dir / f"{base_name}.md"
    md_path.write_text(report)

    if args.json:
        json_path = report_dir / f"{base_name}.json"
        json_path.write_text(json.dumps([f.__dict__ for f in findings], indent=2))

    print(str(md_path.resolve()))


if __name__ == "__main__":
    main()
