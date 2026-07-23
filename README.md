# UniFi Etherlighting for Home Assistant

[![Tests](https://github.com/TimMixedIt/unifi-etherlighting/actions/workflows/tests.yml/badge.svg)](https://github.com/TimMixedIt/unifi-etherlighting/actions/workflows/tests.yml)
[![Home Assistant validation](https://github.com/TimMixedIt/unifi-etherlighting/actions/workflows/validate.yml/badge.svg)](https://github.com/TimMixedIt/unifi-etherlighting/actions/workflows/validate.yml)
[![HACS validation](https://github.com/TimMixedIt/unifi-etherlighting/actions/workflows/hacs.yml/badge.svg)](https://github.com/TimMixedIt/unifi-etherlighting/actions/workflows/hacs.yml)

Local, HACS-compatible Home Assistant integration for verified UniFi
Etherlighting controls. It supports:

- Brightness as a `number` entity.
- Breathing mode as a `switch` entity.
- Network/Speed mode as a `select` entity.
- One native RGB color picker per VLAN/network.
- Native RGB color pickers for FE, GbE, 2.5GbE, 5GbE and 10GbE.

No UniFi Cloud connection, SSH access, external telemetry or raw API service is
used.

## Safe controller-update support

The integration is not pinned to one exact Network patch version, switch model
or firmware build. Runtime compatibility is established using two independent
gates:

1. The Network Application must use the supported UniFi Network 10 API
   generation, starting at 10.5.62.
2. Every selected switch must expose the complete validated Etherlighting read
   and write schema at runtime.

Normal Network 10 patch and minor updates therefore keep working when the live
API contract is unchanged. A future Network API major or a changed/missing
schema fails closed: values may remain diagnostic, writes are disabled and a
Home Assistant Repair explains the safe reason.

This is intentionally stricter than blindly accepting every future response,
while avoiding the former `10.5.62` equality check that broke on routine
updates.

## Write safety

Before every Device write the integration:

1. Re-reads the Network version and complete Device object.
2. Validates the current runtime contract.
3. Builds the full UI-observed payload from the current Device state.
4. Changes exactly one allowlisted Etherlighting value.
5. Sends the request exactly once.
6. Validates HTTP success, `meta.rc`, response state and an independent read.

Color writes preserve both complete override arrays, change one color, perform
the UI-observed no-op Device refresh and independently verify both resources.
Writes are never retried automatically. An indeterminate result blocks further
writes for the affected Device or Site.

## Installation

### HACS custom repository

[![Open your Home Assistant instance and add this repository to HACS.](https://my.home-assistant.io/badges/hacs_repository.svg)](https://my.home-assistant.io/redirect/hacs_repository/?owner=TimMixedIt&repository=unifi-etherlighting&category=integration)

1. Add this repository to HACS as an Integration repository.
2. Install the latest release.
3. Restart Home Assistant.
4. Go to **Settings → Devices & services → Add integration**.
5. Select **UniFi Etherlighting**.

Use a dedicated local UniFi account with access to the Network application and
the selected Site. Setup performs login and read-only validation; it never
performs a test write. Self-signed certificates require explicitly disabling
TLS certificate verification.

If credentials later expire or change, Home Assistant starts a reauthentication
flow instead of requiring the integration to be removed and recreated.

## Compatibility

Live validation currently covers:

| Controller | Network Application | Device type | Model | Firmware |
|---|---:|---|---|---|
| UniFi OS | 10.5.62 | `usw` | USWED72 | 7.4.1.16850 |
| UniFi OS | 10.5.66 | `usw` | USWED72 | 7.4.1.16850 |

The table records environments that received a reversible live test. It is not
an exact allowlist. Other Network 10 releases and Etherlighting switches are
accepted only when the complete runtime contract passes.

Not supported:

- Per-port Etherlighting or port configuration.
- Raw API services.
- Changing the Etherlighting activation field.
- UniFi Cloud login.

See [Compatibility](docs/COMPATIBILITY.md) and
[Security model](docs/SECURITY_MODEL.md) for the full policy.

## Troubleshooting

Download diagnostics from **Settings → Devices & services → UniFi
Etherlighting** and attach them to a bug report. Diagnostics are allowlist-based
and omit controller addresses, usernames, passwords, Site and Device IDs,
cookies, session values, CSRF values, payloads and full responses.

Useful status fields:

- `compatibility_profile`
- `network_api_generation_supported`
- `contract_compatible_device_count`
- `controller_status`
- `last_error_code`
- per-capability `read_supported`, `write_supported` and `write_ready`

Please use the repository's
[bug report form](https://github.com/TimMixedIt/unifi-etherlighting/issues/new/choose)
for regressions after a UniFi update.

## Development

```bash
python3 tools/validate_capture_sequence.py captures/brightness
python3 tools/validate_control_capture.py captures/controls/live_validation.json
python3 tools/validate_color_capture.py captures/colors/live_validation.json
python3 tools/validate_update_compatibility.py captures/update_compatibility/live_validation.json
uv run --with-requirements requirements_test.txt pytest -q
uv run --with 'ruff>=0.11.0' ruff check .
```

Captures in this repository are pseudonymized projections. Never submit raw HAR
files, credentials, cookies, tokens, controller addresses, Site IDs, Device IDs
or unredacted diagnostics.

See [CONTRIBUTING.md](CONTRIBUTING.md) and [SECURITY.md](SECURITY.md).
