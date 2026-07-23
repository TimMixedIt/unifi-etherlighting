# Verified Etherlighting read-modify-write

## Device controls

```text
ensure authenticated session
→ read Network version
→ validate supported API generation
→ read complete Device
→ validate capability and full write-source schema
→ validate requested value
→ project the UI-observed payload from current values
→ change exactly one semantic field
→ send one PUT
→ validate HTTP, meta.rc and response value
→ independently read Device
→ verify target value and preserved invariants
```

`build_etherlighting_write_payload()` does not send a minimal patch. It copies
only the top-level, `config_network` and Etherlighting fields observed in the
real Network UI write. Missing required fields stop the operation before a
request is sent.

Brightness is restricted to 1–100, behavior to `steady`/`breath` and mode to
`network`/`speed`.

## Color controls

```text
validate Network generation and witness Device contract
→ read complete Etherlighting settings
→ replace or append one override
→ send both complete override arrays once
→ validate settings response
→ send the UI-observed no-op Device refresh once
→ validate Device response
→ independently re-read settings and Device
→ verify target color and every preserved invariant
```

## Failure classification

- `applied`: target was independently read and invariants were preserved.
- `not_applied`: original value remained and invariants were preserved.
- `indeterminate`: the result or preservation could not be proven.

`indeterminate` blocks subsequent writes for the affected Device or Site. No
write path has an automatic retry.
