# Capability-Modell

`EvidenceLevel` beschreibt die Evidenzqualität: `unknown`, `model_only`, `captured`, `write_accepted`, `read_verified`, `reversible`. `CapabilityState` beschreibt die Produktfreigabe: `candidate`, `confirmed`, `unsupported`.

Der einzige Confirmed-Schlüssel lautet:

```text
controller_type=unifi_os
network_application_version=10.5.62
device_model=USWED72
device_firmware=7.4.1.16850
```

| Capability | State | Evidence | Produktive Entität |
|---|---|---|---|
| `brightness` | confirmed | reversible | `number` |
| `behavior` | candidate | write_accepted | keine |
| `mode` | candidate | captured | keine |
| `enabled` | candidate | captured | keine |
| `network_color` | candidate | captured | keine |
| `port_control` | unsupported | unknown | keine |

Die erfolgreiche Device-PUT-Route bleibt selbst eine technische Candidate-Evidenz und wird nicht als Raw-API-Capability veröffentlicht.
