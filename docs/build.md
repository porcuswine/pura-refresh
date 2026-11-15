# Building firmware

The release includes the exact binaries tested on hardware. Installing the Pi flasher does not compile firmware. Rebuilding is for development and must not silently replace those tested binaries.

Use the upstream [Espressif ESP-IDF repository](https://github.com/espressif/esp-idf) at commit `0d6099ec533c4b647fb7a7b0b8942bc7aeb82f90` (IDF 5.5 development). Follow its setup instructions for your development host, install the ESP32 tools and activate its environment. The tested compiler was `esp-14.2.0_20241119`. The IDF environment supplies pyelftools and `idf.py`.

```sh
git clone https://github.com/espressif/esp-idf.git
git -C esp-idf checkout 0d6099ec533c4b647fb7a7b0b8942bc7aeb82f90
git -C esp-idf submodule update --init --recursive
./esp-idf/install.sh esp32
. ./esp-idf/export.sh
# From the pura-refresh repository:
./scripts/build-firmware.sh v2
./scripts/build-firmware.sh v3
```

`PURA_BUILD_DIR` can select a different build directory. Output is `.build/BOARD/verified-image/application.bin` plus a development manifest. The script checks the pinned SDK and does not overwrite release images. Timestamps and toolchain/environment differences can change binary hashes; byte-for-byte reproducibility is not claimed.

The verifier checks image identity, checksum, SHA256, legacy memory ranges, DIO/40 MHz configuration, partition offset, original-ESP32 support, Wi-Fi RAM-only storage and early-startup hook ordering in the ELF. V3 additionally requires partition-table MD5 checking disabled and PSRAM disabled. V2 must cap the inherited flash descriptor at 4 MB; V3 uses valid JEDEC density up to 16 MB.

Do not flash generated bootloader or partition-table binaries through the stock OTA route. Only an application image belongs there. Do not erase stock NVS: older SDK data can coexist with the new `pura_setup` namespace. Keep the documented NVS legacy compatibility flag enabled.

Before releasing a changed application, verify startup/layout/settings/heater polarity on the correct hardware, test a full untouched-stock first flash, test subsequent web OTA and re-audit the distribution for private paths/credentials. New image project/version constants must agree with `boards.py` and their manifest. Source edits alone do not update bundled images.
