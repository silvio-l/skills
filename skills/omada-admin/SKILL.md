---
name: omada-admin
description: 'Manage a TP-Link Omada SDN Controller via its API — devices, clients, DHCP reservations, VLANs, SSIDs, firewall rules, switch ports. Triggers: "Omada", "OC200", "SSID", "VLAN", "DHCP-Reservierung", "AP konfigurieren".'
---

# Omada Admin

Controls a TP-Link Omada SDN hardware controller (OC200 or similar) over its HTTP API. Two API surfaces exist — pick the right one.

## Bootstrap

```bash
source ~/.config/omada/.env
```

Sets `OMADA_URL`, `OMADA_OMADAC_ID`, `OMADA_SITE_ID`, `OMADA_OPENAPI_CLIENT_ID`, `OMADA_OPENAPI_CLIENT_SECRET`, `OMADA_WEB_USER`, `OMADA_WEB_PASS`. Site-specific values (URL, IDs, credentials) live in that `.env` file only — never hardcode them anywhere, including in this skill's own files.

## API surfaces

| | OpenAPI v1 | Web API v2 |
|---|---|---|
| Auth | OAuth2 client credentials | Session (login → CSRF token + cookie) |
| Base | `$OMADA_URL/openapi/v1/$OMADA_OMADAC_ID/sites/$OMADA_SITE_ID/` | `$OMADA_URL/$OMADA_OMADAC_ID/api/v2/sites/$OMADA_SITE_ID/` |
| Confirmed working | `clients`, `devices` (active clients/devices only) | Everything — clients (incl. offline), networks, SSIDs, firewall, switches, mDNS, AP radio config |
| Best for | Quick reads of currently-active clients/devices | Every write, and any read of an offline/reserved client |

**Leading rule: default to Web API v2.** It is the only surface confirmed to cover writes and offline clients. Reach for OpenAPI v1 only for a quick read of a client or device you know is currently online.

**Path segment, not query param:** on both surfaces the site scope is a URL path segment (`.../sites/$OMADA_SITE_ID/...`), never a `?siteId=` query parameter — using a query param returns `-1001`.

## Step 1: Authenticate

Always authenticate and make the call in the *same* shell block — sessions/tokens are short-lived, and reusing a token or cookie from an earlier call is a common source of spurious `-1600`/`-1` errors.

### Web API v2 — session auth (default)

```bash
source ~/.config/omada/.env
CSRF=$(curl -sk -X POST "$OMADA_URL/$OMADA_OMADAC_ID/api/v2/login" \
  -H "Content-Type: application/json" \
  -d "{\"username\":\"$OMADA_WEB_USER\",\"password\":\"$OMADA_WEB_PASS\"}" \
  -c /tmp/omada_cookie.txt \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['token'])")
```

Every subsequent request needs: header `Csrf-Token: $CSRF`, cookie `-b /tmp/omada_cookie.txt`, URL query param `?token=$CSRF`.

### OpenAPI v1 — client credentials

```bash
source ~/.config/omada/.env
TOKEN=$(curl -sk -X POST "$OMADA_URL/openapi/authorize/token?grant_type=client_credentials" \
  -H 'content-type:application/json' \
  -d "{\"omadacId\":\"$OMADA_OMADAC_ID\",\"client_id\":\"$OMADA_OPENAPI_CLIENT_ID\",\"client_secret\":\"$OMADA_OPENAPI_CLIENT_SECRET\"}" \
  | python3 -c "import sys,json; print(json.load(sys.stdin)['result']['accessToken'])")
```

`accessToken` has a 2h TTL. Subsequent calls use header `Authorization:AccessToken=$TOKEN`.

## Step 2: Execute operation

Common endpoints, payload shapes, and field values are in [`API-REFERENCE.md`](API-REFERENCE.md) — load it on demand rather than guessing a payload.

### Quick reference — most-used Web API v2 endpoints

| Task | Method | Path (relative to Web API v2 base) |
|---|---|---|
| List/find a client (incl. offline) | GET | `/insight/clients?currentPage=1&currentPageSize=200` |
| Client detail (incl. DHCP reservation) | GET | `/clients/{mac}` |
| Set/change DHCP reservation | PATCH | `/clients/{mac}` — see recipe below |
| List devices | GET | `/devices` |
| List networks/VLANs | GET | `/setting/lan/networks` |
| List SSIDs | GET | `/setting/wlans/{wlanGroupId}/ssids` |
| Create SSID | POST | `/setting/wlans/{wlanGroupId}/ssids` |
| List firewall ACLs | GET | `/setting/firewall/acls?type=0` |
| Create firewall ACL | POST | `/setting/firewall/acls` |
| mDNS rules | GET/PATCH | `/setting/service/mdns` |
| AP details / radio / RSSI | GET/PATCH | `/eaps/{mac}` |
| AP SSID override | PUT | `/eaps/{mac}/config/wlans` (PATCH silently ignores this) |
| Switch ports | GET/PATCH | `/switches/{mac}/ports` |
| Adopt device | POST | `/cmd/devices/adopt` (body: `{"mac":"..."}`) |

