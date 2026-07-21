# Phase F1 gate

## Decision

```text
PHASE_F2_ALLOWED = true
```

The live prerequisites for implementing Etherlighting brightness as the sole productive write capability are satisfied for the exact captured compatibility tuple.

| Gate | Evidence | Result |
|---:|---|---|
| 1 | Five-stage brightness validator and restored initial state | PASS |
| 2 | UI `min=1` | PASS |
| 3 | UI `max=100` | PASS |
| 4 | Effective UI step `1`, confirmed by the real 30 → 31 → 30 sequence | PASS |
| 5 | `GET /proxy/network/v2/api/info`, `$.version` | PASS |
| 6 | `POST /api/auth/login` | PASS |
| 7 | Session cookie name `TOKEN` | PASS |
| 8 | `X-CSRF-Token` from a response header | PASS |
| 9 | UI-triggered authenticated `GET /proxy/network/api/s/site_001/stat/device`, HTTP 200 | PASS |
| 10 | Sanitized fixtures and reports contain no secret values | PASS |
| 11 | No alternate, legacy, or inferred endpoint was used | PASS |
| 12 | UniFi OS / Network `10.5.62` / model `USWED72` / firmware `7.4.1.16850` | PASS |

## Locked scope for Phase F2

The gate permits only the following productive capability:

- `ether_lighting.brightness`

The exact supported UI contract is minimum 1, maximum 100, step 1, unit `%`.

All other capabilities remain locked:

- `behavior`: candidate
- `mode`: candidate
- `enabled`: candidate
- `network_color`: candidate
- `port_control`: unsupported

Phase F2 must continue to use only these confirmed paths:

- Login: `POST /api/auth/login`
- Logout: `POST /api/auth/logout`
- Network version: `GET /proxy/network/v2/api/info`
- Device read: `GET /proxy/network/api/s/{site}/stat/device`
- Device write: `PUT /proxy/network/api/s/{site}/rest/device/{device}`

No setup or polling operation may write. Every brightness write must be constructed from a fresh Device read, sent once, and independently verified by another Device read.
