# Live-Capture-Analyse: Phase-F-Stand

Die echte lokale UniFi-Network-Weboberfläche bestätigte für dieselbe Browser-Sitzung:

- Login, Session-Cookie-Name, CSRF-Quelle, Logout und 401-Verhalten;
- Network Application Version über einen read-only UI-Request;
- Device-Sammelread;
- Brightness-Sequenz 30 → 31 → 30 mit unabhängigen Reads;
- Behavior-Sequenz `steady → breath → steady` mit unabhängigen Reads;
- Mode-Sequenz `network → speed → network` mit unabhängigen Reads;
- Network-Farbsequenz `0544FF → 0644FF → 0544FF` mit unabhängigen Setting-Reads;
- Speed-Farbsequenz `FFC105 → FEC105 → FFC105` mit unabhängigen Setting-Reads;
- beide Writes HTTP 200 und `meta.rc = ok`;
- unveränderte `mode`, `behavior` und `led_mode`;
- UI-Grenzen 1–100 %, effektiver Schritt 1.

| Feld | Evidenz | Status |
|---|---|---|
| `ether_lighting.brightness` | Read/Write/Read-back/Reversal/Final Read plus bestätigte UI-Feldinitialisierung | `confirmed`, `reversible`, write-ready=true |
| `ether_lighting.behavior` | UI-Write/Read-back/Reversal/Final Read | `confirmed`, `reversible`, write-ready=true |
| `ether_lighting.mode` | UI-Write/Read-back/Reversal/Final Read | `confirmed`, `reversible`, write-ready=true |
| `ether_lighting.led_mode` | unveränderter Begleitwert | `candidate`, `captured` |
| `network_overrides[*].raw_color_hex` | UI-Write/Setting-Read-back/Reversal/Final Read plus unveränderter Device-Refresh | `confirmed`, `reversible`, write-ready=true |
| `speed_overrides[*].raw_color_hex` | UI-Write/Setting-Read-back/Reversal/Final Read plus unveränderter Device-Refresh | `confirmed`, `reversible`, write-ready=true |
| Port Control | keine Evidenz, nicht im Scope | `unsupported` |

Alle Captures sind pseudonymisiert. Roh-HARs, Hosts, Adressen, interne Namen und Authentifizierungswerte werden nicht gespeichert.
