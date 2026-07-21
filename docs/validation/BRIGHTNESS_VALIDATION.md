# Etherlighting brightness validation

## Result

**Capability decision: `confirmed`, `reversible`, and write-ready**

The same signed-in Chrome session produced a complete UI-triggered read, forward write, independent read-back, reverse write, and final independent read. The original visible state was restored. No manually constructed controller request was used.

## Environment

| Item | Observed value |
|---|---|
| Capture date | 2026-07-21 |
| Controller type | `unifi_os` |
| Network Application version | `10.5.62` |
| Device type | `usw` |
| Switch model | `USWED72` |
| Switch firmware | `7.4.1.16850` |
| Capture source | `unifi_network_web_ui` |
| Session | `brightness_capture_001` |

The Network Application version was read from the Applications view in the same authenticated UniFi web interface. It was not inferred from the switch firmware.

## Confirmed sequence

| Stage | Method and sanitized path | Brightness | HTTP | UniFi status |
|---|---|---:|---:|---|
| Read before | `GET /proxy/network/api/s/site_001/stat/device` | 30 | 200 | `meta.rc = ok` |
| Write forward | `PUT /proxy/network/api/s/site_001/rest/device/device_001` | 30 → 31 | 200 | `meta.rc = ok` |
| Read after | `GET /proxy/network/api/s/site_001/stat/device` | 31 | 200 | `meta.rc = ok` |
| Write reverse | `PUT /proxy/network/api/s/site_001/rest/device/device_001` | 31 → 30 | 200 | `meta.rc = ok` |
| Read final | `GET /proxy/network/api/s/site_001/stat/device` | 30 | 200 | `meta.rc = ok` |

The confirmed semantic JSON path is `ether_lighting.brightness`. Both writes were caused by moving the real UI control by exactly one step and applying the change in the UniFi interface. Both independent reads were caused by normal UI navigation or reload activity.

## Invariants and side effects

Across all five captures:

- `ether_lighting.mode` remained `network`.
- `ether_lighting.behavior` remained `steady`.
- `ether_lighting.led_mode` remained `etherlighting`.
- The UI kept Network selected, Breathing Mode disabled, and Etherlighting active.
- The relevant projected device-configuration fields remained present.
- The forward and reverse request bodies had identical field sets.
- The only semantic difference between the two sanitized write bodies was `ether_lighting.brightness`.

No unexpected configuration side effect was detected. Controller revision and provisioning metadata changed as an expected consequence of saving and was treated as volatile rather than as a device-setting change.

## Sanitization

The write captures preserve every observed top-level request field and the complete observed `config_network` structure. Sensitive values were replaced in place: address values use `redacted`, the management-network reference uses `network_001`, and the device-name field uses `device_001`.

The controller responses were reduced to a target-device configuration projection. The following areas were removed without dropping Etherlighting or comparison-relevant configuration fields:

- address and hardware-address data;
- authentication material;
- internal names and nonessential identifiers;
- runtime statistics and telemetry;
- port runtime and link history;
- timestamps, uptime, temperatures, and traffic counters;
- controller revision and provisioning metadata.

Only header names were retained. No header values were stored. No raw HAR file or unredacted controller response was added to the project.

## Validation

Executed locally without network access or file mutation:

```text
python3 tools/validate_capture_sequence.py captures/brightness
```

Result: **PASS**

- All five brightness files and `environment.json` exist.
- Session and version context are identical.
- Pseudonyms and read/write paths are consistent.
- Forward write, independent target read, reverse write, and final original-value read all succeed.
- Exactly one semantic Etherlighting path changes.
- `mode`, `behavior`, and `led_mode` remain unchanged.
- Relevant projected fields remain present.
- The sensitive-data scan passes.

## Capability decision

The reversible UI sequence remains confirmed. A later source inspection established that `lcm_night_mode_enabled`, which the UI sent but the Device read omitted, is explicitly initialized by the Network UI to `false` when absent and otherwise preserved. The complete write configuration is therefore reproducible without an invented value for this exact compatibility tuple.

The Number entity uses the verified Brightness service. Writes remain single-shot,
version-bound, full-payload, independently read back, and non-retrying.
