# Check Catalog

Since Feb 2024, Gmail and Yahoo require SPF+DKIM+DMARC for any sender
pushing meaningful volume and actively enforce it — that raised the bar
for what "meets best practice" means for every domain, not just bulk
senders. The checks below track that bar plus the older FCrDNS/TLS
conventions most receiving MTAs already scored on for years.

Every check reports one of: `pass`, `warn`, `fail`, `n_a` (could not be
determined — usually a local network restriction, not the target's
fault), or `info` (observational, not scored).

## Critical (deliverability-breaking if missing/wrong)

### MX
At least one MX record resolves. Lower priority number = more preferred
(RFC 5321 §5). `fail` if none resolve; `warn` if MX points directly at
an IP literal instead of a hostname (invalid per RFC 5321, some MTAs
reject it outright).

### SPF (RFC 7208)
- Exactly one TXT record starting `v=spf1` at the apex. **Two or more
  → `permerror`**; most receivers treat a permerror as fail. `fail` if
  0 or >1 SPF records are found.
- Ends in `-all` (hard fail) or `~all` (soft fail). `fail` if it ends in
  `+all` (anyone can spoof the domain) or has no `all` mechanism at all
  (undefined fallback for unlisted senders).
- **≤10 DNS-lookup mechanisms** (`a`, `mx`, `ptr`, `exists`, `include`,
  and the `redirect` modifier), counted recursively through
  `include:`/`redirect=` chains — exceeding it is a hard `permerror`
  per §4.6.4. `fail` at >10 lookups, `warn` at 8–10 (little headroom
  left before an unrelated third-party `include:` change breaks you).
- `ptr` mechanism: RFC 7208 §5.5 itself says implementations "SHOULD
  NOT" publish it (expensive, unreliable). `warn` if present.

### DKIM (RFC 6376)
At least one selector under `<selector>._domainkey.<domain>` resolves
— either a `v=DKIM1` TXT record directly, or (Netcup's pattern) a CNAME
delegating to one. `fail` if none of the probed selectors resolve. Key
strength (RSA ≥ 2048-bit recommended) is only inspectable for a direct
TXT key, not a CNAME-delegated one — that sub-check is `n_a` for Netcup.

### DMARC (RFC 7489)
- `_dmarc.<domain>` TXT starting `v=DMARC1` with a `p=` tag. `fail` if
  missing entirely — this is exactly what Gmail/Yahoo's 2024 bulk-sender
  rules require.
- `warn` (not `fail`) if present but has no `rua=` reporting address —
  the domain has zero visibility into spoofing attempts even if a
  policy is set.
- Policy strictness (`p=none`/`quarantine`/`reject`) is reported as
  `info`, not scored — `none` → `quarantine` → `reject` is a deliberate
  rollout over weeks/months, not a config bug to fix in one pass.

### Reverse DNS / FCrDNS
The sending IP's PTR record resolves, and forward-resolving that
hostname returns the same IP (forward-confirmed reverse DNS) — one of
the oldest and still most-weighted anti-spam heuristics (e.g. Postfix's
`reject_unknown_client_hostname` gates on exactly this). `fail` if no
PTR record exists; `warn` if a PTR exists but doesn't forward-confirm.

## Advanced (state of the art, not yet universally required)

### STARTTLS / certificate hostname (MX, port 25)
Connects to the MX host and negotiates STARTTLS, then validates the
certificate's CN/SAN actually matches the hostname connected to.
`n_a` (not `fail`) if the connection itself is refused/times out —
common when the auditing machine's own network firewalls outbound 25.

### Submission TLS (port 465 / 587)
Separately checks both the implicit-TLS submission port (465) and the
STARTTLS submission port (587), since providers differ on which they
actually support — Netcup shared webhosting supports **465 only**, 587
fails outright (see NETCUP.md). `pass` if 465 works; `warn` if only 587
works (confirm the provider genuinely supports it before relying on
it); `fail` if neither works. Never sends `AUTH` — only the TLS
handshake is tested, so this cannot trigger a provider's brute-force
lockout on the mailbox.

This is the automated version of the Netcup wildcard-cert gotcha in
[NETCUP.md](NETCUP.md): a `*.netcup.net` wildcard cert **fails**
hostname validation if a client is pointed at `mail.<customerdomain>`
instead of the canonical `mx<hex>.netcup.net`. Pass `--client-host` to
check one specific configured hostname directly.

### DNSBL / RBL
Reverse-IP query against Spamhaus ZEN (`zen.spamhaus.org`) — the most
widely consulted blocklist. `fail` if listed, `pass` if not. Single DNS
query, free, no key required; do not add more blocklist zones without
checking their published query-rate policy first (Free-Tier-Disziplin).

### MTA-STS (RFC 8461) / TLS-RPT (RFC 8460)
Presence of `_mta-sts.<domain>` and `_smtp._tls.<domain>` TXT records.
`info`-only, not scored — very few small domains have these yet; this
is a forward-looking recommendation, not a current gap.

### BIMI
Presence of `default._bimi.<domain>` TXT. `info`-only — BIMI requires
DMARC at `p=quarantine`/`reject` plus a verified-mark certificate at
most inbox providers, so it's a later-stage recommendation, not
something to flag as broken today.

## Netcup Comparison (conditional section)

Rendered only when the resolved MX matches `mx[a-f0-9]+\.netcup\.net`
or `--netcup` was passed explicitly. Diffs the live SPF/DKIM records
against the exact values in [NETCUP.md](NETCUP.md).
