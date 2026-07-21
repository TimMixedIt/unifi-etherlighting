# Phase F1 gate

## Decision

```text
PHASE_F2_ALLOWED = true
```

The reversible UI sequence and the source of every UI write field are confirmed. The one field absent from the Device read has a live-confirmed Network UI initialization rule.

| Gate | Evidence | Result |
|---:|---|---|
| 1 | Five-stage brightness validator and restored initial state | PASS |
| 2 | UI `min=1` | PASS |
| 3 | UI `max=100` | PASS |
| 4 | Effective UI step `1`, confirmed by the real 30 → 31 → 30 sequence | PASS |
| 5 | `GET /proxy/network/v2/api/info`, `$.system.version` | PASS |
| 6 | `POST /api/auth/login` | PASS |
| 7 | Session cookie name `TOKEN` | PASS |
| 8 | `X-CSRF-Token` from a response header | PASS |
| 9 | UI-triggered authenticated `GET /proxy/network/api/s/site_001/stat/device`, HTTP 200 | PASS |
| 10 | Sanitized fixtures and reports contain no secret values | PASS |
| 11 | No alternate, legacy, or inferred endpoint was used | PASS |
| 12 | UniFi OS / Network `10.5.62` / model `USWED72` / firmware `7.4.1.16850` | PASS |

## Locked productive scope

The gate permits only `ether_lighting.brightness`. The confirmed UI contract is
minimum 1, maximum 100, step 1, unit `%`.

- `brightness`: confirmed, write-ready=true
- `behavior`: candidate
- `mode`: candidate
- `enabled`: candidate
- `network_color`: candidate
- `port_control`: unsupported

Only the following confirmed paths may be used:

- Login: `POST /api/auth/login`
- Logout: `POST /api/auth/logout`
- Network version: `GET /proxy/network/v2/api/info`
- Device read: `GET /proxy/network/api/s/{site}/stat/device`
- Device write: `PUT /proxy/network/api/s/{site}/rest/device/{device}`

Setup and polling remain read-only. The Number entity may call only the verified
Brightness service, which performs an exact compatibility check, a fresh Device
read, one Device PUT, and an independent read-back without automatic write retry.
