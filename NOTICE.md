# Licensing and attribution

Original installer, bootstrap application source and mechanical source in this repository are distributed under the root MIT license, copyright 2026 porcuswine. Third-party components retain their own terms.

Bundled ESP32 applications include components from Espressif ESP-IDF, built with SDK commit `0d6099ec533c4b647fb7a7b0b8942bc7aeb82f90`. ESP-IDF uses Apache-2.0 for its own code and includes components under other licenses. Copies of SDK, Wi-Fi/PHY, FreeRTOS, lwIP, cJSON and Mbed TLS license texts are under `third_party_licenses/`, along with license/notice files collected from enabled ESP-IDF component source trees. Upstream copyright and attribution notices are retained.

The Python installer depends on Bleak 2.1.1 and its platform dependencies, installed through pip under their respective licenses. Enclosure generation optionally uses NumPy, trimesh, manifold3d and matplotlib; those are separate dependencies, not bundled implementations.

No stock Pura firmware or full flash dump is distributed. Pura and ESP32 names identify compatible hardware and do not imply endorsement. See [build instructions](docs/build.md) for the upstream SDK source used to build applications.
