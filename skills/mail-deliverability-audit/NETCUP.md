# Netcup Shared Webhosting — Known-Good Mail Values

Verified 2026-07-07 against a real `hosting237032` package (Netcup
Helpcenter "DNS-Einträge — Web-Hosting", cross-checked with a live CCP
setup for `bastheon.app` and against
`~/.claude/infrastructure/netcup-hosting237032.md`, the durable
cross-project infra notes for this account). These values are **fixed
by Netcup, not parameterized per package or domain** — every Netcup
Webhosting mail domain gets the same SPF/DKIM targets.

## Expected records

| Record | Name | Expected content |
|---|---|---|
| MX | `<domain>` | `mx<hex>.netcup.net` (e.g. `mxf91d.netcup.net`), priority 10 |
| TXT (SPF) | `<domain>` | `v=spf1 mx a include:_spf.webhosting.systems ~all` |
| CNAME (DKIM) | `key1._domainkey.<domain>` | `key1._domainkey.webhosting.systems` |
| CNAME (DKIM) | `key2._domainkey.<domain>` | `key2._domainkey.webhosting.systems` |

Both DKIM CNAMEs are required — the CCP treats them as a pair, not
independently optional.

## Canonical hostnames (TLS gotcha)

Netcup's TLS certificate on the mail/web/DB servers is a **wildcard on
`*.netcup.net`** — it does not, and cannot, cover a customer domain
(`mail.<yourdomain>.tld`). Any SMTP/IMAP/POP3 client config **must**
use the canonical hostname shown in CCP → "Globale Verwaltung und
Konfigurationen des Webhostings" (pattern `mx<hex>.netcup.net`), never
the customer domain — pointing a client at `mail.<domain>` produces a
certificate-hostname-mismatch at TLS handshake time. This is exactly
what this skill's submission-TLS check catches automatically via
`--client-host`.

This is a real, previously-hit drift in this account:
`~/.config/netcup/mail.env` for `silvio-und-maik.de` shipped with
`mail.silvio-und-maik.de` instead of the canonical host — caught by
hand, not by tooling, which is the gap this skill closes.

## Ports — 465 implicit TLS only, not 587

Confirmed against this account's Plesk "E-Mail-Konto manuell
einrichten" panel: outbound authenticated SMTP is **port 465 with
implicit TLS**. Port 587/STARTTLS is **not** the supported variant on
this account — a connection attempt on 587 fails. Client libraries
must connect with implicit TLS on 465 (e.g. Symfony Mailer
`EsmtpTransport($host, 465, tls: true)` / DSN
`smtps://user:pass@mx<hex>.netcup.net:465`, never `smtp://...:587`).
Inbound is IMAP 993 / POP3 995, both SSL/TLS.

## Brute-force lockout on SMTP AUTH

Several failed `AUTH` attempts in a row triggered a temporary lockout of
**only the SMTP service** on this account (IMAP/993 stayed reachable,
SMTP/465 returned `Connection refused`) — looks like an automatic
brute-force guard. This skill's TLS checks never send `AUTH`, only a
bare TLS handshake, specifically so an audit run cannot trip this.

## Domain/mailbox management — webinterface only

Adding an external domain for mail, creating mailboxes, aliases, and
enabling DKIM all happen in the Netcup CCP webinterface. Neither the
webhosting SSH chroot
(`hosting237032@hosting237032.af91b.netcup.net` — shows only
`httpdocs/`, no mail config) nor the Server/vServer webservice API in
`~/.config/netcup/api.env` exposes this — that API is scoped to
vServer/root-server management and to DNS for domains still on
Netcup's own nameservers, neither of which applies to a
Cloudflare-delegated domain's Plesk-managed mailbox. This skill cannot
create mailboxes, aliases, or enable DKIM for you; it can only audit
what's already live and hand you copy-paste DNS snippets once it is.

## Domain verification TXT

Adding a domain as "external" in the CCP requires a one-time TXT
record at the apex holding Netcup's verification token. **It must stay
in DNS permanently** — removing it after verification can un-verify
the domain, not just skip a one-time check.
