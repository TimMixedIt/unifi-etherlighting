# Verifiziertes Etherlighting-Read-modify-write

> **Freigabe 0.3.0:** Dieser Ablauf ist ausschließlich für die exakt validierte Versionskombination produktiv erreichbar. Das im Device-Read fehlende Feld `lcm_night_mode_enabled` folgt der live bestätigten UI-Initialisierung: vorhandenen booleschen Wert erhalten, bei Abwesenheit `false`, bei jedem anderen Typ sicher abbrechen.

Der Ablauf ändert pro Aktion fachlich genau eines der bestätigten Felder `ether_lighting.brightness`, `ether_lighting.behavior` oder `ether_lighting.mode`:

```text
Authentifizierung sicherstellen
→ Network-Version lesen
→ exakte Kompatibilität prüfen
→ aktuelles Device über stat/device lesen
→ Zielwert gegen die bestätigte Allowlist prüfen
→ bestätigten UI-Payload aus aktuellen Feldern projizieren
→ PUT genau einmal senden
→ HTTP, meta.rc und den erwarteten Responsewert prüfen
→ Device erneut über stat/device lesen
→ Zielwert und unveränderte Etherlighting-Felder prüfen
```

## Payload-Projektion

`build_etherlighting_write_payload()` erzeugt kein minimales Patch. Es übernimmt ausschließlich die im echten UI-Write beobachteten Top-Level-Felder, die bestätigten `config_network`-Felder und `mode`, `brightness`, `behavior`, `led_mode` aus dem aktuellen Device-Zustand. Fehlende Pflichtfelder brechen vor dem Write ab. Read-only- und unbekannte Felder werden nicht ungeprüft gesendet.

Das Eingabeobjekt bleibt unverändert. Die Projektion akzeptiert exakt eine Änderung. Brightness ist auf 1–100 in Einerschritten begrenzt, Behavior auf `steady`/`breath` und Mode auf `network`/`speed`.

## Unsichere Ergebnisse

Writes werden niemals automatisch wiederholt. Nach einer Ablehnung, einem Auth-Fehler oder einer Transportunterbrechung liest der Service den aktuellen Device-Zustand und klassifiziert:

- `applied`: Zielwert unabhängig gelesen, Invarianten erhalten;
- `not_applied`: Ausgangswert unabhängig gelesen, Invarianten erhalten;
- `indeterminate`: kein eindeutiger Zustand oder unerwartete Nebenänderung.

Bei `indeterminate` bleibt die Entität nicht optimistisch auf dem Zielwert; weitere Writes für das Gerät werden temporär gesperrt und ein Repair wird erzeugt.
