# Kompatibilität

| Controller | Network App | Device-Typ | Modell | Firmware | Read-Support | Write-Support | Write-ready |
|---|---|---|---|---|---|---|---|
| UniFi OS | `10.5.62` | `usw` | `USWED72` | `7.4.1.16850` | `brightness` | `candidate` | nein |

Die Prüfung verwendet einen exakten `ControllerCompatibilityKey`. Es gibt keine Wildcards für Network 10.x, Firmware 7.x, Modellfamilien oder ähnlich benannte Switches.

Zusätzlich zur exakten Version muss das aktuelle Device-Objekt `ether_lighting.brightness` als Integer enthalten. Fehlt eine Bedingung, wird keine Number-Entität erzeugt. Bei passender Kombination bleibt die Number lesbar, aber ausdrücklich schreibgesperrt.

Weiterhin gesperrt:

- `behavior`, `mode`, `enabled`, `network_color`: `candidate`
- `port_control`: `unsupported`
