# Bestätigte Endpoints

| Funktion | Methode | Bereinigter Pfad | Produktive Nutzung |
|---|---|---|---|
| Lokaler Login | `POST` | `/api/auth/login` | ja |
| Lokaler Logout | `POST` | `/api/auth/logout` | ja, Session-Abbau |
| Network-Version | `GET` | `/proxy/network/v2/api/info` | ja, read-only |
| Devices lesen | `GET` | `/proxy/network/api/s/{site}/stat/device` | ja, read-only |
| Device schreiben | `PUT` | `/proxy/network/api/s/{site}/rest/device/{device}` | nur Brightness-Service |

Der Versionswert liegt an `$.system.version`. Der Device-Read verlangt `$.meta.rc = ok` und ein Array an `$.data`. Der Write verlangt HTTP-Erfolg und `$.meta.rc = ok`; der Brightness-Service prüft zusätzlich den Responsewert und einen unabhängigen Read-after-Write.

Es gibt keine Fallback-, Legacy-, Site-Discovery- oder Detail-Device-Route. Ein einzelnes Device wird aus der bestätigten `stat/device`-Antwort eindeutig über seine vorhandene ID gewählt.

`X-CSRF-Token` wird dynamisch aus einem Response-Header übernommen. Nur Header- und Cookie-Namen sind dokumentiert; Werte werden nicht persistiert.
