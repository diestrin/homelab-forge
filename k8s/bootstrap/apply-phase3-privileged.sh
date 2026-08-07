#!/usr/bin/env bash
# Privileged Phase 3 host steps (requires sudo TTY), then cluster bootstrap as user.
#   ./k8s/bootstrap/apply-phase3-privileged.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

echo "==> Caching sudo credentials"
sudo -v

echo "==> 1/5 Install k3s"
"$REPO_ROOT/k8s/bootstrap/install-k3s.sh"

echo "==> 2/5 Namespaces + network policies (pre-UFW open so Traefik exists)"
# Ensure kubectl works
export KUBECONFIG=/home/${SUDO_USER:-$USER}/.kube/config
kubectl apply -k "$REPO_ROOT/k8s/platform/namespaces"
kubectl apply -k "$REPO_ROOT/k8s/platform/network-policies"

echo "==> 3/5 UFW + open 80/443"
"$REPO_ROOT/k8s/bootstrap/ufw-k3s.sh"

echo "==> 4/5 cert-manager + issuers"
# Drop sudo cache for clarity; kubectl as invoking user
sudo -u "${SUDO_USER:-$USER}" -E env KUBECONFIG="/home/${SUDO_USER:-$USER}/.kube/config" \
  bash "$REPO_ROOT/k8s/bootstrap/apply-cert-manager.sh"

echo "==> 5/5 Demo hello (HTTP first; LE needs router forward)"
sudo -u "${SUDO_USER:-$USER}" -E env KUBECONFIG="/home/${SUDO_USER:-$USER}/.kube/config" \
  kubectl apply -k "$REPO_ROOT/k8s/apps/forge-demo-hello"

echo
echo "==> Privileged Phase 3 host steps complete."
echo "    NEXT (operator): enable router port-forward TCP 80/443 → this host."
echo "    Then: kubectl -n forge-demo get certificate,ingress"
echo "    Then: ./k8s/bootstrap/apply-external-secrets.sh"
echo "          ./k8s/bootstrap/init-vault.sh"
echo "          ./k8s/bootstrap/apply-argocd.sh"
echo "          kubectl apply -f k8s/apps/root-app.yaml"
