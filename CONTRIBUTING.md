# Contributing

Thank you for helping improve UniFi Etherlighting.

## Before opening an issue

- Install the latest release.
- Restart Home Assistant after updating through HACS.
- Download the integration diagnostics.
- Check whether the issue is a credential, permission, unsupported API
  generation or schema-contract problem.

Never attach raw HAR files, controller responses or Home Assistant storage
files. Remove controller addresses, usernames, passwords, Site and Device IDs,
cookies, session values, CSRF values and tokens.

## Development

Use a feature branch and keep controller-specific data out of fixtures.

```bash
uv run --with-requirements requirements_test.txt pytest -q
uv run --with 'ruff>=0.11.0' ruff check .
python3 tools/validate_capture_sequence.py captures/brightness
python3 tools/validate_control_capture.py captures/controls/live_validation.json
python3 tools/validate_color_capture.py captures/colors/live_validation.json
```

Pull requests should include regression tests and document any newly supported
runtime contract. Never add guessed endpoints or automatic write retries.
