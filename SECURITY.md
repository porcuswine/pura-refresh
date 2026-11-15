# Privacy and security

This repository and its releases are public. Keep raw device reports, flash dumps, network credentials and device passwords out of commits, issues and release assets. Review both new files and their history before publishing changes. GitHub Pages is not enabled.

The distribution contains generic firmware, source, documentation, license notices and mechanical files. It contains no saved home Wi-Fi credentials, private device inventories, stock flash dumps, device passwords, private logs or personal filesystem paths. The first-flash AP uses a new random name/password per run. Temporary session files and recovery journal are root-owned; result reports use mode 0600. Reports still contain device identifiers and should stay private.

The initial device password `pura-setup` is public. Change it during setup. Recovery Wi-Fi and HTTP then use the new password. The web interface uses local HTTP Basic authentication without TLS; use a trusted LAN, keep it off the public Internet, and do not reuse an important password. There is no forgotten-password reset UI.

The first-flash route relies on update behavior of tested stock firmware. Image checks and model checks reduce mistakes but do not prove arbitrary device authenticity. Do not modify devices without authorization. When reporting a security issue, do not upload raw flash dumps, network credentials or identifiable device reports to a public issue.

Use the original enclosure for powered flashing. The printable case is an unpowered mechanical prototype. Firmware heater-off settings do not make exposed mains circuitry safe.
