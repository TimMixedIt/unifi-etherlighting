# Compatibility

## Runtime profile

The production gate is `unifi_os_network_v10`.

| Check | Requirement |
|---|---|
| Controller | UniFi OS |
| Network version | 10.5.62 or newer (no upper bound) |
| Device identity | `type=usw`, non-empty Device ID, model and firmware |
| Etherlighting reads | valid `brightness`, `behavior`, and `mode` |
| Device write source | valid read schema, `led_mode`, required companion fields and a recognized static/DHCP network shape |
| Colors | complete validated settings schema plus compatible witness Device |

The Network version is parsed, not compared as an opaque string. Patch, minor and major updates are accepted only after the live response and
Device contract pass. Model and firmware values are reported for diagnostics,
but are not used as brittle equality gates.

From 0.5.10, static networking requires all original IP/DNS companion fields.
DHCP requires `type=dhcp` and boolean `bonding_enabled`; IP/DNS companion fields
are projected only when present and are never filled with invented defaults.
The LCD group is optional only when every LCD field, including
`lcm_night_mode_enabled`, is absent. Partial or malformed LCD groups fail closed.
On an existing complete LCD group, the previously captured default for an absent
`lcm_night_mode_enabled` remains unchanged. Post-write reads must preserve the
network configuration and all present projected companion fields.

These shapes are based on the field-presence reports in issues #22 and #40 and
are tested with synthetic devices. They have not yet received reversible live
validation on those reporters' switches.

## Live-validated environments

| Network App | Device type | Model | Firmware | Result |
|---:|---|---|---|---|
| 10.5.62 | `usw` | USWED72 | 7.4.1.16850 | reversible controls and colors |
| 10.5.66 | `usw` | USWED72 | 7.4.1.16850 | reversible post-update validation |

## Reading the setup error

If setup stops with "No switch exposes the supported Etherlighting read
contract", the message lists, per switch model, every failed read check, for
example `USPXG10: ether_lighting.mode`. The entries are fixed field names from
this integration, never controller values, so the line can be pasted into a
GitHub issue as is. `ether_lighting` alone means the switch reports no
Etherlighting configuration. A switch that passes this read contract but lacks
the complete write source is offered as **read-only** instead: its current
state is visible, while every Etherlighting and color write stays disabled.

## Fail-closed behavior

- A malformed version or Network version below 10.5.62 is unsupported.
- A newer Network major is accepted when the bounded read schema still
  matches. Any incomplete full Device write source makes the affected switch
  read-only and disables color writes.
- A missing/changed read field disables that capability.
- A missing full-write field keeps the readable value but disables its write.
- A changed color/settings schema disables color entities.
- A failed or ambiguous write is not retried and blocks subsequent writes.

The integration therefore survives compatible routine updates without claiming
that every future UniFi API is automatically safe.
