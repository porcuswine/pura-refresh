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

V2 P6 was traced as pins 1=GPIO33, 2=GPIO32, 3=nominal 3.3 V, 4=GND, using the working bench numbering. This numbering has not yet been reconciled with the manufacturer's cavity numbers. Verify orientation and continuity on your own board before connecting anything. No spare-current rating has been established for its 3.3 V rail. V3 TP1 is not mapped; do not assume it matches V2.

## V2 P6 connector

The candidate identification is **Molex Pico-EZmate, 1.20 mm pitch, four circuits**, rather than 1.25 mm PicoBlade. The purchased mating plugs were reported to fit P6 successfully during bench testing on 2026-11-19. Manufacturer cavity numbering and the exact purchased cable/contact part numbers remain to be documented.

| Part | Manufacturer description | Role |
| --- | --- | --- |
| [78171-0004 / 0781710004](https://www.molex.com/en-us/products/part-detail/781710004) | Four-circuit PCB header, male, surface mount | Candidate board-side P6 header |
| [78172-0004](https://www.molex.com/en-us/products/part-detail/781720004) | Four-circuit receptacle crimp housing | Candidate mating cable housing; contacts/wires are separate |

Molex specifies vertical mating for this low-profile family. Its open appearance differs from a conventional enclosed side-entry connector. See the [P6 close-up](photos/v2-p6-connector.jpg). Connector specifications do not establish the Pura's available accessory current. Physical fit and use as a load-test connection have been observed; a reproducible cable/contact parts list and manufacturer-numbered pinout are still needed. See the [TODO list](../TODO.md).

## V2 P6 isolation evidence — 2026-11-19

**The observed topology strongly supports galvanic isolation of the ESP32/P6 low-voltage domain from mains.** This is a conclusion from reported circuit tracing and component identification, not a dielectric-withstand or leakage-test result. It applies to the examined V2 board; V3 and other PCB revisions have not been assessed here.

The central eight-pin component was read as **ELD207** (additional marking reported as `148`). Everlight identifies ELD207 as a dual-channel phototransistor optocoupler: its input LEDs transfer signals optically to electrically separate output transistors. The manufacturer lists a component isolation voltage of 3750 Vrms; that is not an operating-voltage or insulation rating for the complete PCB. See [Everlight's catalogue, ELD207 entry](https://en.everlight.com/wp-content/uploads/2026/01/2026-2027_Catalogue_IR.pdf).

The reported trace observations fit this arrangement:

- The mains/rectified supply feeds the transformer primary and a separate heater-power path.
- The transformer secondary supplies the low-voltage circuitry; P6 shares the ESP32 supply and ground.
- One side of the ELD207 connects toward the ESP32 and the other toward the heater circuitry, consistent with two isolated heater-control channels.

The optocoupler identification resolves the previously unidentified component in the heater-control path and provides additional evidence beyond the transformer alone. Reference photos show the [component side](photos/v2-component-side.jpg) and [module side](photos/v2-module-side.jpg). The marking and connectivity were reported from hands-on inspection; the existing photographs alone do not independently establish every connection.

The working conclusion is **apparently galvanically isolated, with strong topology evidence**, conditional on there being no other conductive path between the domains. Remaining work is to record an annotated isolation-boundary/net trace, identify any other components crossing it, and assess transformer insulation, PCB clearances/creepage and the completed assembly. Protective-insulation suitability for accessible accessories has not been qualified. This observation neither establishes a continuous accessory-current rating nor qualifies a modified enclosure.

## V2 P6 additional-load observation — 2026-11-19

One V2 board was tested through P6 working pins 3 (nominal 3.3 V) and 4 (GND), using a mating plug. The board was powered through its original AC plug using the onboard power supply, with no bench supply connected. The exact PCB revision, firmware/radio workload and ambient temperature were not captured in the measurement log. Results must not be generalized to other revisions or V3, or treated as an original-supply current rating.

| Added resistive load | Reported rail voltage | Calculated additional current |
| --- | --- | --- |
| 330 ohm | approximately 3.3 V | 10 mA |
| 150 ohm | approximately 3.3 V | 22 mA |
| 100 ohm | approximately 3.3 V | 33 mA |
| 47 ohm | approximately 3.3 V | 70 mA |
| Two 47 ohm resistors in parallel (23.5 ohm nominal) | reported approximately 3.327–3.328 V after about 20 minutes using MIN/MAX mode | approximately 142 mA |

Resistors were specified as 0.5 W, 1% metal film. At the final reported voltage, total added load power was approximately 0.47 W, or 0.236 W per resistor. Current is calculated from nominal resistance, not measured directly; it excludes the board's own consumption. The instrument was a KAIWEETS HT118A. The resistors were reported as not noticeably warm; no component or enclosure temperatures were measured. No explicit reset-monitoring result was recorded. The voltage range is a reported reading, not a calibrated uncertainty or an oscilloscope ripple measurement.

**This is a single-board load observation, not a maximum-current rating, continuous accessory-current allowance, or electrical-safety qualification.** No supply-temperature, transient/ripple, insulation, leakage or fault testing accompanied it.

Before publishing a usable accessory-power budget:

- Complete and annotate the P6 regulator/return and isolation-boundary trace, building on the transformer and ELD207 evidence above. Check for any additional paths crossing the boundary and identify component ratings; topology evidence or an open-circuit continuity test alone does not qualify protective insulation.
- Have a qualified person assess insulation, clearances/creepage and accessible conductive parts. Any required dielectric-withstand and leakage/touch-current tests need appropriate equipment and procedures; they are not improvised multimeter tests. See [MEAN WELL's insulation-test explanation](https://www.meanwell.com/qa.aspx).
- Measure regulator, transformer, rectifier, capacitor and enclosure temperatures under sustained representative load, in the intended enclosure and ambient conditions, until temperatures stabilize. Compare with actual component ratings and retain margin. The load resistors' temperature is not the supply temperature.
- Check startup, radio peaks and load changes using appropriately rated isolated or differential measurement equipment. A handheld meter's MIN/MAX display can miss brief dips and switching ripple. Never defeat an oscilloscope's protective earth; see [Tektronix's floating-measurement guidance](https://www.tek.com/en/documents/application-note/three-facets-floating-measurement-solutions).
- Assess wiring insulation, strain relief, connector/contact suitability and accessory fault protection. Verify the completed assembly, including any modified enclosure; the original product's safety evaluation does not qualify the modification.

Keep externally accessible accessories and grounded USB/bench instruments disconnected until the isolation boundary and suitability for the intended connections have been verified. Further mains-powered characterization should use a protected test fixture and qualified assistance. A longer unchanged-voltage test alone cannot answer these safety questions.

## Programming and power limits

P1 on both photographed revisions is GND, PROG (GPIO0 boot strap), TX (GPIO1), RX (GPIO3). Module pad numbers differ from GPIO numbers and P1 terminal positions. P1 supplies no dedicated power pin. GPIO16/17 on WROVER are reserved for internal PSRAM and must not be reused as V2 LED outputs.

Heater connectors can carry rectified mains voltage around 160 V on a 120 V supply. They are not general low-voltage accessory power. A transformer marking, input fuse rating or idle wall-power measurement does not establish spare low-voltage output capacity. External load ratings remain unverified.

The included firmware exposes setup/status/update only. Pin maps do not mean the web UI already implements all LEDs, button, sensors or a gateway. For additional circuits, first establish isolation, rail voltage, regulation and load margin with appropriate equipment.

See [the v7 enclosure](../hardware/case/v7/README.md) for the mechanical prototype; its fit and electrical suitability are separate from firmware compatibility.

[Sanitized V2/V3 reference photographs](photos/README.md) show both PCB sides and the original housing.
