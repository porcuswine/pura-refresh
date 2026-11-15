# Validation and limits

## Hardware evidence

Multiple V2 hardware 2.1 units with stock 2.10.0 completed the standalone Raspberry Pi wireless installation, recovery-AP boot check, home-Wi-Fi setup and restart. V3 hardware 3.0 stock 2.7.0 completed an untouched-stock wireless install with the corrected V3 image, followed by settings and restart checks. Early V2/V3 recovery investigations used UART to diagnose boot compatibility; those failures are not counted as successful wireless installs.

The bundled binaries are the exact tested images:

| Board | Version | Bytes | SHA256 |
| --- | --- | --- | --- |
| V2 | pura-setup-3 | 768240 | 730e6c1412950b5e037590415d0052099281e47859e759e8f284247cfc957eca |
| V3 | pura-v3-setup-3 | 768896 | d76610faa0066f503a6a7e85198c89ffb5bf011ffb0fa1b7c33959253d3816e3 |

V2 stock 2.10.1 was analyzed separately. It is not a separate end-to-end hardware validation. Hardware beyond the table is unsupported. This is a small pilot, not broad production qualification.

The combined `pura-refresh` wrapper passed installation, unit tests and isolated-network checks on the Pi. The V2/V3 transfer and bootstrap implementations were exercised in the hardware tests above; the final combined wizard has not yet been exercised on another untouched unit.

## Automated checks

The test suite validates board-specific images, cross-board rejection, corrupt images, legacy memory bounds and required startup proof; protocol framing/provisioning order; device metadata parsing and identity mismatches; isolated DHCP/DNS configuration; HTTPS source/model restrictions; rehearsal withholding; one completed delivery; boot identity checks; and owner-only report permissions. Local TLS tests require loopback socket access and OpenSSL.

```sh
python3 -m unittest discover -s tests -v
python3 -m pura_refresh.cli images
```

`network-test` checks real Pi namespace/service startup, local DNS and HTTPS. It changes the selected Pi Wi-Fi connection temporarily, but sends no device commands. It does not replace a complete hardware flash test. Firmware image integrity and successful boot do not establish arbitrary future application's electrical behavior.

## Known limits

- Stock metadata exposes only major/minor software, not a trustworthy patch value.
- Bluetooth can stop advertising or time out; keep other clients disconnected.
- A transfer can complete without a usable boot. The final readiness check is mandatory.
- No complete stock flash backup or password-reset mechanism is provided.
- Setup does not implement a full gateway, heater control or physical-button behavior.
- No spare-current, enclosure thermal, mains-insulation or plug-retention qualification has been performed.
- Built-in signed-update or TLS policy changes in other stock builds can prevent this route.

Device names, live MACs, LAN addresses, private logs and credentials are intentionally excluded from this record.
