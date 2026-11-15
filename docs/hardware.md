# Hardware reference

These are board observations and stock-firmware analysis for tested hardware, not a circuit schematic or a rating for external loads. Keep exposed boards disconnected from mains when tracing connections.

| Function | V2 hardware 2.1 | V3 hardware 3.0 |
| --- | --- | --- |
| Module | ESP32-WROOM-32 | ESP32-WROVER-E N16R8 |
| Flash | 4 MB on tested units | 16 MB on tested unit |
| PSRAM | none identified | 8 MB; bootstrap does not enable it |
| Heater control | GPIO22/23, HIGH off | GPIO22/23, LOW/zero PWM off |
| Bay 1 RGB | 17 / 16 / 5 | 25 / 33 / 5 |
| Bay 2 RGB | 19 / 18 / 21 | 19 / 18 / 21 |
| Status RGB | 26 / 2 / 27, active low | 26 / 2 / 27, active low |
| Button | GPIO4, active low | GPIO4, active low |
| Revision ADC | GPIO34 | GPIO35 |
| Ambient sensor | GPIO35; higher raw readings when covered | not identified |
| Thermistors | not mapped here | GPIO36 and GPIO39 |

V2 P6 was traced as pins 1=GPIO33, 2=GPIO32, 3=3.3 V, 4=GND, using the observed connector orientation. Verify orientation and continuity on your own board before connecting anything. The connector family investigated was Molex 78171/78172, four positions. No spare-current rating has been established for its 3.3 V rail. V3 TP1 is not mapped; do not assume it matches V2.

P1 on both photographed revisions is GND, PROG (GPIO0 boot strap), TX (GPIO1), RX (GPIO3). Module pad numbers differ from GPIO numbers and P1 terminal positions. P1 supplies no dedicated power pin. GPIO16/17 on WROVER are reserved for internal PSRAM and must not be reused as V2 LED outputs.

Heater connectors can carry rectified mains voltage around 160 V on a 120 V supply. They are not general low-voltage accessory power. A transformer marking, input fuse rating or idle wall-power measurement does not establish spare low-voltage output capacity. External load ratings remain unverified.

The included firmware exposes setup/status/update only. Pin maps do not mean the web UI already implements all LEDs, button, sensors or a gateway. For additional circuits, first establish isolation, rail voltage, regulation and load margin with appropriate equipment.

See [the v7 enclosure](../hardware/case/v7/README.md) for the mechanical prototype; its fit and electrical suitability are separate from firmware compatibility.

[Sanitized V2/V3 reference photographs](photos/README.md) show both PCB sides and the original housing.
