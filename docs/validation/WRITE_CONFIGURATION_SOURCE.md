# UI write-configuration source capture

## Result

The isolated UniFi Network browser capture completed the one-step reversible sequence `30 -> 31 -> 30`. The final value was independently read as 30. Mode remained `network`; behavior remained unchanged. Exactly two UI-triggered Device PUT requests occurred, both with HTTP 200. No manually constructed request was used.

The UI issued `GET /api/users/self` immediately before each PUT. That response is not a source for Device write fields. The Device configuration already loaded by the UI came from the confirmed `GET /proxy/network/api/s/site_001/stat/device` response (HTTP 200).

## Field-source decision

All observed write fields except one map by field name and type to the selected Device object below `$.data[*]` in `stat/device`. Nested Etherlighting fields map below `$.data[*].ether_lighting`; network configuration fields map below `$.data[*].config_network`.

`lcm_night_mode_enabled` was present in both UI-generated PUT payloads as a boolean but absent from the live `stat/device` Device object. A subsequent DevTools search of the loaded Network Application resources found five matching lines in two JavaScript bundles. Both form implementations explicitly preserve a supplied boolean and initialize the field to `false` when it is absent. This exactly explains the observed read/UI-write difference.

No bundle URL, hash, source file, or raw source text is retained. The documented behavior is limited to the field name, boolean type, result counts, and initialization semantics.

The complete machine-readable path mapping is stored in `captures/write_configuration_source/field_sources.json`. It contains methods, relative pseudonymized endpoints, statuses, field names, types, and JSON paths only.

## Safety and release consequence

- Separate browser session used: yes
- UI writes: exactly two
- Final brightness: 30
- Raw request or response retained: no
- Header values, Cookies, tokens, CSRF values, credentials, hosts, addresses, MACs, or controller identifiers retained: no
- Complete confirmed write configuration available: yes
- `brightness_read_supported`: true
- `brightness_write_supported`: confirmed
- `brightness_write_ready`: true
- Release action: allow the verified Brightness read-modify-write flow for the exact compatibility tuple

The payload builder may mirror this confirmed UI behavior: preserve an existing boolean, initialize the field to `false` only when absent, and fail closed for any other type. This does not authorize defaults for any other field or capability.
