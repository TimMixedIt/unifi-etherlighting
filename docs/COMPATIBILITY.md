# Kompatibilität

| Controller | Network App | Device-Typ | Modell | Firmware | Produktiv bestätigte Capability |
|---|---|---|---|---|---|
| UniFi OS | `10.5.62` | `usw` | `USWED72` | `7.4.1.16850` | `brightness` |

Die Prüfung verwendet einen exakten `ControllerCompatibilityKey`. Es gibt keine Wildcards für Network 10.x, Firmware 7.x, Modellfamilien oder ähnlich benannte Switches.

Zusätzlich zur exakten Version muss das aktuelle Device-Objekt `ether_lighting.brightness` als Integer enthalten. Fehlt eine Bedingung, bleibt Brightness `candidate` und es wird keine Number-Entität erzeugt.

Weiterhin gesperrt:

- `behavior`, `mode`, `enabled`, `network_color`: `candidate`
- `port_control`: `unsupported`
