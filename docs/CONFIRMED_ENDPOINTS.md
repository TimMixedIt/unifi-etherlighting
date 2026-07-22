# Bestätigte Endpoints

| Funktion | Methode | Bereinigter Pfad | Produktive Nutzung |
|---|---|---|---|
| Lokaler Login | `POST` | `/api/auth/login` | ja |
| Lokaler Logout | `POST` | `/api/auth/logout` | ja, Session-Abbau |
| Network-Version | `GET` | `/proxy/network/v2/api/info` | ja, read-only |
| Devices lesen | `GET` | `/proxy/network/api/s/{site}/stat/device` | ja, read-only |
| Device schreiben | `PUT` | `/proxy/network/api/s/{site}/rest/device/{device}` | verifizierte Brightness-, Behavior- und Mode-Steuerung |
| Etherlighting-Farbeinstellungen lesen | `GET` | `/proxy/network/api/s/{site}/get/setting` | ja, read-only |
| Network-Bezeichnungen lesen | `GET` | `/proxy/network/api/s/{site}/rest/networkconf` | ja, read-only |
| Etherlighting-Farb-Overrides schreiben | `POST` | `/proxy/network/api/s/{site}/set/setting/ether_lighting` | verifizierte VLAN-/Network- und Speed-Farben |

Der Versionswert liegt an `$.system.version`. Der Device-Read verlangt `$.meta.rc = ok` und ein Array an `$.data`. Jeder Write verlangt HTTP-Erfolg, `$.meta.rc = ok`, den erwarteten Responsewert und einen unabhängigen Read-after-Write. Produktive Device-Änderungen sind auf genau eines der Felder `brightness`, `behavior` oder `mode` begrenzt. Ein Farb-Write ändert genau einen Eintrag in `network_overrides` oder `speed_overrides`, bewahrt jeweils beide vollständigen Override-Arrays und sendet danach den von der UI beobachteten unveränderten Device-Refresh.

Es gibt keine Fallback-, Legacy-, Site-Discovery- oder Detail-Device-Route. Ein einzelnes Device wird aus der bestätigten `stat/device`-Antwort eindeutig über seine vorhandene ID gewählt.

`X-CSRF-Token` wird dynamisch aus einem Response-Header übernommen. Nur Header- und Cookie-Namen sind dokumentiert; Werte werden nicht persistiert.
