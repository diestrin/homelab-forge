#!/usr/bin/env bash
# Phase 3: reconcile UFW with k3s (flannel / CNI) and open Ingress 80/443.
# Never disables UFW.
set -euo pipefail

OPEN_HTTP="${OPEN_HTTP:-1}"
LAN_CIDR="${LAN_CIDR:-192.168.86.0/24}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Re-running with sudo..."
  exec sudo OPEN_HTTP="$OPEN_HTTP" LAN_CIDR="$LAN_CIDR" bash "$0" "$@"
fi

command -v ufw >/dev/null 2>&1 || {
  echo "error: ufw not installed" >&2
  exit 1
}

echo "==> Allow CNI / flannel interfaces through UFW"
# Idempotent: ufw allow duplicates are ignored / renumbered harmlessly.
ufw allow in on cni0 comment 'k3s cni0' || true
ufw allow out on cni0 comment 'k3s cni0' || true
ufw allow in on flannel.1 comment 'k3s flannel' || true
ufw allow out on flannel.1 comment 'k3s flannel' || true

echo "==> Allow pod/service CIDR forwarding"
ufw route allow from 10.42.0.0/16 to any comment 'k3s pods' || true
ufw route allow from 10.43.0.0/16 to any comment 'k3s services' || true

echo "==> Allow API from localhost + LAN (not WAN)"
ufw allow from 127.0.0.1 to any port 6443 proto tcp comment 'k3s API localhost' || true
ufw allow from "${LAN_CIDR}" to any port 6443 proto tcp comment 'k3s API LAN' || true

if [[ "$OPEN_HTTP" == "1" ]]; then
  echo "==> Opening host 80/443 for Traefik Ingress"
  ufw allow 80/tcp comment 'homelab-forge Ingress HTTP'
  ufw allow 443/tcp comment 'homelab-forge Ingress HTTPS'
else
  echo "==> OPEN_HTTP=0 — leaving 80/443 closed"
fi

echo "==> Reloading UFW"
ufw reload
ufw status verbose

echo "OK: UFW reconciled with k3s. Confirm router forwards 80/443 to this host before LE issuance."
