#!/bin/sh
set -eu
ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
if [ "$(id -u)" = 0 ]; then
    echo 'Run ./install-pi.sh as your normal Pi user; it uses sudo for OS packages.' >&2
    exit 1
fi
export PATH="$PATH:/usr/sbin:/sbin"
if ! command -v nmcli >/dev/null 2>&1 || ! systemctl is-active --quiet NetworkManager; then
    echo 'Use Raspberry Pi OS Bookworm with an active NetworkManager installation.' >&2
    echo 'This installer will not replace your network manager.' >&2
    exit 1
fi
MISSING=''
for package in python3-venv hostapd dnsmasq-base iw iproute2 bluez openssl wpasupplicant; do
    if ! dpkg-query -W -f='${Status}' "$package" 2>/dev/null | grep -q 'install ok installed'; then
        MISSING="$MISSING $package"
    fi
done
if [ -n "$MISSING" ]; then
    sudo apt-get update
    # Fixed package allowlist above; intentional word splitting.
    sudo apt-get install -y $MISSING
fi
python3 -m venv "$ROOT/.venv"
"$ROOT/.venv/bin/python" -m pip install "$ROOT"
printf '\nInstalled. With the Pi connected by Ethernet, run:\n'
printf '  sudo %s/.venv/bin/pura-refresh wizard\n' "$ROOT"
