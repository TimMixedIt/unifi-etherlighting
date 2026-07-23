# Compatibility

## Runtime profile

The production gate is `unifi_os_network_v10`.

| Check | Requirement |
|---|---|
| Controller | UniFi OS |
| Network API generation | major 10, version 10.5.62 or newer |
| Device identity | `type=usw`, non-empty Device ID, model and firmware |
| Etherlighting reads | valid `brightness`, `behavior`, `mode`, `led_mode` |
| Device write source | all UI-observed top-level and `config_network` fields present |
| Colors | complete validated settings schema plus compatible witness Device |

The Network version is parsed, not compared as an opaque string. Patch and
minor updates inside Network 10 are accepted only after the live response and
Device contract pass. Model and firmware values are reported for diagnostics,
but are not used as brittle equality gates.

## Live-validated environments

| Network App | Device type | Model | Firmware | Result |
|---:|---|---|---|---|
| 10.5.62 | `usw` | USWED72 | 7.4.1.16850 | reversible controls and colors |
| 10.5.66 | `usw` | USWED72 | 7.4.1.16850 | reversible post-update validation |

## Fail-closed behavior

- A malformed version or Network version below 10.5.62 is unsupported.
- A future Network major is unsupported until its API contract is validated.
- A missing/changed read field disables that capability.
- A missing full-write field keeps the readable value but disables its write.
- A changed color/settings schema disables color entities.
- A failed or ambiguous write is not retried and blocks subsequent writes.

The integration therefore survives compatible routine updates without claiming
that every future UniFi API is automatically safe.
