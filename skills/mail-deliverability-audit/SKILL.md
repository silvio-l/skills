---
name: mail-deliverability-audit
description: "Audits SPF, DKIM, DMARC, MX, reverse-DNS, TLS for a mail domain vs. best practice, flags spam-risk gaps with DNS fix snippets — Netcup-aware. Use for deliverability checks, spam-folder issues, 'Mail-Konfiguration prüfen', 'landet im Spam'."
---

# Mail Deliverability Audit

Checks whether a domain's mail setup (SPF, DKIM, DMARC, MX, reverse-DNS,
TLS, DNSBL) meets current best practices, so real mail doesn't land in
spam. Read-only by default — every finding ships with a copy-paste DNS
fix snippet; you (the agent) apply fixes only after the user confirms,
the same confirm-per-change discipline `seo-audit`'s `--push` flow uses.

## Where things live

| Concern | File |
|---|---|
| Check catalog — what/why/threshold per check, RFC references | [CHECKS.md](CHECKS.md) |
| Netcup shared-webhosting known-good values + gotchas | [NETCUP.md](NETCUP.md) |
| Dispatcher (single entry point) | [scripts/audit.py](scripts/audit.py) |

## Quick start

```bash
S=~/.claude/skills/mail-deliverability-audit/scripts/audit.py
python3 "$S" --domain bastheon.app --mailbox hallo@bastheon.app
```

Writes `.scratch/mail-deliverability-audit/<domain>-<date>.md` and prints
its absolute path. **Open and read it before summarizing to the user** —
exit 0 only means the script ran, not that every check passed.

## Flow

1. Run the dispatcher for the target domain (see Quick start). Network
   checks (MX/TLS/DNSBL) need outbound DNS + SMTP; some networks block
   outbound port 25 — the script marks those checks `n_a` rather than
   `fail`, read the detail line before treating them as broken.
2. If the resolved MX matches `mx*.netcup.net` (or `--netcup` was
   passed), the report includes a **Netcup Comparison** section that
   diffs the live SPF/DKIM records against the known-good values in
   [NETCUP.md](NETCUP.md) — the fast path for any project on a shared
   Netcup webhosting package.
3. Read the report's **Fix Snippets** section together with the user.
   Every `fail`/`warn` finding lists the exact DNS record (type/name/
   content/priority) needed.
4. **Never apply a DNS change without asking first, per record.** If
   the zone lives on Cloudflare (check for `~/.config/cloudflare/api.env`),
   apply via the Cloudflare API the same way already used in this
   account's projects; otherwise hand the snippet to the user for their
   DNS provider's UI. Mailbox/alias/DKIM-activation itself cannot be
   automated for Netcup — see NETCUP.md.
5. Re-run the dispatcher after changes — DNS propagation on Cloudflare
   is near-instant, but allow a minute and re-check rather than trusting
   memory.

## Arguments

| Flag | Default | Behaviour |
|---|---|---|
| `--domain <domain>` | required | Apex domain to audit (MX/SPF/DMARC/PTR checked here). |
| `--mailbox <address>` | none | Cosmetic — included in the report header. |
| `--dkim-selectors <a,b,c>` | `key1,key2,default,selector1,selector2,google,k1,dkim` | Selectors to probe under `<selector>._domainkey.<domain>`. Pass the real one if known. |
| `--client-host <hostname>` | none | Extra TLS-hostname check against a literal configured mail-client hostname — catches "pointed at the wrong host" drift (see NETCUP.md). |
| `--netcup` | auto-detected | Force the Netcup known-good comparison even when the MX hostname doesn't match `mx*.netcup.net`. |
| `--report-dir <path>` | `.scratch/mail-deliverability-audit/` | Output directory. |
| `--json` | off | Also write the findings as `<report>.json`. |

## Definition of Done

A run is done when the report exists with all applicable sections
(Critical Checks, Advanced Checks, Netcup Comparison when applicable,
Fix Snippets, Verdict) and every `fail`/`warn` finding has a non-empty
fix snippet or an explicit reason none applies.
