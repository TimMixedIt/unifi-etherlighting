# Phase-C-Umsetzung und nächste Capture-Runde

> Historischer Zwischenstand. Der aktuelle produktive Umfang ist in `PHASE_F_IMPLEMENTATION.md` beschrieben.

## Implementiert

- versionsgebundenes Datenmodell für die Capture-Kombination;
- bestätigter UniFi-OS-Device-PUT-Adapter mit Response-Prüfung;
- gesperrtes Read-modify-write-Gerüst;
- Deep-Copy-, JSON-Path- und Diff-Hilfen;
- anonymisierte reduzierte Fixtures und Tests.

Es gibt kein Config Flow, keine HTTP-Session-Erzeugung durch Home Assistant, keine Entity-Plattform und keine freigegebene Schreiboperation.

## Nächste Capture-Schritte

Für jeden Test den Network-Tab vor der Aktion leeren und die ganze Switch-Detailseite vor/nach der Änderung neu laden, falls die UI keinen Read selbst auslöst. Keine GET-URL manuell raten oder aufrufen.

1. **Helligkeit:** Read vor 34; PUT 34 → 35; Read nach 35; PUT 35 → 34; Read nach Rückkehr.
2. **Verhalten:** Read vor `steady`; PUT `steady → breath`; Read nach `breath`; Rückweg und abschließender Read.
3. **Modus:** nur zwei sichtbar angebotene UI-Werte wählen; vollständige Hin-/Rückfolge erfassen.
4. **Aktivierung:** Deaktivieren und Reaktivieren getrennt mit Reads erfassen.
5. **Netzwerkfarbe:** Setting-Read, Farb-Write, Setting-Read, Rückweg und abschließender Read. Zusätzlich siteweite Wirkung, Schlüsseltyp und Farbformat notieren.
6. **Version:** Network-Application-Version ohne Secrets ergänzen.

Erst dann beginnt die Ergänzung eines Read-Adapters. Jede einzelne Capability wird separat verifiziert; Mode, Aktivierung und Netzwerkfarbe werden nicht aus den bisherigen Begleitwerten abgeleitet.
