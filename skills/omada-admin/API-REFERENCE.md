# Omada API Reference

All Web API v2 paths are relative to:
`$OMADA_URL/$OMADA_OMADAC_ID/api/v2/sites/$OMADA_SITE_ID`

All OpenAPI v1 paths are relative to:
`$OMADA_URL/openapi/v1/$OMADA_OMADAC_ID` (site-scoped ones need `/sites/$OMADA_SITE_ID` appended)

Verification status below is against controller firmware 6.2.14.12 / API v3 — a different firmware may differ. Anything not marked "verified" is a documented guess (from the Omada web UI's own request bodies) that has not been fire-tested; confirm with a `GET` before relying on it, and never `PATCH`/`POST` an unverified body against a production network without a dry-run read first.

---

## Networks / VLANs

### Web API v2 — verified schema

`GET /setting/lan/networks?currentPage=1&currentPageSize=100`

Real response fields (differ substantially from what the web UI's create form suggests): `id`, `site`, `name`, `purpose` (`"interface"`), `interfaceIds`, `vlanType`, `vlan` (not `vlanId`), `application`, `isolation`, `gatewaySubnet` (combined `"192.168.0.1/24"`, not separate `subnet`+`cidr`), `dhcpSettings: {enable, ipaddrStart, ipaddrEnd, ipRangePool, dhcpns, leasetime, options}`, `domain`, `igmpSnoopEnable`, `resource`, `deviceType`, `state`, `totalIpNum`, `dhcpServerNum`, `subnetOverrideEnable`, `interface`, `primary`.

`PATCH /setting/lan/networks/{networkId}` — full object required; read first, keep every field, only change what's needed.

### OpenAPI v1 — verified, different endpoint and schema

`GET /sites/{siteId}/lan-networks?page=1&pageSize=100` (kebab-case; this is a *different* resource from the Web API one above, not an alias for it)

Response fields: `id`, `name`, `purpose`, `interfaceIds`, `vlanType`, `vlan`, `application`, `gatewaySubnet`, `dhcpSettingsVO`, `domain`, `igmpSnoopEnable`, `mldSnoopEnable`, `dhcpL2RelayEnable`, `dhcpGuard`, `dhcpv6Guard`, `portal`, `accessControlRule`, `rateLimit`, `lanNetworkIpv6Config`, `allLan`, `qosQueueEnable`, `primary`.

---

## Clients — reading and DHCP reservations

`GET /insight/clients?currentPage=1&currentPageSize=200` — every client the controller has ever seen (online and offline). Prefer this over OpenAPI's `clients`, which only lists currently-active ones — an offline device's existing reservation would be silently missed.

`GET /clients/{mac}` — full detail, including `ipSetting` (the DHCP reservation):

```json
"ipSetting": {"useFixedAddr": true, "netId": "...", "ip": "192.168.0.171", "serverType": "gateway", "serverMac": "..."}
```

`PATCH /clients/{mac}` with body `{"ipSetting": {...}}` — **verified working**, full walkthrough in `SKILL.md`'s "Recipe: read or change a DHCP reservation".

---

## SSIDs (unverified payloads — confirm with a GET before writing)

Two-level hierarchy: WLAN Groups → SSIDs.

- List WLAN Groups: `GET /setting/wlans?currentPage=1&currentPageSize=100`
- List SSIDs: `GET /setting/wlans/{wlanGroupId}/ssids`
- Create: `POST /setting/wlans/{wlanGroupId}/ssids`
- Modify: `PATCH /setting/wlans/{wlanGroupId}/ssids/{ssidId}` — full object, strip read-only fields (`id`, `idInt`, `index`, `site`, `resource`, `vlanEnable`, `portalEnable`, `accessEnable`)
- Delete: `DELETE /setting/wlans/{wlanGroupId}/ssids/{ssidId}`

Field values (stable across schema changes — these are UI-documented constants, not guessed field names):
- `band`: bitmask — `1`=2.4G, `2`=5G, `3`=both
- `security`: `0`=open, `3`=WPA2/WPA3 (never `2` on creation — fails)
- `vlanSetting.mode`: `0`=group default, `1`=custom VLAN

### SSID override per AP

**Must use `PUT /eaps/{mac}/config/wlans`** — PATCH silently ignores `ssidOverrides`. Body needs `wlanId` + a `ssidOverrides` array; each override's `enable` must be `false` (`true` causes a spurious "SSID name already exists" error), `ssidEnable` controls whether it broadcasts on that specific AP.

---

## Firewall ACLs (unverified payloads — confirm with a GET before writing)

`GET /setting/firewall/acls?type=0&currentPage=1&currentPageSize=100`
`POST /setting/firewall/acls`

Field values:
- `policy`: `0`=deny, `1`=permit
- `protocols`: `[6]`=TCP, `[17]`=UDP, `[1]`=ICMP — always list explicitly, an empty `protocols: []` is unreliable
- `sourceType`/`destinationType`: `0`=network, `2`=IP/port group
- `type`: `0`=gateway ACL, `switch`=switch ACL, `eap`=AP ACL

IP/Port groups (for port-based filtering in ACLs): `POST /setting/firewall/ipGroups`, body has `ipList: [{ip, portList}]` — ports are strings, ranges use a hyphen (`"7000-7100"`).

OpenAPI v1's `sites/{siteId}/firewall` is a **different** resource — connection-timeout tuning (`tcpEstablished`, `icmp`, `synCookies`, …), not ACL rules.

---

## mDNS Reflector (unverified payload — confirm with a GET before writing)

`GET /setting/service/mdns` / `PATCH /setting/service/mdns` (full object).

- `type`: `1`=gateway (OSG), `0`=AP rule
- `profileIds`: `"buildIn-1"`=AirPlay
- Limits: 20 OSG rules, 16 AP rules

---

## Access Points (EAPs)

`GET /eaps/{mac}` — verified read.

`PATCH /eaps/{mac}` (radio/RSSI, unverified payload) — full object required, sets `radioSetting2g`/`radioSetting5g`/`rssiSetting2g`/`rssiSetting5g`.

Frequency → channel (stable reference table):

| Band | Ch | MHz |
|---|---|---|
| 2.4G | 1 | 2412 |
| 2.4G | 6 | 2437 |
| 2.4G | 11 | 2462 |
| 5G | 36 | 5180 |
| 5G | 52 | 5260 |
| 5G | 100 | 5500 |
| 5G | 132 | 5660 |
| Auto | — | 0 |

Channel is set via `freq` (MHz), not `channel`. TX power ranges (EAP650): 2.4G = 7–20 dBm, 5G = 7–28 dBm.

---

## Switches (unverified write payloads — confirm with a GET before writing)

- List ports: `GET /switches/{mac}/ports`
- Modify port: `PATCH /switches/{mac}/ports/{portNumber}` — full object, strip `portStatus`/`portCap` (read-only)
- Port profiles: `GET /setting/lan/profiles`, `POST /setting/lan/profiles`

Trunk profile notes: needs `nativeNetworkId` (a profile without one cannot be assigned to a port), and `nativeNetworkId` must not also appear in `tagNetworkIds`.

---

## Devices

`GET /devices?currentPage=1&currentPageSize=100` — verified.

`POST /cmd/devices/adopt` — body `{"mac":"AA-BB-CC-DD-EE-FF"}`; retry after 10–30s if the device isn't discovered yet (status 20).

---

## OpenAPI v1 endpoints — verified vs. not found

Verified working (firmware 6.2.14.12):

| Endpoint | Scope | Notes |
|---|---|---|
| `GET /sites?page=1&pageSize=N` | top-level (no siteId) | list sites |
| `GET /sites/{siteId}/clients?page=1&pageSize=N` | site | active clients only — see the reservation recipe above for why `insight/clients` on Web API v2 is preferred |
| `GET /sites/{siteId}/devices?page=1&pageSize=N` | site | |
| `GET /sites/{siteId}/lan-networks?page=1&pageSize=N` | site | own schema, see Networks section above |
| `GET /sites/{siteId}/firewall` | site | connection-timeout settings, not ACLs |

**Not found under any tried name** (all returned `-1600 Unsupported request path`, tried both camelCase and kebab-case: `networks`, `ssids`, `wlan-groups`, `firewall-rules`, `switches`, `switch-ports`, `wlans`, `eaps`, `aps`, `ap`, `eap`, `acl`, `acl-rules`, `gateway-acls`, `port-forwarding`, `port-forwardings`, `gateways`): SSIDs, firewall ACLs, switches, APs. This is evidence about the *names tried*, not proof OpenAPI v1 lacks the capability — but until a working name turns up, use Web API v2 for these.

---

## Error codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `-1` | Session expired — re-auth |
| `-1001` | Invalid/incomplete request parameters (right path, bad/missing params) |
| `-1600` | Unsupported request path (wrong path) |
| `-30109` | Invalid credentials |
| `-44116` | OpenAPI auth failed |
| `-7131` | Controller ID not found |

`-1001` vs `-1600` is a useful discriminator when probing an unknown endpoint name: `-1001` means the path exists but the query is malformed (add pagination params); `-1600` means the path itself is wrong.
