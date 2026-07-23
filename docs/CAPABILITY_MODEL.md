# Capability model

`EvidenceLevel` records how a controller behavior was established:
`unknown`, `model_only`, `captured`, `write_accepted`, `read_verified` or
`reversible`.

`CapabilityState` records the product decision: `candidate`, `confirmed` or
`unsupported`.

## Runtime decision

Historical captures remain tied to their exact controller/model/firmware
combination. Production support is derived separately from:

```text
supported Network API generation
+ live field types and allowed values
+ complete UI-observed write-source schema
+ central write release gate
```

This produces independent states such as:

```text
brightness_read_supported=true
brightness_write_supported=confirmed
brightness_write_ready=true
```

A readable field may remain available while its write is disabled because a
different required payload field disappeared.

| Capability | Required live contract | Product entity |
|---|---|---|
| `brightness` | integer 1–100 | `number` |
| `behavior` | `steady` or `breath` | `switch` |
| `mode` | `network` or `speed` | `select` |
| `network_color` | validated settings and network-label schemas | `light` per network |
| `speed_color` | validated settings schema and visible speed key | `light` per speed |
| `enabled` | not independently validated | none |
| `port_control` | no evidence | none |

Network colors combine `network_defaults` with `network_overrides`. Speed
colors combine `speed_defaults` with `speed_overrides`; the productive keys are
FE, GbE, 2.5GbE, 5GbE and 10GbE.

`lcm_night_mode_enabled` is the only UI-observed write field allowed to be
absent from the Device read. The real Network UI preserves an existing boolean
and initializes a missing value to `false`; any other type fails closed.
