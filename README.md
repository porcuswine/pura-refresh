# pura-refresh

A standalone Raspberry Pi installer that replaces the stock application on tested Pura V2 and V3 diffusers with local setup and Wi-Fi firmware updates. No router changes, cloud account or UART wiring are required for a successful installation.

**Private repository.** Source, instructions and release downloads are available only to repository collaborators. GitHub Pages is not enabled.

This is a limited hardware pilot. An unsuccessful install can require opening the device and recovering it over UART. Keep the diffuser assembled during wireless installation. The included application holds both heaters off; it is a starting point for repurposing, not a complete diffuser or Bluetooth gateway application.

## Compatibility

| Physical hardware | Stock software tested end to end | Module | Bundled application |
| --- | --- | --- | --- |
| V2, hardware 2.1 | 2.10.0 | ESP32-WROOM-32 | `pura-setup-3` |
| V3, hardware 3.0 | 2.7.0 | ESP32-WROVER-E | `pura-v3-setup-3` |

V2 2.10.1 has been analyzed but is not separately validated end to end. Stock Bluetooth metadata reports only the major/minor software family, so `2.10` and `2.7` are accepted when using automatic inspection. Confirm the complete stock version in the Pura app when possible. Other hardware and software are unsupported. V4 and Pura Mini are not supported.

## Start here

Use Raspberry Pi OS Bookworm with NetworkManager, working Wi-Fi and Bluetooth, and **Ethernet for SSH**. The installer temporarily takes exclusive control of the selected Wi-Fi adapter. Do not run it through an SSH connection carried by that adapter.

With GitHub access configured on the Pi:

```sh
gh repo clone porcuswine/pura-refresh
cd pura-refresh
./install-pi.sh
sudo "$PWD/.venv/bin/pura-refresh" images
sudo "$PWD/.venv/bin/pura-refresh" wizard
```

Alternatively clone the private repository using your existing authenticated Git setup. Installation downloads system/Python dependencies; device flashing itself uses a local isolated network without Internet forwarding.

Power only the selected stock diffuser near the Pi. Close the Pura app and disconnect other Bluetooth clients. Hold the diffuser's accessible setup button until the nightlight breathes blue, then release it. In the wizard, choose the physical V2/V3 board and the advertised device. The installer queries its Wi-Fi MAC, hardware and software family, then checks its updater model before serving the matching image.

A successful run must print **BOOT VERIFIED**. Firmware download alone is not proof of successful installation. Then join `Pura-Setup-XXXX`, password `pura-setup`, open **http://172.29.241.1**, and sign in as `pura` / `pura-setup`. Save your home Wi-Fi and a new device password. That password also protects the recovery Wi-Fi. The device's home address comes from your router's DHCP list.

## Included

- One installer and wizard for V2/V3, with separate validated application images.
- Local setup page, authenticated status and subsequent Wi-Fi application uploads.
- Firmware source and build verification tools; original bootloader/partition table remain in place.
- [Printable enclosure v7](hardware/case/v7/README.md), STL files, editable sources and previews. This is an **unpowered fit prototype**, not an electrically validated mains enclosure.

## Documentation

- [Detailed installation and command reference](docs/install.md)
- [Troubleshooting and recovery](docs/troubleshooting.md)
- [How installation works](docs/architecture.md)
- [Hardware pin maps and limitations](docs/hardware.md)
- [Sanitized hardware and enclosure photos](docs/photos/README.md)
- [Validation and known limits](docs/validation.md)
- [Building firmware](docs/build.md)
- [Privacy and security](SECURITY.md)
- [Licenses and attribution](NOTICE.md)

This project is independent of Pura. Use only devices you own or have permission to modify.
