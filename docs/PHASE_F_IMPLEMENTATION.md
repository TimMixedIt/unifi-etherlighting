# Phase F implementation

## Gate

Phase F1 ist bestanden. Die Einzelbelege liegen unter `captures/brightness`, `captures/controller_version`, `captures/auth` und `docs/validation`.

## Implementierter Umfang

- bestätigter UniFi-OS-Login und -Logout;
- Cookie-Session und CSRF nur im Speicher;
- Runtime-Read der Network Application Version;
- bestätigter `stat/device`-Read und eindeutige Device-Auswahl;
- exakte Kompatibilitätsmatrix;
- explizite Brightness-Payload-Projektion;
- einmaliger Write plus unabhängiger Read-after-Write;
- Klassifikation `applied`, `not_applied`, `indeterminate`;
- temporäre Write-Sperre und Repairs bei unbestimmtem Ergebnis;
- eine `number`-Entität je ausgewähltem, exakt kompatiblem Switch;
- weiterhin ausschließlich `sensor` und `number` als Plattformen.

## Sicherheits- und Regressionsergebnis

Behavior, Mode, Enabled und Network Color bleiben `candidate`; Port Control bleibt `unsupported`. Es wurden keine Select-, Switch-, Light- oder Raw-Service-Schnittstellen hinzugefügt. Setup und Coordinator-Polling schreiben nicht.

Lokale Validierung:

```text
36 tests passed
Ruff: all checks passed
Brightness capture sequence: PASS
```

Integrationsversion: `0.2.0`.
