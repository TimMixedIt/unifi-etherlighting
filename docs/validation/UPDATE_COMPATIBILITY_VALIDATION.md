# UniFi update compatibility validation

## Result

Version 0.5.0 passed a reversible live validation after the UniFi Network
Application changed from 10.5.62 to 10.5.66.

| Item | Observed result |
|---|---|
| Controller | UniFi OS |
| Runtime profile | `unifi_os_network_v10` |
| Network API generation | supported |
| Compatible selected Devices | 1 |
| Integration status | online |
| Product entities | 19 |
| Write capability | ready |
| Blocking errors | none |

The switch type, model and firmware were unchanged. The complete runtime Device
contract passed; compatibility was not inferred from the version number alone.

## Reversible control checks

Each action was invoked through its native Home Assistant entity. The
integration performed its normal pre-write read, single write and independent
read-back verification.

| Capability | Forward | Independent read | Reverse | Final |
|---|---|---|---|---|
| Brightness | 30 → 31 | 31 | 31 → 30 | 30 |
| Mode | network → speed | speed | speed → network | network |
| Behavior | steady → breath | breath | breath → steady | steady |
| Network color | one RGB channel changed | target RGB | original RGB restored | restored |
| Speed color | one RGB channel changed | target RGB | original RGB restored | restored |

Brightness, mode and behavior remained invariant during each unrelated
sequence. The tested network and speed colors were both restored. No write
block or integration error remained after the final reads.

## Security

The stored validation is a semantic projection only. It contains no controller
address, Site or Device identifier, account data, cookie or token value,
request/response body, absolute URL, MAC address or raw capture.

The offline update validator and the existing brightness, control and color
capture validators all passed.
