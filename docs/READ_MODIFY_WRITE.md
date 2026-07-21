# Verifiziertes Brightness-Read-modify-write

> **Release-Sperre 0.2.5:** Dieser Ablauf ist nicht produktiv erreichbar. Der echte `stat/device`-Read enthält `lcm_night_mode_enabled` nicht, obwohl das Feld Bestandteil des bestätigten UI-Write-Payloads war. Number-Entität und Brightness-Service brechen deshalb vor jeder Netzwerkoperation mit `confirmed_write_configuration_incomplete` ab.

Der für eine spätere Freigabe vorgesehene Ablauf ist fachlich auf `ether_lighting.brightness` begrenzt:

```text
Authentifizierung sicherstellen
→ Network-Version lesen
→ exakte Kompatibilität prüfen
→ aktuelles Device über stat/device lesen
→ Brightness gegen 1–100 und Schritt 1 prüfen
→ bestätigten UI-Payload aus aktuellen Feldern projizieren
→ PUT genau einmal senden
→ HTTP, meta.rc und Response-Brightness prüfen
→ Device erneut über stat/device lesen
→ Brightness und unveränderte Etherlighting-Felder prüfen
```

## Payload-Projektion

`build_brightness_write_payload()` erzeugt kein minimales Patch. Es übernimmt ausschließlich die im echten UI-Write beobachteten Top-Level-Felder, die bestätigten `config_network`-Felder und `mode`, `brightness`, `behavior`, `led_mode` aus dem aktuellen Device-Zustand. Fehlende Pflichtfelder brechen vor dem Write ab. Read-only- und unbekannte Felder werden nicht ungeprüft gesendet.

Das Eingabeobjekt bleibt unverändert. Die einzige fachliche Änderung innerhalb der Projektion ist `ether_lighting.brightness`.

## Unsichere Ergebnisse

Writes werden niemals automatisch wiederholt. Nach einer Ablehnung, einem Auth-Fehler oder einer Transportunterbrechung liest der Service den aktuellen Device-Zustand und klassifiziert:

- `applied`: Zielwert unabhängig gelesen, Invarianten erhalten;
- `not_applied`: Ausgangswert unabhängig gelesen, Invarianten erhalten;
- `indeterminate`: kein eindeutiger Zustand oder unerwartete Nebenänderung.

Bei `indeterminate` bleibt die Number-Entität nicht optimistisch auf dem Zielwert; weitere Writes für das Gerät werden temporär gesperrt und ein Repair wird erzeugt.
