# Compatibility

## Runtime profile

The production gate is `unifi_os_network_v10`.

| Check | Requirement |
|---|---|
| Controller | UniFi OS |
| Network version | 10.5.62 or newer (no upper bound) |
| Device identity | `type=usw`, non-empty Device ID, model and firmware |
| Etherlighting reads | valid `brightness`, `behavior`, `mode`, `led_mode` |
| Device write source | all UI-observed top-level and `config_network` fields present |
| Colors | complete validated settings schema plus compatible witness Device |

The Network version is parsed, not compared as an opaque string. Patch, minor and major updates are accepted only after the live response and
Device contract pass. Model and firmware values are reported for diagnostics,
but are not used as brittle equality gates.

## Live-validated environments

| Network App | Device type | Model | Firmware | Result |
|---:|---|---|---|---|
| 10.5.62 | `usw` | USWED72 | 7.4.1.16850 | reversible controls and colors |
| 10.5.66 | `usw` | USWED72 | 7.4.1.16850 | reversible post-update validation |

## Reading the setup error

If setup stops with "No switch exposes the complete supported Etherlighting API
contract", the message lists, per switch model, every contract check that
failed, for example `USPXG10: ether_lighting.led_mode, lcm_orientation_override`.
The entries are fixed field names from this integration, never controller
values, so the line can be pasted into a GitHub issue as is. `ether_lighting`
alone means the switch reports no Etherlighting configuration; a `lcm_*`,
`config_network.*` or `snmp_*` entry means the Device object lacks a field the
UniFi UI sends when it writes the Etherlighting settings.

## Fail-closed behavior

- A malformed version or Network version below 10.5.62 is unsupported.
- A newer Network major is accepted only while the complete Device and
  settings schema still matches; any deviation disables the affected controls.
- A missing/changed read field disables that capability.
- A missing full-write field keeps the readable value but disables its write.
- A changed color/settings schema disables color entities.
- A failed or ambiguous write is not retried and blocks subsequent writes.

The integration therefore survives compatible routine updates without claiming
that every future UniFi API is automatically safe.
