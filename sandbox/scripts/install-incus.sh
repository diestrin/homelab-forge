#!/usr/bin/env bash
# Optional L2 runtime: install Incus on Ubuntu (requires sudo TTY).
# Note: LXD snap may be present but inactive on this host; prefer Incus going forward.
set -euo pipefail

if [[ "$(id -u)" -ne 0 ]]; then
  echo "Re-running with sudo..."
  exec sudo -E "$0" "$@"
fi

export DEBIAN_FRONTEND=noninteractive

if command -v incus >/dev/null 2>&1 && systemctl is-active --quiet incus.socket 2>/dev/null; then
  echo "Incus already installed and active."
  exit 0
fi

CODENAME="$(. /etc/os-release && echo "$VERSION_CODENAME")"
ARCH="$(dpkg --print-architecture)"

install -d -m 0755 /etc/apt/keyrings
curl -fsSL https://pkgs.zabbly.com/key.asc | gpg --dearmor -o /etc/apt/keyrings/zabbly.gpg

cat > /etc/apt/sources.list.d/zabbly-incus-stable.sources <<EOF
Enabled: yes
Types: deb
URIs: https://pkgs.zabbly.com/incus/stable
Suites: ${CODENAME}
Components: main
Architectures: ${ARCH}
Signed-By: /etc/apt/keyrings/zabbly.gpg
EOF

apt-get update -qq
apt-get install -y -qq incus

mkdir -p /media/diestrin/data/forge/incus
if ! incus info >/dev/null 2>&1; then
  # Non-interactive init; dir backend (data stays on large volume when configured).
  incus admin init --auto || true
fi

if [[ -n "${SUDO_USER:-}" ]]; then
  usermod -aG incus-admin "$SUDO_USER" || true
  echo "Added $SUDO_USER to incus-admin — re-login (or newgrp) before using incus."
fi

systemctl enable --now incus.socket incus.service 2>/dev/null || true
echo "Incus install complete. Verify: incus version && incus list"
