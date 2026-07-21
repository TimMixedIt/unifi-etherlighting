# Test-user Network-version response validation

## Result

The temporary local UniFi test account triggered the real UniFi Network web UI request `GET /proxy/network/v2/api/info` in a separate Chrome Incognito session. The administrator browser session was not modified.

| Property | Observed value |
|---|---|
| HTTP status | `200` |
| JSON root type | `object` |
| Top-level `self` | `object` |
| Top-level `sites` | `array` |
| Top-level `system` | `object` |
| Confirmed version path | `$.system.version` |
| Version type | `string` |
| Confirmed Network version | `10.5.62` |

The root path `$.version` was not present in this test-user response. The existing controller adapter therefore raised `UniFiSchemaError` even though login and the HTTP request succeeded.

## Relevant observed header names

- `Content-Type`
- `X-CSRF-Token`
- `X-Updated-CSRF-Token`

Header values were discarded.

## Security boundary

Only the root type, top-level field names and types, version-named path and type, confirmed Network version, HTTP status, and relevant header names were retained. Values and nested contents of `self`, `sites`, and `system` were not stored, except for the explicitly confirmed Network version. No host, IP address, user information, identifier, Cookie, token, CSRF value, request body, response body, or raw HAR was persisted.

The capture was read-only. No Controller, Device, or Etherlighting write was triggered.
