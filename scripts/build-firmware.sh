#!/bin/sh
set -eu
: "${IDF_PATH:?Activate the documented ESP-IDF ESP32 build environment first}"
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
BOARD=${1:?Usage: scripts/build-firmware.sh v2 or v3}
case "$BOARD" in v2|v3) ;; *) echo 'Choose v2 or v3' >&2; exit 1 ;; esac
EXPECTED=0d6099ec533c4b647fb7a7b0b8942bc7aeb82f90
if [ "$(git -C "$IDF_PATH" rev-parse HEAD)" != "$EXPECTED" ]; then
    echo 'Use the ESP-IDF commit specified in docs/build.md.' >&2
    exit 1
fi
BUILD=${PURA_BUILD_DIR:-"$ROOT/.build/$BOARD"}
idf.py -C "$ROOT/firmware/$BOARD" -B "$BUILD" -D "SDKCONFIG=$BUILD/sdkconfig" build
PYTHONPATH="$ROOT" python "$ROOT/scripts/verify_build.py" --board "$BOARD" --build "$BUILD" \
    --sdkconfig "$BUILD/sdkconfig" --images "$BUILD/verified-image"
echo "Verified development image: $BUILD/verified-image/application.bin"
echo 'Bundled tested images were not overwritten. Validate the rebuild on hardware before releasing.'
