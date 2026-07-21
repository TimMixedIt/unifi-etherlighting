# Brightness write-lock validation

## Decision

Version 0.2.5 is an explicitly write-blocked diagnostic release.

```text
brightness_read_supported=true
brightness_write_supported=candidate
brightness_write_ready=false
write_capability=blocked
write_block_reason=confirmed_write_configuration_incomplete
missing_confirmed_fields=lcm_night_mode_enabled
```

The current Brightness value remains available from the confirmed read path. The Number entity and `BrightnessService.async_set_brightness()` independently block every write attempt before authentication, Network-version read, Device read, payload projection, or Device write.

The missing field is named because it is part of the confirmed UI write payload and was verified absent from the live `stat/device` response. No controller value, identifier, address, credential, Cookie, token, CSRF value, payload, or response body is retained.

The independent logout HTTP 403 warning does not change a successful read result and does not weaken the write lock.
