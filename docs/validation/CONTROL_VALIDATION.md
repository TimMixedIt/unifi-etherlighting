# Breathing- und Mode-Validierung

Capture: 21. Juli 2026, echte lokale UniFi-Network-Weboberfläche, dieselbe angemeldete Browser-Sitzung wie die bestätigte Geräteumgebung.

| Merkmal | Bestätigter Wert |
|---|---|
| Controller | UniFi OS |
| Network Application | `10.5.62` |
| Switch-Modell | `USWED72` |
| Switch-Firmware | `7.4.1.16850` |
| Read | `GET /proxy/network/api/s/{site}/stat/device` |
| Write | `PUT /proxy/network/api/s/{site}/rest/device/{device}` |
| Behavior-Sequenz | `steady → breath → steady` |
| Mode-Sequenz | `network → speed → network` |
| Write-Status | jeweils HTTP 200, `meta.rc = ok` |

Für jeden Hin- und Rückweg wurde die Einstellung in der echten UI geändert und mit **Apply Changes** ausgelöst. Nach jedem Hinweg und am Ende wurde die Seite neu geladen und die Einstellung erneut geöffnet. Die unabhängigen Reads bestätigten den Zielwert und anschließend den wiederhergestellten Ausgangswert.

In beiden Sequenzen änderte sich fachlich exakt ein Pfad:

- `ether_lighting.behavior` für Breathing;
- `ether_lighting.mode` für Speed/Network.

`brightness`, das jeweils andere Steuerfeld und `led_mode` blieben unverändert. Die Helligkeit blieb bei 30, der finale Zustand ist Network mit ausgeschaltetem Breathing. Farben und Port-Einstellungen wurden nicht verändert.

## Sicherheitsprüfung

Die Repository-Evidenz enthält ausschließlich relative pseudonymisierte Pfade, Methoden, Headernamen, Statuswerte und die vier nicht sensiblen Etherlighting-Steuerfelder. Sie enthält keine Hosts, Adressen, internen Namen, realen IDs, Cookies, Sessionwerte, CSRF-Werte, Zugangsdaten oder Roh-Captures. Es wurden keine Requests manuell konstruiert und keine Controllerdaten übertragen.

## Entscheidung

- `behavior`: **confirmed**, Evidenz `reversible`;
- `mode`: **confirmed**, Evidenz `reversible`;
- Netzwerkfarben und Portfarben: unverändert `candidate` beziehungsweise `unsupported`.

Der Offline-Validator wird ausgeführt mit:

```bash
python3 tools/validate_control_capture.py captures/controls/live_validation.json
```
