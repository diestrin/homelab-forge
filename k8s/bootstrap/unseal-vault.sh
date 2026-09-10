#!/usr/bin/env bash
# After k3s starts: unseal Vault if needed, then restart External Secrets so
# ClusterSecretStore does not stay cached as "Vault is sealed".
#
# Unseal material is read from INIT_JSON on the host (never git). Safe to run
# when Vault is already unsealed (idempotent).
set -euo pipefail

INIT_JSON="${INIT_JSON:-/media/diestrin/data/secrets/vault/init.json}"
VAULT_NS="${VAULT_NS:-forge-system}"
TIMEOUT_SECS="${TIMEOUT_SECS:-180}"

if [[ "$(id -u)" -eq 0 && -x /usr/local/bin/k3s ]]; then
  kubectl() { /usr/local/bin/k3s kubectl "$@"; }
fi

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

die() {
  printf '%s error: %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*" >&2
  exit 1
}

wait_for_api() {
  local deadline=$((SECONDS + TIMEOUT_SECS))
  while ((SECONDS < deadline)); do
    if kubectl get --raw=/readyz >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done
  die "kube-apiserver not ready after ${TIMEOUT_SECS}s"
}

wait_for_vault() {
  local deadline=$((SECONDS + TIMEOUT_SECS))
  while ((SECONDS < deadline)); do
    if kubectl -n "$VAULT_NS" get deploy vault >/dev/null 2>&1; then
      if kubectl -n "$VAULT_NS" rollout status deploy/vault --timeout=15s >/dev/null 2>&1; then
        return 0
      fi
    fi
    sleep 3
  done
  die "Vault deploy not ready after ${TIMEOUT_SECS}s"
}

vault_status_json() {
  kubectl -n "$VAULT_NS" exec deploy/vault -- vault status -format=json 2>/dev/null || true
}

vault_is_sealed() {
  python3 -c 'import json,sys; d=json.loads(sys.stdin.read() or "{}"); sys.exit(0 if d.get("sealed") else 1)'
}

eso_restart() {
  if kubectl -n default get deploy external-secrets >/dev/null 2>&1; then
    kubectl -n default rollout restart deploy/external-secrets
    kubectl -n default rollout status deploy/external-secrets --timeout=90s
    return 0
  fi
  if kubectl -n forge-system get deploy -l app.kubernetes.io/name=external-secrets -o name 2>/dev/null | grep -q .; then
    kubectl -n forge-system rollout restart deploy -l app.kubernetes.io/name=external-secrets
    kubectl -n forge-system rollout status deploy -l app.kubernetes.io/name=external-secrets --timeout=90s
    return 0
  fi
  die "External Secrets operator deploy not found"
}

wait_for_store() {
  local deadline=$((SECONDS + TIMEOUT_SECS))
  local ready
  while ((SECONDS < deadline)); do
    ready="$(kubectl get clustersecretstore vault-backend -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}' 2>/dev/null || true)"
    if [[ "$ready" == "True" ]]; then
      return 0
    fi
    sleep 3
  done
  die "ClusterSecretStore vault-backend not Ready after ${TIMEOUT_SECS}s"
}

[[ -f "$INIT_JSON" ]] || die "missing $INIT_JSON"
[[ -r "$INIT_JSON" ]] || die "cannot read $INIT_JSON"

log "waiting for kube-apiserver"
wait_for_api
log "waiting for Vault"
wait_for_vault

STATUS="$(vault_status_json)"
[[ -n "$STATUS" ]] || die "could not read Vault seal status"
if printf '%s' "$STATUS" | vault_is_sealed; then
  log "Vault is sealed; unsealing"
  UNSEAL_KEY="$(INIT_JSON="$INIT_JSON" python3 -c 'import json,os,sys
p=os.environ["INIT_JSON"]
keys=json.load(open(p, encoding="utf-8")).get("unseal_keys_b64") or []
if not keys:
    sys.exit("init.json has no unseal_keys_b64")
print(keys[0])
')"
  printf '%s\n' "$UNSEAL_KEY" | kubectl -n "$VAULT_NS" exec -i deploy/vault -- \
    sh -c 'read -r k && vault operator unseal "$k" >/dev/null'
  unset UNSEAL_KEY
  STATUS="$(vault_status_json)"
  if printf '%s' "$STATUS" | vault_is_sealed; then
    die "Vault still sealed after unseal"
  fi
  log "Vault unsealed"
else
  log "Vault already unsealed"
fi

log "restarting External Secrets operator"
eso_restart
log "waiting for ClusterSecretStore vault-backend"
wait_for_store
log "OK: Vault unsealed and ESO store Ready"
