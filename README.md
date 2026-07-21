# UniFi Etherlighting

HACS-fähige Home-Assistant-Custom-Integration für eine eng versionsgebundene Steuerung der Etherlighting-Helligkeit eines UniFi-Switches.

## Bestätigte Schreibfunktion

- Etherlighting-Helligkeit als `number`-Entität
- bestätigter UI-Bereich: 1–100 %, Schrittweite 1
- aktueller Wert ausschließlich aus einem Controller-Read
- jeder Write wird genau einmal gesendet und anschließend unabhängig gelesen
- kein optimistischer Zustand und kein automatischer Write-Retry

## Exakt getestete Kombination

- Controller: UniFi OS
- Network Application: `10.5.62`
- Device-Typ: `usw`
- Modell: `USWED72`
- Firmware: `7.4.1.16850`

Nur diese exakte Kombination erzeugt eine Brightness-Entität. Andere Network-, Modell- oder Firmware-Versionen erhalten keine Schreibfreigabe.

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

Polling liest die Network-Version und den bestätigten Device-Sammelpfad. Vor jedem Write werden Version, Gerät und aktueller Zustand erneut gelesen. Der UI-Payload wird aus dem aktuellen Device-Zustand auf die beobachteten Felder projiziert; ein minimales Etherlighting-Patch wird nicht verwendet.

Bei einem Timeout oder Verbindungsabbruch nach möglichem Absenden wird der Write nicht wiederholt. Ein Read klassifiziert das Ergebnis als `applied`, `not_applied` oder `indeterminate`. Bei `indeterminate` werden weitere Writes für das Gerät gesperrt und ein Repair erzeugt.

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
