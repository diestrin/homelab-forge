#!/usr/bin/env bash
# Install the boot-time Vault unseal oneshot (not Argo-managed).
# Run as root on the k3s host after cloning this repo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SRC_SCRIPT="$REPO_ROOT/k8s/bootstrap/unseal-vault.sh"
SRC_UNIT="$REPO_ROOT/k8s/bootstrap/systemd/forge-vault-unseal.service"

if [[ "$(id -u)" -ne 0 ]]; then
  echo "error: run as root (sudo $0)" >&2
  exit 1
fi

install -m 0755 "$SRC_SCRIPT" /usr/local/sbin/forge-vault-unseal
install -m 0644 "$SRC_UNIT" /etc/systemd/system/forge-vault-unseal.service
systemctl daemon-reload
systemctl enable forge-vault-unseal.service
echo "enabled forge-vault-unseal.service"
echo "start now with: systemctl start forge-vault-unseal.service"
