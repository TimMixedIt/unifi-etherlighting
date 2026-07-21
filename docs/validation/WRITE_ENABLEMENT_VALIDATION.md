# Brightness write enablement validation

## Decision

Version 0.2.6 enables verified Brightness writes only for the exact validated compatibility tuple.

```text
brightness_read_supported=true
brightness_write_supported=confirmed
brightness_write_ready=true
write_capability=ready
write_block_reason=null
missing_confirmed_fields=[]
```

## Previously missing field

The confirmed Device read omits `lcm_night_mode_enabled`. A DevTools search of the loaded Network Application resources found five matching lines in two bundles. The form code preserves a supplied boolean and initializes the field to `false` when absent. Both reversible UI writes contained that initialized boolean.

Production behavior is intentionally identical and narrow:

- preserve the current value when it exists and is boolean;
- use `false` only when the field is absent;
- reject null, strings, numbers, and every other type;
- provide no defaults for any other payload field;
- keep exact Network, model, and firmware matching;
- send once and verify through an independent Device read;
- never retry an ambiguous write automatically.

No raw source, bundle identifier, host, controller identifier, credential, Cookie, token, CSRF value, payload, or response body is stored in this report.
