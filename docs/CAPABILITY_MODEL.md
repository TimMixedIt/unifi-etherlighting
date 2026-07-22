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
| `behavior` | confirmed | reversible | `switch` |
| `mode` | confirmed | reversible | `select` |
| `enabled` | candidate | captured | keine |
| `network_color` | confirmed | reversible | `light` pro Network/VLAN |
| `speed_color` | confirmed | reversible | `light` pro bestätigter Geschwindigkeit |
| `port_control` | unsupported | unknown | keine |

Die erfolgreiche Device-PUT-Route bleibt selbst eine technische Candidate-Evidenz und wird nicht als Raw-API-Capability veröffentlicht.

Jede produktive Steuerung wird in drei unabhängige Zustände getrennt:

```text
brightness_read_supported=true
brightness_write_supported=confirmed
brightness_write_ready=true
```

Dasselbe Modell gilt als `behavior_*`, `mode_*` und für die site-weiten Farbsteuerungen. Behavior akzeptiert ausschließlich `steady` und `breath`; Mode ausschließlich `network` und `speed`.

Network-Farben werden aus `network_defaults` plus `network_overrides` gebildet und über den bestätigten Network-Konfigurationsread benannt. Speed-Farben werden aus `speed_defaults` plus `speed_overrides` gebildet. Produktiv angeboten werden nur die fünf in der validierten Switch-Oberfläche sichtbaren Schlüssel `FE`, `GbE`, `2.5GbE`, `5GbE` und `10GbE`.

Alle vom UI-Write verwendeten Werte stammen entweder aus dem bestätigten Device-Read oder aus der live bestätigten UI-Forminitialisierung für `lcm_night_mode_enabled`. Ein vorhandener boolescher Wert wird bewahrt; nur bei Abwesenheit wird wie in der UI `false` initialisiert.
