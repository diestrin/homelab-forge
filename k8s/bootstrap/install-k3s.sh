#!/usr/bin/env bash
# Phase 3: install single-node k3s with data-dir on the data disk (ADR-003).
# Idempotent: re-run is safe if the same version is already installed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
INSTALL_K3S_VERSION="${INSTALL_K3S_VERSION:-v1.36.3+k3s1}"
K3S_DATA_DIR="${K3S_DATA_DIR:-/media/diestrin/data/forge/k3s}"
LOCAL_PATH_DIR="${LOCAL_PATH_DIR:-/media/diestrin/data/forge/k3s/local-path}"
ALLOW_USER="${ALLOW_USER:-diestrin}"
KUBECONFIG_USER_PATH="/home/${ALLOW_USER}/.kube/config"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Re-running with sudo..."
  exec sudo INSTALL_K3S_VERSION="$INSTALL_K3S_VERSION" \
    K3S_DATA_DIR="$K3S_DATA_DIR" \
    LOCAL_PATH_DIR="$LOCAL_PATH_DIR" \
    ALLOW_USER="$ALLOW_USER" \
    bash "$0" "$@"
fi

echo "==> Ensuring data directories"
mkdir -p "$K3S_DATA_DIR" "$LOCAL_PATH_DIR"
chmod 755 /media/diestrin/data/forge/k3s

if command -v k3s >/dev/null 2>&1 && systemctl is-active --quiet k3s; then
  current="$(k3s --version | head -1 || true)"
  echo "==> k3s already active: $current"
  if k3s --version 2>/dev/null | grep -q "${INSTALL_K3S_VERSION%%+*}"; then
    echo "==> Version pin matches; skipping reinstall"
  else
    echo "warning: running k3s differs from pin ${INSTALL_K3S_VERSION}; not auto-upgrading" >&2
  fi
else
  echo "==> Installing k3s ${INSTALL_K3S_VERSION}"
  # Note: args after `sh -s -` are passed to the installer (the lone `-` is required).
  curl -sfL https://get.k3s.io | INSTALL_K3S_VERSION="$INSTALL_K3S_VERSION" sh -s - \
    --write-kubeconfig-mode 644 \
    --data-dir "$K3S_DATA_DIR" \
    --default-local-storage-path "$LOCAL_PATH_DIR" \
    --tls-san localpower.diegobarahona.com \
    --tls-san 127.0.0.1
fi

echo "==> Waiting for node Ready"
export KUBECONFIG=/etc/rancher/k3s/k3s.yaml
for _ in $(seq 1 60); do
  if kubectl get nodes --no-headers 2>/dev/null | grep -q ' Ready'; then
    break
  fi
  sleep 2
done
kubectl get nodes -o wide

echo "==> Installing user kubeconfig for ${ALLOW_USER}"
install -d -o "$ALLOW_USER" -g "$ALLOW_USER" -m 700 "$(dirname "$KUBECONFIG_USER_PATH")"
install -o "$ALLOW_USER" -g "$ALLOW_USER" -m 600 /etc/rancher/k3s/k3s.yaml "$KUBECONFIG_USER_PATH"
# Point API at localhost so the user copy works without root.
sed -i 's#server: https://127.0.0.1:6443#server: https://127.0.0.1:6443#' "$KUBECONFIG_USER_PATH" || true
# k3s default already uses 127.0.0.1; ensure readable
chown "$ALLOW_USER:$ALLOW_USER" "$KUBECONFIG_USER_PATH"

echo "==> Coexistence note: rootless Docker remains for L1/L4; k3s uses containerd"
echo "OK: k3s ${INSTALL_K3S_VERSION} data-dir=${K3S_DATA_DIR}"
echo "Next: ${REPO_ROOT}/k8s/bootstrap/ufw-k3s.sh"
