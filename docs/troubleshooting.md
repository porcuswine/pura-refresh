# Troubleshooting

## No advertisements or a stalled connection

Close the Pura app and other Bluetooth tools, temporarily turn phone Bluetooth off, and use breathing-blue setup mode. Try one normal power cycle with a 10-second pause. An already-installed bootstrap does not advertise stock Bluetooth or respond to the stock setup-button gesture; look for `Pura-Setup-XXXX` or its home-network address instead.

Run one scanner at a time. BlueZ `InProgress` can mean another discovery process is running. Close it before retrying. If the adapter is idle but stuck, the optional command below refuses to reset an adapter with active Bluetooth connections:

```sh
sudo "$PWD/.venv/bin/pura-refresh" bluetooth-recover
sudo "$PWD/.venv/bin/pura-refresh" scan
```

It resets the selected idle controller, not the Pi, router or network configuration. This can interrupt a pending discovery session. Do not use it while another Bluetooth operation is in progress.

## Wi-Fi was interrupted

SSH must use Ethernet or a separate adapter. The chosen adapter moves into a temporary network namespace. Normal cleanup restores its prior NetworkManager profile. If the process or Pi was killed during cleanup, run:

```sh
sudo "$PWD/.venv/bin/pura-refresh" recover
```

Recovery reads the tool's root-owned journal and restores only its recorded adapter/profile. No upstream router rules are needed. Check that global dnsmasq or unrelated services are still running if you were independently changing network configuration.

## Metadata or model mismatch

Stop and verify the physical hardware, exact advertised target, actual Wi-Fi MAC and stock software version. A mismatch is a deliberate refusal to serve firmware. Never work around it by editing manifests or guessing another board. The metadata has no trustworthy patch-version byte; it reports major/minor only.

## Image transferred, but no BOOT VERIFIED

Do not repeat installation blindly. Allow startup time, check `Pura-Setup-XXXX` and http://172.29.241.1, and inspect any saved report. A transfer log is not proof of boot, settings availability or a usable partition layout. An unchanged light alone cannot diagnose firmware state.

This process cannot create a complete stock flash backup over Bluetooth. A failed install can require wired recovery. **Disconnect mains before attaching UART or a bench supply.** Do not connect a grounded USB adapter to a mains-powered exposed board. Use 3.3 V UART levels; P1 has GND/PROG/TX/RX, not a power output. Recovery depends on the actual board, boot log and flash layout; do not copy V2 flash offsets or GPIO assumptions to V3.

## Recovery page opens but sign-in fails

The initial credentials are `pura` / `pura-setup`. After setup, use the new device password for both the page and recovery AP. The initial password is no longer valid. There is no password-reset button in this bootstrap.

## Editing configuration

If you need a terminal editor, use Vim. Avoid editing a live session's root-only temporary files; stop the installer and restore Wi-Fi first.
