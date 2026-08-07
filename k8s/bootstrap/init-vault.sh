#!/usr/bin/env bash
# Init/unseal Vault; write example policies; create ESO token; migrate ntfy if present.
# Secrets written under /media/diestrin/data/secrets/vault/ (outside git).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SECRETS_DIR="${SECRETS_DIR:-/media/diestrin/data/secrets/vault}"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"
export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

mkdir -p "$SECRETS_DIR"
chmod 700 "$SECRETS_DIR"

echo "==> Applying Vault manifests"
kubectl apply -k "$REPO_ROOT/k8s/platform/namespaces"
kubectl apply -k "$REPO_ROOT/k8s/platform/vault"

echo "==> Waiting for Vault pod"
kubectl -n forge-system rollout status deploy/vault --timeout=180s

# Port-forward in background
kubectl -n forge-system port-forward svc/vault 8200:8200 >/tmp/vault-pf.log 2>&1 &
PF_PID=$!
trap 'kill $PF_PID 2>/dev/null || true' EXIT
sleep 3

if ! command -v vault >/dev/null 2>&1; then
  echo "error: vault CLI required on PATH (install via Nix HM or download)" >&2
  exit 1
fi

STATUS="$(vault status -format=json 2>/dev/null || echo '{}')"
INITIALIZED="$(echo "$STATUS" | jq -r '.initialized // false')"

if [[ "$INITIALIZED" != "true" ]]; then
  echo "==> Initializing Vault (1 share / threshold 1 for single-node homelab)"
  vault operator init -key-shares=1 -key-threshold=1 -format=json |
    tee "$SECRETS_DIR/init.json" >/dev/null
  chmod 600 "$SECRETS_DIR/init.json"
  echo "Wrote $SECRETS_DIR/init.json — back up offline"
fi

UNSEAL_KEY="$(jq -r '.unseal_keys_b64[0]' "$SECRETS_DIR/init.json")"
ROOT_TOKEN="$(jq -r '.root_token' "$SECRETS_DIR/init.json")"

SEALED="$(vault status -format=json | jq -r '.sealed')"
if [[ "$SEALED" == "true" ]]; then
  echo "==> Unsealing"
  vault operator unseal "$UNSEAL_KEY" >/dev/null
fi

export VAULT_TOKEN="$ROOT_TOKEN"
echo "$ROOT_TOKEN" >"$SECRETS_DIR/root.token"
chmod 600 "$SECRETS_DIR/root.token"

echo "==> Enabling KV v2 at secret/"
vault secrets enable -path=secret kv-v2 2>/dev/null || true

echo "==> Writing policies"
vault policy write platform "$REPO_ROOT/k8s/platform/vault/policies/platform.hcl"
vault policy write ci-deployer "$REPO_ROOT/k8s/platform/vault/policies/ci-deployer.hcl"
vault policy write agent "$REPO_ROOT/k8s/platform/vault/policies/agent.hcl"

echo "==> Enabling AppRole for agents"
vault auth enable approle 2>/dev/null || true
vault write auth/approle/role/forge-agent \
  token_policies="agent" \
  token_ttl=15m \
  token_max_ttl=1h \
  secret_id_ttl=24h

echo "==> Creating ESO token"
ESO_TOKEN="$(vault token create -policy=platform -period=768h -orphan -format=json | jq -r .auth.client_token)"
kubectl -n forge-system create secret generic vault-eso-token \
  --from-literal=token="$ESO_TOKEN" \
  --dry-run=client -o yaml | kubectl apply -f -

# Migrate ntfy from age store if decryptable (toml/yaml-ish url = "...")
if [[ -f /media/diestrin/data/secrets/bootstrap/secrets.age && -f /media/diestrin/data/secrets/bootstrap/age-key.txt ]]; then
  if command -v age >/dev/null 2>&1; then
    echo "==> Migrating bootstrap secrets into Vault (best-effort)"
    TMP_SECRETS="$(mktemp)"
    if age -d -i /media/diestrin/data/secrets/bootstrap/age-key.txt \
      /media/diestrin/data/secrets/bootstrap/secrets.age >"$TMP_SECRETS" 2>/dev/null; then
      NTFY="$(sed -nE 's/^[[:space:]]*url[[:space:]]*=[[:space:]]*"([^"]+)".*/\1/p' "$TMP_SECRETS" | head -1 || true)"
      if [[ -z "${NTFY:-}" ]]; then
        NTFY="$(grep -E '^(NTFY_URL|ntfy_url)=' "$TMP_SECRETS" | head -1 | cut -d= -f2- | tr -d '"' || true)"
      fi
      if [[ -n "${NTFY:-}" ]]; then
        vault kv put secret/forge/ntfy url="$NTFY"
        echo "    wrote secret/forge/ntfy"
      fi
    fi
    rm -f "$TMP_SECRETS"
  fi
fi

echo "==> Applying ClusterSecretStore"
kubectl apply -k "$REPO_ROOT/k8s/platform/external-secrets"

echo "OK: Vault initialized/unsealed. Unseal after reboot:"
echo "  kubectl -n forge-system port-forward svc/vault 8200:8200 &"
echo "  vault operator unseal \$(jq -r '.unseal_keys_b64[0]' $SECRETS_DIR/init.json)"
