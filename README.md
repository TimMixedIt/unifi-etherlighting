# UniFi Etherlighting

HACS-fähige Home-Assistant-Custom-Integration zum verifizierten Steuern von Etherlighting-Helligkeit, Breathing, Speed/Network-Modus sowie VLAN-/Network- und Link-Speed-Farben eines UniFi-Switches.

## Aktueller Freigabestatus

- `brightness_read_supported = true`
- `brightness_write_supported = confirmed`
- `brightness_write_ready = true`
- der aktuelle Wert ist als `number`-Entität les- und schreibbar
- Breathing ist als `switch`-Entität schaltbar
- Speed/Network ist als `select`-Entität wählbar
- jede VLAN-/Network-Farbe ist über eine native `light`-Farbauswahl steuerbar
- die bestätigten Link-Speed-Farben sind über native `light`-Farbauswahlen steuerbar
- jeder Write liest zuerst Version und vollständige Device-Konfiguration
- jeder Write wird genau einmal gesendet und anschließend unabhängig gelesen

Der bestätigte UI-Write enthielt `lcm_night_mode_enabled`, obwohl das Feld im echten `stat/device`-Read fehlt. Die Network-Oberfläche bewahrt einen vorhandenen booleschen Wert und initialisiert ihn bei Fehlen ausdrücklich mit `false`. Version 0.4.0 bildet exakt dieses live beobachtete UI-Verhalten nach; für andere Device-Felder gibt es keine Defaults.

## Exakt getestete Kombination

- Controller: UniFi OS
- Network Application: `10.5.62`
- Device-Typ: `usw`
- Modell: `USWED72`
- Firmware: `7.4.1.16850`

Nur diese exakte Kombination erzeugt eine schreibbereite Brightness-Entität. Andere Network-, Modell- oder Firmware-Versionen erhalten keine Schreibfreigabe.

## Weiterhin nicht steuerbar

- Aktivierungszustand
- Port-Etherlighting oder andere Portsteuerung
- Raw-API-Services

Der Aktivierungszustand bleibt `candidate`; Portsteuerung bleibt `unsupported`.

## Einrichtung

1. Repository über HACS als benutzerdefiniertes Integrations-Repository hinzufügen.
2. Integration installieren und Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste** „UniFi Etherlighting“ hinzufügen.
4. Lokalen Controller, TLS-Einstellungen, Zugangsdaten und den UniFi-Site-Slug angeben.
5. Einen oder mehrere exakt kompatible Switches auswählen.

Der Config Flow führt einen echten lokalen Login sowie ausschließlich bestätigte Read-Aufrufe aus. Er führt keinen Test-Write aus. Bei selbstsignierten Zertifikaten muss die Zertifikatsprüfung bewusst deaktiviert werden.

Unerwartete Einrichtungsfehler werden sicher einer der Phasen `session`, `login`, `version_read`, `device_read` oder `compatibility` zugeordnet. Ein best-effort fehlgeschlagener Logout wird als Phase `logout` protokolliert, kann aber einen erfolgreichen Flow nicht maskieren. Die Diagnose enthält keine Controlleradresse, Zugangsdaten, Cookies, Token, CSRF-Werte oder Request-/Response-Inhalte.

## Laufzeitverhalten

Die Integration lädt:

- `sensor` für sicheren Status, Version und Capability-Diagnostik;
- `number` für `Etherlighting brightness`;
- `switch` für den Breathing-Modus;
- `select` für `network` oder `speed`;
- `light` für jede gelesene VLAN-/Network-Farbe und für `FE`, `GbE`, `2.5GbE`, `5GbE` und `10GbE`.

Polling liest die Network-Version, den bestätigten Device-Sammelpfad, die Etherlighting-Farbeinstellungen und die Network-Bezeichnungen. Vor einem Device-Write prüft der Steuerdienst erneut die exakte Versionskombination, liest den aktuellen Device-Zustand, baut den vollständigen UI-Payload mit exakt einer fachlichen Änderung und verifiziert den Zielwert durch einen unabhängigen Read.

Ein Farb-Write liest zuerst die vollständigen Default- und Override-Arrays, ändert genau einen Farbwert, bewahrt alle anderen Farbzuordnungen und sendet anschließend den von der UniFi-Oberfläche beobachteten fachlich unveränderten Device-Refresh. Setting-Response, Device-Response, Setting-Read-after-Write und Device-Read-after-Write müssen übereinstimmen; es gibt keinen automatischen Write-Retry.

Ein Diagnosesensor meldet `write_capability=ready`. Bei einem unbestimmten Ergebnis wird nicht automatisch wiederholt; weitere Writes für das betroffene Gerät werden bis zur Prüfung blockiert.

## Datenschutz und Sicherheit

Zugangsdaten, Hosts, Site-Slugs, Device-IDs, Cookie-/Session-/CSRF-Werte, Payloads und vollständige Responses sind aus Diagnostics und Logs ausgeschlossen. Session-Cookies und CSRF-Daten bleiben ausschließlich im Arbeitsspeicher der dedizierten Home-Assistant-HTTP-Session. Es gibt kein SSH, keine Cloud-Weiterleitung und keinen externen Debug-Upload.

## Entwicklung

```bash
python3 tools/validate_capture_sequence.py captures/brightness
python3 tools/validate_control_capture.py captures/controls/live_validation.json
python3 tools/validate_color_capture.py captures/colors/live_validation.json
uv run --with-requirements requirements_test.txt pytest -q
uv run --with 'ruff>=0.11.0' ruff check .
```

Die Captures sind pseudonymisiert; vollständige HAR-Dateien gehören nicht in das Repository.

Die Repository-Links in `manifest.json` verweisen auf das öffentliche GitHub-Repository.
