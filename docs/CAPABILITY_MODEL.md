# Capability-Modell

`EvidenceLevel` beschreibt die Evidenzqualität: `unknown`, `model_only`, `captured`, `write_accepted`, `read_verified`, `reversible`. `CapabilityState` beschreibt die Produktfreigabe: `candidate`, `confirmed`, `unsupported`.

Der exakte Read-Support-Schlüssel lautet:

```text
controller_type=unifi_os
network_application_version=10.5.62
device_model=USWED72
device_firmware=7.4.1.16850
```

| Capability | State | Evidence | Produktive Entität |
|---|---|---|---|
| `brightness` | candidate | reversible | `number` (read-only) |
| `behavior` | candidate | write_accepted | keine |
| `mode` | candidate | captured | keine |
| `enabled` | candidate | captured | keine |
| `network_color` | candidate | captured | keine |
| `port_control` | unsupported | unknown | keine |

Die erfolgreiche Device-PUT-Route bleibt selbst eine technische Candidate-Evidenz und wird nicht als Raw-API-Capability veröffentlicht.

Brightness wird in drei unabhängige Zustände getrennt:

```text
brightness_read_supported=true
brightness_write_supported=candidate
brightness_write_ready=false
```

Die reversible UI-Beobachtung bestätigt nicht, dass alle vom UI-Write verwendeten Felder aus dem produktiven Device-Read sicher rekonstruiert werden können. Deshalb kann Evidenz vorhanden sein, während die produktive Schreibbereitschaft gesperrt bleibt.
