# Installation

## Prepare the Pi

Use Raspberry Pi OS Bookworm, Python 3.10 or later, NetworkManager, an AP-capable Wi-Fi adapter and working BlueZ Bluetooth. Development was tested on a Debian Bookworm aarch64 Raspberry Pi. Connect Ethernet before using SSH. Give the Pi reliable power and keep the diffuser close enough for Wi-Fi and Bluetooth.

Download a private release with authenticated GitHub CLI (`gh release download v0.1.0 --repo porcuswine/pura-refresh`) or clone this private repository. Extract the source archive before running `./install-pi.sh` as your normal user. It installs missing packages from a fixed list, then creates `.venv`. It does not replace NetworkManager or overwrite the global dnsmasq configuration. Internet is needed to install dependencies.

Read the compatibility table in the README. Power only the target stock unit, in its original housing. Close the Pura app, disconnect nRF Connect or similar clients, and temporarily turn phone Bluetooth off. Enter breathing-blue setup mode with the accessible button. This may reset the device's stock Wi-Fi settings.

## Interactive installation

```sh
sudo "$PWD/.venv/bin/pura-refresh" wizard
```

Choose V2 or V3 based on the physical hardware, then select one advertisement. Metadata inspection fills the actual Wi-Fi MAC and software family. Select `rehearse` to test the update path without serving application bytes, or `flash` to install. A rehearsal still changes the diffuser's Wi-Fi settings; it is not a completely read-only operation.

Keep power on throughout installation. The Pi creates a temporary WPA2 access point, provides local DNS/HTTPS, provisions the selected diffuser through Bluetooth, then joins its new recovery AP to verify the application. It restores its original Wi-Fi profile afterward, including on ordinary failures.

A successful result checks the expected firmware version, exact Wi-Fi MAC, heaters-off status, compatible partition layout and working settings storage. A private JSON report is written with owner-only permissions. Do not publish the report: it includes your device identifiers.

## Manual commands

Replace example addresses with values obtained from your own device. Bluetooth addresses and Wi-Fi MACs differ; do not calculate one from the other.

```sh
sudo "$PWD/.venv/bin/pura-refresh" scan
sudo "$PWD/.venv/bin/pura-refresh" inspect --device 02:00:00:00:00:03
sudo "$PWD/.venv/bin/pura-refresh" network-test --wifi-mac 02:00:00:00:00:01
sudo "$PWD/.venv/bin/pura-refresh" rehearse --board v2 --stock-version 2.10.0 --device 02:00:00:00:00:03 --wifi-mac 02:00:00:00:00:01
sudo "$PWD/.venv/bin/pura-refresh" flash --board v2 --stock-version 2.10.0 --device 02:00:00:00:00:03 --wifi-mac 02:00:00:00:00:01
```

For V3 use `--board v3 --stock-version 2.7.0`. Commands accept `--interface wlan0`; rehearse/flash also accept `--timeout 360` and `--report /path/to/private-report.json`. `network-test` temporarily takes the Wi-Fi adapter but sends no Pura Bluetooth commands and serves no firmware to a device. It checks local DNS and HTTPS plus service startup, not a complete external DHCP client exchange.

`inspect` sends only protocol/version and stock metadata queries; it does not alter Wi-Fi or trigger an update. The radio connection itself can affect how long a stock device advertises.

## Set up the new firmware

Join `Pura-Setup-XXXX` (last four Wi-Fi MAC digits), password `pura-setup`. Disable cellular/VPN routing if your phone insists this network has no Internet. Open http://172.29.241.1 and sign in with username `pura`, password `pura-setup`.

Enter a 2.4 GHz home Wi-Fi network and a new device password of 12–63 printable ASCII characters. The same password protects HTTP access and recovery Wi-Fi. Save it in your password manager. The device saves settings separately from stock data, restarts, and attempts home Wi-Fi. Locate its IP in your router's DHCP list. If home Wi-Fi fails, recovery is available at the address above.

The current firmware has no reset-button handler; holding the button will not erase its settings. There is no factory-reset or forgotten-password recovery UI. Recovering lost credentials can require UART or a deliberately designed replacement application.

## Later firmware updates

Use the authenticated web page's upload form with an **application-only ESP32 image specifically built for that board**. Do not upload a merged image, bootloader or partition-table file. V2 and V3 heater polarities differ. The web updater checks image validity and slot capacity; it cannot establish that arbitrary third-party application code uses the board safely. The first-flash CLI intentionally accepts only its packaged, board-specific images.

## After rehearsal

A rehearsal withholds every firmware byte but provisions temporary Wi-Fi. Run `flash` next, or use `restore-wifi --device ADDRESS` to enter the original network privately. This restricted legacy Bluetooth helper supports SSIDs up to 16 UTF-8 bytes and passwords 8–16 bytes; use the official app for other credentials. New firmware's browser setup supports ordinary longer Wi-Fi credentials.
