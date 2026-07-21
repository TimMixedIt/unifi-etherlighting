# UI write-configuration source capture

## Result

The isolated UniFi Network browser capture completed the one-step reversible sequence `30 -> 31 -> 30`. The final value was independently read as 30. Mode remained `network`; behavior remained unchanged. Exactly two UI-triggered Device PUT requests occurred, both with HTTP 200. No manually constructed request was used.

The UI issued `GET /api/users/self` immediately before each PUT. That response is not a source for Device write fields. The Device configuration already loaded by the UI came from the confirmed `GET /proxy/network/api/s/site_001/stat/device` response (HTTP 200).

## Field-source decision

All observed write fields except one map by field name and type to the selected Device object below `$.data[*]` in `stat/device`. Nested Etherlighting fields map below `$.data[*].ether_lighting`; network configuration fields map below `$.data[*].config_network`.

`lcm_night_mode_enabled` was present in both UI-generated PUT payloads as a boolean, but was not present in the live `stat/device` Device object and no UI-read response was confirmed as its source. Its source therefore remains unresolved. The field is not removed, invented, defaulted, or derived.

The complete machine-readable path mapping is stored in `captures/write_configuration_source/field_sources.json`. It contains methods, relative pseudonymized endpoints, statuses, field names, types, and JSON paths only.

## Safety and release consequence

- Separate browser session used: yes
- UI writes: exactly two
- Final brightness: 30
- Raw request or response retained: no
- Header values, Cookies, tokens, CSRF values, credentials, hosts, addresses, MACs, or controller identifiers retained: no
- Complete confirmed write configuration available: no
- `brightness_read_supported`: true
- `brightness_write_supported`: candidate
- `brightness_write_ready`: false
- Release action: keep the central production write lock enabled

This capture does not justify a payload-builder change. Version 0.2.5 remains an explicitly write-blocked diagnostic release.
