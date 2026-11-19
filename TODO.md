# TODO

Unchecked items are unfinished work, not supported capabilities or established electrical ratings.

## Low-voltage DC power — priority

- [ ] Confirm accessible DC rails and attachment points on each board revision. V2 P6 has an observed nominal 3.3 V connection; V3 TP1 remains unmapped. Record voltage with the original supply, polarity, reference ground and board revision.
- [x] Identify the V2 ELD207 dual-channel optocoupler and record reported transformer/heater-control tracing as strong evidence that the ESP32/P6 domain is galvanically isolated; see [isolation evidence](docs/hardware.md#v2-p6-isolation-evidence--2026-11-19).
- [ ] Complete an annotated V2 isolation-boundary trace, check all crossing components/paths and assess protective insulation before treating P6 as suitable for externally accessible accessories. Assess V3 separately; component identification is not complete-board safety qualification.
- [ ] Identify the regulator and supply topology feeding each candidate rail, and obtain its component ratings. Separate connector/contact ratings from the power supply's available output.
- [ ] Measure baseline rail voltage and current with heaters disabled, including startup and Wi-Fi activity. Record wall input power separately; it does not establish spare output capacity.
- [x] Record an initial V2 P6 resistive-load observation: approximately 142 mA added load at reported 3.327–3.328 V for about 20 minutes; see [test conditions and limits](docs/hardware.md#v2-p6-additional-load-observation--2026-11-19). This is not a current rating.
- [ ] Repeat controlled additional DC loads using suitable resistors or an electronic load. Record resistance/current, voltage droop, resets, temperature and test duration. Use insulated fixtures prepared with mains disconnected; do not connect grounded bench instruments until isolation is established.
- [ ] Check ripple/transient behavior and sustained operation, then publish a conservative accessory-current budget with headroom. Do not infer a continuous rating merely from the load at which the board first fails.

## Connector and expansion

- [x] Observe physical fit of the purchased mating plug on V2 P6 and use it for a load test.
- [ ] Record the purchased cable/contact part numbers against Molex Pico-EZmate 78171-0004 / 78172-0004. Reconcile the working bench pin numbers with the manufacturer's cavity numbering and add an annotated orientation photo.
- [ ] Confirm suitable crimp contacts and a practical cable/pigtail or adapter solution; document a tested parts list. A bare crimp housing is not a pre-wired connector.
- [ ] Complete stock-firmware analysis of V2 GPIO32/GPIO33 usage before describing P6 as a freely reusable expansion port.
- [ ] Map accessible V3 low-voltage attachment points and identify its ambient-light input. Calibrate thermistor readings before reporting temperatures.

## Firmware and installation

- [ ] Test the final combined wizard on additional untouched V2 and V3 units when available. Record full stock versions and distinguish those results from the earlier board-specific installer tests.
- [ ] Add and test physical-button behavior, including a deliberate settings/password recovery design.
- [ ] Develop an actual repurposing application, such as a Bluetooth gateway or sensor integration. The current bootstrap provides local setup/status and Wi-Fi updates.

## Enclosure

- [ ] Finish mechanical fit checks, button access and connector/cable routing for the v7 case; validate V3 fit separately.
- [ ] Assess insulation, openings, material/temperature behavior and plug retention before any powered use. Existing mesh checks and fit photos do not establish mains suitability.

See [hardware observations](docs/hardware.md) and [validation limits](docs/validation.md).
