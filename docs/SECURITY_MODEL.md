# Security model

- Only capture-confirmed login, logout, version, Device, settings and network
  configuration paths are implemented.
- Site and Device path parameters are URL-encoded.
- Credentials are used only for local login and are never logged.
- Session cookies and CSRF data remain in the dedicated in-memory HTTP session.
- Diagnostics are allowlist-based and exclude host, Site, Device IDs,
  credentials, payloads and complete responses.
- Config-flow logging contains only stage, safe category, exception type and an
  optional HTTP status.
- Setup, reauthentication validation and polling are read-only.
- Authentication failures start Home Assistant reauthentication.
- Compatible Network 10 updates are accepted only when the complete runtime
  API and Device schema still match.
- Unsupported API generations and changed schemas fail closed.
- One action changes exactly one allowlisted semantic value.
- Writes are sent once, never automatically retried and always followed by an
  independent read.
- An indeterminate result blocks later writes and creates a Repair.
- Color writes preserve both override arrays, change one color and validate the
  UI-observed no-op Device refresh.
- No SSH, UniFi Cloud login, port control, raw API service, telemetry or
  external debug upload exists.

A read may retry once after a 401/403 by establishing a new local session. A
write is never retried after an authentication error, timeout or disconnect;
the integration reads the resulting state and classifies it as `applied`,
`not_applied` or `indeterminate`.
