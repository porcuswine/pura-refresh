# Architecture

Bluetooth carries stock BluFi commands for identification, temporary Wi-Fi provisioning and an update check. **Application bytes travel over local HTTPS, not Bluetooth.** This does not dump or read the complete flash over Bluetooth.

The Pi temporarily moves its selected Wi-Fi radio into a private Linux network namespace. An isolated WPA2 AP gives only the selected Wi-Fi MAC a lease. Local DNS maps the stock update hostname to the Pi. There is no Internet forwarding or NAT and no changes to the user's router. The isolated updater network is 192.168.88.0/24. Recovery uses 172.29.241.0/24. Neither is added as an upstream LAN route; choose a separate SSH interface.

The stock firmware on tested builds accepts the locally served HTTPS update. The listener is restricted to the expected source address and requires the selected model headers (`v2` or `v3l`, type `dual-wall`). Before provisioning, the installer verifies device-reported Wi-Fi MAC, hardware and software family. Images are checked against their board manifests, ESP image checksum and SHA256, app identity, flash settings and memory bounds. These compatibility checks are not a cryptographic stock-firmware attestation.

Rehearsal answers the configuration request but returns no image bytes. Flash mode serves one completed application download, allowing limited retries of interrupted transfers. The application goes into an existing stock OTA slot; original bootloader and partition table are not replaced. The Pi subsequently joins the recovery network and checks boot/readiness. Cleanup restores its original Wi-Fi profile.

V2 requires an early startup compatibility hook to limit an inherited flash descriptor to 4 MB. V3 retains valid JEDEC flash density and must accept the original partition table without an MD5 trailer. V3 PSRAM pins 16/17 remain untouched. Both bootstrap applications keep heater outputs off using their board-specific polarity.

The new application starts with independent recovery Wi-Fi and a separate NVS settings namespace. It does not import stock Wi-Fi credentials. HTTP endpoints are `/`, `/status`, `/setup` and `/update`, protected by the device password. HTTP is unencrypted on the local network, so use a trusted network and do not port-forward it. No telemetry, cloud login, remote service or automatic Internet firmware fetch is added.
