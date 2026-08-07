#!/usr/bin/env bash
# Install cert-manager (pinned) and ClusterIssuers with ACME email from env or age store.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
CERT_MANAGER_VERSION="${CERT_MANAGER_VERSION:-v1.21.1}"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

ACME_EMAIL="${ACME_EMAIL:-}"
if [[ -z "$ACME_EMAIL" && -f /media/diestrin/data/secrets/bootstrap/acme-email ]]; then
  ACME_EMAIL="$(tr -d '[:space:]' </media/diestrin/data/secrets/bootstrap/acme-email)"
fi
if [[ -z "$ACME_EMAIL" ]]; then
  echo "error: set ACME_EMAIL or create /media/diestrin/data/secrets/bootstrap/acme-email" >&2
  exit 1
fi

echo "==> Applying cert-manager ${CERT_MANAGER_VERSION}"
kubectl apply -f "https://github.com/cert-manager/cert-manager/releases/download/${CERT_MANAGER_VERSION}/cert-manager.yaml"

echo "==> Waiting for cert-manager webhook"
kubectl -n cert-manager wait --for=condition=Available deploy/cert-manager-webhook --timeout=180s
kubectl -n cert-manager wait --for=condition=Available deploy/cert-manager --timeout=180s
kubectl -n cert-manager wait --for=condition=Available deploy/cert-manager-cainjector --timeout=180s

echo "==> Applying ClusterIssuers"
sed "s/ACME_EMAIL_PLACEHOLDER/${ACME_EMAIL}/g" \
  "$REPO_ROOT/k8s/platform/cert-manager/cluster-issuer.yaml" |
  kubectl apply -f -

echo "OK: cert-manager + letsencrypt-prod/staging issuers"
