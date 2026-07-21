# Phase F1 gate

## Decision

```text
PHASE_F2_ALLOWED = false
```

The original reversible UI sequence remains valid evidence, but the later productive test showed that the confirmed Device read does not expose the complete UI write configuration. Productive writes are therefore superseded and blocked pending a separate field-source capture.

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

## Superseded Phase F2 scope

The earlier gate permitted only `ether_lighting.brightness`. That permission is now
superseded by the incomplete write-configuration finding. The UI contract remains
minimum 1, maximum 100, step 1, unit `%`, but it is read-only in version 0.2.5.

All write capabilities are locked:

- `brightness`: candidate, write-ready=false
- `behavior`: candidate
- `mode`: candidate
- `enabled`: candidate
- `network_color`: candidate
- `port_control`: unsupported

The following paths remain evidence only:

- Login: `POST /api/auth/login`
- Logout: `POST /api/auth/logout`
- Network version: `GET /proxy/network/v2/api/info`
- Device read: `GET /proxy/network/api/s/{site}/stat/device`
- Device write: `PUT /proxy/network/api/s/{site}/rest/device/{device}`

No setup, polling, Number service, internal Brightness service, or Device adapter
operation may write. A future release requires a new explicit gate decision after
the complete UI write configuration has been confirmed from real reads.
