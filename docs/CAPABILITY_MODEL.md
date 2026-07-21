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
| `brightness` | confirmed | reversible | `number` |
| `behavior` | candidate | write_accepted | keine |
| `mode` | candidate | captured | keine |
| `enabled` | candidate | captured | keine |
| `network_color` | candidate | captured | keine |
| `port_control` | unsupported | unknown | keine |

Die erfolgreiche Device-PUT-Route bleibt selbst eine technische Candidate-Evidenz und wird nicht als Raw-API-Capability veröffentlicht.

Brightness wird in drei unabhängige Zustände getrennt:

```text
brightness_read_supported=true
brightness_write_supported=confirmed
brightness_write_ready=true
```

Alle vom UI-Write verwendeten Werte stammen entweder aus dem bestätigten Device-Read oder aus der live bestätigten UI-Forminitialisierung für `lcm_night_mode_enabled`. Ein vorhandener boolescher Wert wird bewahrt; nur bei Abwesenheit wird wie in der UI `false` initialisiert.
