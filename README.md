# UniFi Etherlighting

HACS-fähige Home-Assistant-Custom-Integration zum sicheren Lesen der Etherlighting-Helligkeit eines UniFi-Switches. Version 0.2.5 ist ausdrücklich schreibgesperrt.

## Aktueller Freigabestatus

- `brightness_read_supported = true`
- `brightness_write_supported = candidate`
- `brightness_write_ready = false`
- der aktuelle Wert bleibt als `number`-Entität lesbar
- jeder Number- oder interne Serviceaufruf wird vor Login und Netzwerkzugriff gesperrt
- PUT-, PATCH- und Device-POST-Requests sind in 0.2.5 nicht erreichbar

Der bestätigte UI-Write enthielt `lcm_night_mode_enabled`. Dieses Feld fehlt im echten `stat/device`-Read. Es wird weder entfernt noch erfunden oder durch einen Defaultwert ersetzt.

## Exakt getestete Kombination

- Controller: UniFi OS
- Network Application: `10.5.62`
- Device-Typ: `usw`
- Modell: `USWED72`
- Firmware: `7.4.1.16850`

Nur diese exakte Kombination erzeugt eine lesbare Brightness-Entität. Eine Schreibfreigabe besteht für keine Kombination.

## Weiterhin nicht steuerbar

- Behavior/Breathing
- Etherlighting-Modus
- Aktivierungszustand
- Netzwerkfarben
- Port-Etherlighting oder andere Portsteuerung
- `select`-, `switch`- oder `light`-Entitäten
- Raw-API-Services

Diese Capabilities bleiben `candidate`; Portsteuerung bleibt `unsupported`.

## Einrichtung

1. Repository über HACS als benutzerdefiniertes Integrations-Repository hinzufügen.
2. Integration installieren und Home Assistant neu starten.
3. Unter **Einstellungen → Geräte & Dienste** „UniFi Etherlighting“ hinzufügen.
4. Lokalen Controller, TLS-Einstellungen, Zugangsdaten und den UniFi-Site-Slug angeben.
5. Einen oder mehrere exakt kompatible Switches auswählen.

Der Config Flow führt einen echten lokalen Login sowie ausschließlich bestätigte Read-Aufrufe aus. Er führt keinen Test-Write aus. Bei selbstsignierten Zertifikaten muss die Zertifikatsprüfung bewusst deaktiviert werden.

Unerwartete Einrichtungsfehler werden sicher einer der Phasen `session`, `login`, `version_read`, `device_read` oder `compatibility` zugeordnet. Ein best-effort fehlgeschlagener Logout wird als Phase `logout` protokolliert, kann aber einen erfolgreichen Flow nicht maskieren. Die Diagnose enthält keine Controlleradresse, Zugangsdaten, Cookies, Token, CSRF-Werte oder Request-/Response-Inhalte.

## Laufzeitverhalten

Die Integration lädt ausschließlich:

- `sensor` für sicheren Status, Version und Capability-Diagnostik;
- `number` für `Etherlighting brightness` pro ausgewähltem, exakt kompatiblem Switch.

Polling liest die Network-Version und den bestätigten Device-Sammelpfad. Die zentrale Schreibsperre greift sowohl in der Number-Entität als auch am Anfang des Brightness-Service. Deshalb werden weder Payload-Projektion noch Authentifizierung oder Controllerzugriffe für einen Write gestartet.

Ein Diagnosesensor und ein Repair melden `confirmed_write_configuration_incomplete`; als bekannt fehlendes Feld wird ausschließlich `lcm_night_mode_enabled` genannt.

## Datenschutz und Sicherheit

Zugangsdaten, Hosts, Site-Slugs, Device-IDs, Cookie-/Session-/CSRF-Werte, Payloads und vollständige Responses sind aus Diagnostics und Logs ausgeschlossen. Session-Cookies und CSRF-Daten bleiben ausschließlich im Arbeitsspeicher der dedizierten Home-Assistant-HTTP-Session. Es gibt kein SSH, keine Cloud-Weiterleitung und keinen externen Debug-Upload.

## Entwicklung

```bash
python3 tools/validate_capture_sequence.py captures/brightness
uv run --with-requirements requirements_test.txt pytest -q
uv run --with 'ruff>=0.11.0' ruff check .
```

Die Captures sind pseudonymisiert; vollständige HAR-Dateien gehören nicht in das Repository.

Die Repository-Links in `manifest.json` verweisen auf das öffentliche GitHub-Repository.
