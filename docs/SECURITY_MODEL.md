# Sicherheitsmodell Phase F

- Ausschließlich die live bestätigten Login-, Logout-, Versions-, Device-Read- und Device-Write-Pfade sind implementiert.
- Relative Pfade werden intern gebaut; Site- und Device-Parameter werden URL-kodiert.
- Zugangsdaten werden nur für den bestätigten Login verwendet und nie geloggt.
- Die dedizierte Home-Assistant-ClientSession hält Session-Cookies nur im Speicher.
- Der Cookie-Name `TOKEN` und Headername `X-CSRF-Token` sind bestätigt; ihre Werte werden weder persistiert noch diagnostisch ausgegeben.
- Diagnostics sind allowlist-basiert und enthalten weder Host, Site, Device-ID, Zugangsdaten, Payloads noch vollständige Responses.
- Config-Flow-Fehler werden nur mit Validierungsphase, sicherer Fehlerkategorie, Python-Exception-Typ und optionaler dreistelliger HTTP-Statuszahl protokolliert. Exception-Texte, URLs, Header- und Body-Werte werden verworfen.
- Setup und Polling führen ausschließlich Reads aus, einschließlich der bestätigten Etherlighting-Settings- und Network-Bezeichnungsreads.
- Writes werden einmal gesendet, niemals automatisch wiederholt und immer per Device-Read klassifiziert.
- Ein unbestimmtes Ergebnis sperrt weitere Writes für das betroffene Gerät.
- Nur die exakte bestätigte Versionskombination kann Brightness, Breathing, Mode sowie Network- und Speed-Farben freigeben.
- Pro Aktion darf exakt eines dieser bestätigten Felder geändert werden; Werte außerhalb der jeweiligen Allowlist brechen vor dem Write ab.
- Ein Farb-Write bewahrt beide vollständigen Override-Arrays, ändert genau einen Farbwert und sendet danach den UI-beobachteten, fachlich unveränderten Device-Refresh. Beide Responses und beide unabhängigen Reads werden geprüft.
- Kein SSH, keine Portsteuerung, kein Raw-API-Service, kein Cloud-Upload und keine externe Telemetrie.

HTTP 401 oder 403 bei einem Read erlaubt genau eine erneute Authentifizierung und eine einmalige Wiederholung des Reads. Ein Write wird bei 401, 403, Timeout oder Verbindungsabbruch nicht wiederholt; stattdessen folgt ein Read des aktuellen Zustands.
