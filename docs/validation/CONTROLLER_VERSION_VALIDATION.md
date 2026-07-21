# Controller-version read validation

## Result

The Network Application version is available through a reproducible, read-only request made by the real UniFi Network web interface.

| Item | Confirmed value |
|---|---|
| Source | `unifi_network_web_ui` |
| Method | `GET` |
| Sanitized path | `/proxy/network/v2/api/info` |
| Query | none |
| HTTP status | 200 |
| JSON path | `$.version` |
| Network Application version | `10.5.62` |
| Configuration mutation | none |

## Reproduction

The Network log was cleared and the real Control Plane Updates view was reloaded normally. The no-query request was issued again by the UI and returned the version displayed in the Applications table.

A second UI request to the same resource included volatile UI-preference query data. It is not required for reading the version and is deliberately excluded from the confirmed implementation contract. No query parameters were inferred, copied, or retained.

## Request and response contract

Observed request header names required by the authenticated browser flow:

- `Accept`
- `Cookie`

Observed response header names relevant to the integration:

- `Content-Type`
- `X-CSRF-Token`

Only names are retained. Header values are not stored.

The response fixture is a sanitized projection containing only:

```json
{
  "version": "10.5.62"
}
```

The full response also contained controller, UI, runtime, naming, addressing, and identifier data. Those areas were removed. The runtime version contract is limited to a non-empty string at `$.version`.

## Security decision

- The request is read-only and was caused by the real UI.
- No host, address, hardware address, internal name, user data, Cookie value, or CSRF value is retained.
- No alternate or legacy version endpoint was tried.
- No version is inferred from switch firmware or user input.

**Controller-version read: confirmed for Network Application `10.5.62`.**
