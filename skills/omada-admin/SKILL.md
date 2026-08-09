---
name: omada-admin
description: Manage a TP-Link Omada SDN Controller via its API — devices, clients, DHCP reservations, VLANs, SSIDs, firewall rules, switch ports. Triggers: "Omada", "OC200", "SSID", "VLAN", "DHCP-Reservierung", "AP konfigurieren".
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

1. Find the client's MAC. `GET /insight/clients` lists every client the controller has ever seen (including offline ones) — prefer it over OpenAPI's `clients`, which only returns currently-active clients and will silently miss an offline reservation target.
2. `GET /clients/{mac}` to read the current `ipSetting` (get the right `netId`/`serverMac` for that network).
3. `PATCH /clients/{mac}` with body `{"ipSetting": {...}}`, keeping `netId`/`serverType`/`serverMac` from step 2 and changing only what needs to change.
4. `GET /clients/{mac}` again to confirm the controller-side reservation took.

**A device with two NICs (e.g. Wi-Fi + Ethernet) needs two separate identifications** — the controller has no "same physical host" grouping, so a shared hostname on one interface doesn't imply the other reports one too. Match by connection type (`wireless: true/false`), MAC vendor prefix (OUI), and whether it's currently `active`, rather than guessing.

**Swapping a reserved IP between two clients:** change the *old holder's* reservation away from the IP first, then assign it to the *new holder* — never have both hold the same IP at once, even briefly.

**The reservation change is controller-side only.** It takes effect on the client's *next* DHCP lease renewal, not retroactively on an already-running lease — the controller cannot force this without a reconnect/port action that would interrupt the client. If continuous reachability matters, renew the client's interfaces one at a time (never all at once), so at least one path stays up throughout.

## Hard rules

- **PATCH needs the full sub-object**, not a partial diff — GET first, modify the fields you need, PATCH the whole `ipSetting`/config object back.
- **`protocols: []` is unreliable** on firewall ACLs — always set explicit protocols `[6, 17, 1]`.
- **`security: 2` (WPA2-only) fails on SSID creation** — use `security: 3` (WPA2/WPA3).
- **SSID overrides require `PUT /eaps/{mac}/config/wlans`** — PATCH silently ignores them.
- **Trunk profiles need `nativeNetworkId`** — profiles without it cannot be assigned to ports.
- **Channel is set via `freq` (MHz), not `channel`** — see the frequency table in the reference.
- **Re-authenticate on `-1`/`-44116`** — the token/session invalidates after a site copy/import or a permission change.