### Recipe: read or change a DHCP reservation (verified working)

DHCP reservations ("Fixed Address" in the UI) are not a separate list — they are the `ipSetting` field on a client:

```json
"ipSetting": {"useFixedAddr": true, "netId": "...", "ip": "192.168.0.171", "serverType": "gateway", "serverMac": "..."}
```

0. **`GET /setting/lan/networks` first and read `dhcpSettings.ipaddrStart`/`ipaddrEnd`.** The reserved IP must be **outside** that dynamic pool range. On at least some gateway firmware, a reservation for an address *inside* the pool is silently ignored — the gateway keeps handing that client a normal pool address instead, with no error anywhere. This is not a hypothetical: verified 2026-08-09 against firmware 6.2.14.12 — of 25 existing reservations, every one outside the pool worked, and the only two inside the pool were both silently ignored. Pick an unused address below `ipaddrStart` or above `ipaddrEnd`, and confirm it's actually free (see step 5).
1. Find the client's MAC. `GET /insight/clients` lists every client the controller has ever seen (including offline ones) — prefer it over OpenAPI's `clients`, which only returns currently-active clients and will silently miss an offline reservation target.
2. `GET /clients/{mac}` to read the current `ipSetting` (get the right `netId`/`serverMac` for that network).
3. `PATCH /clients/{mac}` with body `{"ipSetting": {...}}`, keeping `netId`/`serverType`/`serverMac` from step 2 and changing only what needs to change.
4. **A `PATCH` returning `errorCode: 0`, or a subsequent `GET` echoing the new `ipSetting`, only proves the controller's database accepted the write — not that the gateway enforces it.** Both silently succeed even when the reservation (step 0's bug) never takes effect. The only real verification is checking the client's actual live-leased IP after a fresh DHCP negotiation (reboot the client's network stack, or wait for a lease renewal, then read the live IP from the device itself or from `GET /clients/{mac}`'s top-level `ip` field — not `ipSetting`).

**A device with two NICs (e.g. Wi-Fi + Ethernet) needs two separate identifications** — the controller has no "same physical host" grouping, so a shared hostname on one interface doesn't imply the other reports one too. Match by connection type (`wireless: true/false`), MAC vendor prefix (OUI), and whether it's currently `active`, rather than guessing.

**Swapping a reserved IP between two clients:** change the *old holder's* reservation away from the IP first, then assign it to the *new holder* — never have both hold the same IP at once, even briefly. Also double-check the target IP isn't some unrelated device's *current dynamic* lease (`GET /insight/clients` or the OpenAPI `clients` list, both include the live `ip`) — a reservation doesn't reserve anything against a device that's already holding that address dynamically.

**The reservation change only takes effect on the client's *next* DHCP negotiation**, not retroactively on an already-running lease. A plain lease *renewal* (unicast REQUEST for the same IP the client already holds) is often not enough to pick up a changed reservation — it may need a full new negotiation (release + discover), e.g. by cycling the client's interface down/up. If continuous reachability matters, do this one interface at a time (never all at once), so at least one path stays up throughout — and be ready to fall back to whatever IP the interface ends up with if the reservation still doesn't apply, rather than assuming the target address.

## Hard rules

- **PATCH needs the full sub-object**, not a partial diff — GET first, modify the fields you need, PATCH the whole `ipSetting`/config object back.
- **`protocols: []` is unreliable** on firewall ACLs — always set explicit protocols `[6, 17, 1]`.
- **`security: 2` (WPA2-only) fails on SSID creation** — use `security: 3` (WPA2/WPA3).
- **SSID overrides require `PUT /eaps/{mac}/config/wlans`** — PATCH silently ignores them.
- **Trunk profiles need `nativeNetworkId`** — profiles without it cannot be assigned to ports.
- **Channel is set via `freq` (MHz), not `channel`** — see the frequency table in the reference.
- **Re-authenticate on `-1`/`-44116`** — the token/session invalidates after a site copy/import or a permission change.
- **A DHCP reservation inside the network's dynamic pool range is silently ignored by the gateway** — the write succeeds and reads back fine, but is never enforced. Always reserve an address outside `dhcpSettings.ipaddrStart`–`ipaddrEnd`. See the recipe above.
- **`PATCH /setting/lan/networks/{id}` can reject a full GET-then-PATCH round-trip with `-1001` for a field absent from the GET response** (e.g. `proto`) — the network-settings schema isn't fully self-describing on read. Treat network-level (not client-level) DHCP/pool edits as unverified; a failed attempt here left the pool untouched, which is the safe outcome.
