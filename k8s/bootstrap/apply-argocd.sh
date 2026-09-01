#!/usr/bin/env bash
# One-time Argo CD install into forge-system (ADR-008).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ARGO_VERSION="${ARGO_VERSION:-v3.5.0}"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

echo "==> Ensuring forge-system"
kubectl apply -k "$REPO_ROOT/k8s/platform/namespaces"

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "==> Downloading Argo CD ${ARGO_VERSION} manifests"
curl -sfL "https://raw.githubusercontent.com/argoproj/argo-cd/${ARGO_VERSION}/manifests/install.yaml" \
  -o "$TMP/install.yaml"

# Rewrite default namespace argocd -> forge-system
sed -i 's/namespace: argocd/namespace: forge-system/g' "$TMP/install.yaml"

echo "==> Applying Argo CD into forge-system (server-side; CRD annotations are large)"
kubectl apply --server-side --force-conflicts -n forge-system -f "$TMP/install.yaml"

echo "==> Waiting for argocd-server"
kubectl -n forge-system rollout status deploy/argocd-server --timeout=300s

echo "==> Sizing application-controller (Helm apps exceed LimitRange default 512Mi)"
kubectl -n forge-system set resources statefulset/argocd-application-controller \
  -c=argocd-application-controller \
  --requests=cpu=100m,memory=256Mi \
  --limits=cpu=1000m,memory=1536Mi
kubectl -n forge-system rollout status statefulset/argocd-application-controller --timeout=300s

echo "==> Initial admin password (change after first login):"
kubectl -n forge-system get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' 2>/dev/null | base64 -d || true
echo

echo "Access UI via SSH tunnel: ssh -L 8080:localhost:8080 … then"
echo "  kubectl -n forge-system port-forward svc/argocd-server 8080:443"
echo "Apply root app: kubectl apply -f $REPO_ROOT/k8s/apps/root-app.yaml"
