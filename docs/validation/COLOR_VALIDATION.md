# Etherlighting-Farbvalidierung

## Ergebnis

Die VLAN-/Network- und Link-Speed-Farben sind für die exakt getestete Kombination als `confirmed` freigegeben. Beide Farbarten wurden über die echte UniFi-Network-Oberfläche geändert, unabhängig neu gelesen, auf den Ausgangswert zurückgesetzt und final erneut geprüft.

## Umgebung

- Capture-Datum: 2026-07-22
- Controller-Typ: UniFi OS
- Network Application: `10.5.62`
- Switch-Modell: `USWED72`
- Switch-Firmware: `7.4.1.16850`
- Capture-Quelle: UniFi Network Web UI

## Bestätigte Requests

| Aufgabe | Methode | Bereinigter Pfad | Ergebnis |
|---|---|---|---|
| Etherlighting-Farbeinstellungen lesen | `GET` | `/proxy/network/api/s/{site}/get/setting` | HTTP 200, `meta.rc=ok` |
| Network-Bezeichnungen lesen | `GET` | `/proxy/network/api/s/{site}/rest/networkconf` | HTTP 200, `meta.rc=ok` |
| Farb-Overrides speichern | `POST` | `/proxy/network/api/s/{site}/set/setting/ether_lighting` | HTTP 200, `meta.rc=ok` |
| UI-begleitenden Device-Refresh senden | `PUT` | `/proxy/network/api/s/{site}/rest/device/{device}` | HTTP 200, `meta.rc=ok` |

Die Oberfläche sendet beim Speichern einer Farbe zuerst den vollständigen Setting-Payload mit `key`, `network_overrides` und `speed_overrides`. Anschließend sendet sie den bereits bestätigten vollständigen Device-Payload, ohne `mode`, `brightness`, `behavior` oder `led_mode` fachlich zu verändern. Die produktive Implementierung bildet genau diese Reihenfolge nach.

## Reversible Sequenzen

| Capability | Ausgangswert | Testwert | Finalwert | Fachlicher Pfad |
|---|---:|---:|---:|---|
| Network-Farbe | `0544FF` | `0644FF` | `0544FF` | `network_overrides[*].raw_color_hex` |
| Speed-Farbe `FE` | `FFC105` | `FEC105` | `FFC105` | `speed_overrides[*].raw_color_hex` |

Der Speed-Modus wurde für die Speed-Farbprüfung vorübergehend über die UI aktiviert und anschließend auf `network` zurückgestellt. Helligkeit blieb `30`, Verhalten blieb `steady`, und `led_mode` blieb `etherlighting`.

## Freigegebene Link-Speed-Schlüssel

Die konkrete Switch-Oberfläche bot `FE`, `GbE`, `2.5GbE`, `5GbE` und `10GbE` zur Farbauswahl an. Nur diese fünf Schlüssel werden produktiv als Farbauswahl angeboten. Weitere im Setting-Read vorhandene Default-Schlüssel werden nicht spekulativ freigeschaltet.

## Sicherheit

- keine Roh-HAR-Datei gespeichert
- keine Hosts, IP-/MAC-Adressen, internen Namen oder echten IDs gespeichert
- keine Cookies, Token, CSRF-Werte oder Zugangsdaten gespeichert
- IDs konsistent pseudonymisiert
- vollständige Override-Arrays statt gekürzter Fragmente validiert
- kein Port, VLAN-Zuordnung oder Netzwerkparameter verändert
- finaler UI-Zustand vollständig wiederhergestellt

Der Offline-Validator `tools/validate_color_capture.py` meldet keine blockierenden Fehler.

## Capability-Entscheidung

- `network_color`: `confirmed`
- `speed_color`: `confirmed`
