# Kompatibilität

| Controller | Network App | Device-Typ | Modell | Firmware | Read-Support | Write-Support | Write-ready |
|---|---|---|---|---|---|---|---|
| UniFi OS | `10.5.62` | `usw` | `USWED72` | `7.4.1.16850` | `brightness`, `behavior`, `mode`, `network_color`, `speed_color` | `confirmed` | ja |

Die Prüfung verwendet einen exakten `ControllerCompatibilityKey`. Es gibt keine Wildcards für Network 10.x, Firmware 7.x, Modellfamilien oder ähnlich benannte Switches.

Zusätzlich zur exakten Version muss das aktuelle Device-Objekt die bestätigten Werte für `brightness`, `behavior`, `mode` und `led_mode` sowie alle übrigen UI-Payload-Felder mit dem erwarteten Typ enthalten. Nur `lcm_night_mode_enabled` darf fehlen; dann greift ausschließlich der bestätigte UI-Initialwert `false`.

Weiterhin gesperrt:

- `enabled`: `candidate`
- `port_control`: `unsupported`
