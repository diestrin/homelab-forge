#!/usr/bin/env bash
# Install External Secrets Operator (pinned) into forge-system.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ESO_VERSION="${ESO_VERSION:-v2.8.0}"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

echo "==> Ensuring forge-system namespace"
kubectl apply -k "$REPO_ROOT/k8s/platform/namespaces"

echo "==> Applying ESO ${ESO_VERSION}"
# Official release bundle targets namespace external-secrets by default in some versions;
# prefer Helm-free kubectl if a single manifest exists.
if curl -sfI "https://github.com/external-secrets/external-secrets/releases/download/${ESO_VERSION}/external-secrets.yaml" >/dev/null; then
  # CRD annotations exceed kubectl client-side apply size limit — use SSA.
  kubectl apply --server-side --force-conflicts \
    -f "https://github.com/external-secrets/external-secrets/releases/download/${ESO_VERSION}/external-secrets.yaml"
else
  echo "==> Bundle missing; installing via helm chart into forge-system"
  if ! command -v helm >/dev/null 2>&1; then
    echo "error: helm required to install ESO ${ESO_VERSION}" >&2
    exit 1
  fi
  helm repo add external-secrets https://charts.external-secrets.io 2>/dev/null || true
  helm repo update external-secrets
  helm upgrade --install external-secrets external-secrets/external-secrets \
    --namespace forge-system \
    --version "${ESO_VERSION#v}" \
    --set installCRDs=true \
    --wait
fi

echo "==> Waiting for ESO"
kubectl wait --for=condition=Available -n forge-system deploy -l app.kubernetes.io/name=external-secrets --timeout=180s 2>/dev/null ||
  kubectl wait --for=condition=Available -n external-secrets deploy -l app.kubernetes.io/name=external-secrets --timeout=180s

echo "OK: ESO installed (apply ClusterSecretStore after Vault token exists)"
