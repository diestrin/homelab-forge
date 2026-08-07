#!/usr/bin/env bash
# Login with Vault AppRole forge-agent; export VAULT_TOKEN (short-lived).
# Role/secret ids live OUTSIDE git (see docs/runbooks/factory.md).
set -euo pipefail

SECRETS_ROOT="${FORGE_SECRETS_ROOT:-/media/diestrin/data/secrets}"
APPROLE_ENV="${FORGE_APPROLE_ENV:-$SECRETS_ROOT/vault/approle-forge-agent.env}"
VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

usage() {
  cat <<'EOF'
Usage: vault-agent-login.sh [--print-token] [--fetch PATH KEY]

  Loads role_id/secret_id from FORGE_APPROLE_ENV (default:
  /media/diestrin/data/secrets/vault/approle-forge-agent.env), logs in, and
  exports VAULT_TOKEN in the current shell when sourced from bash:

    source factory/scripts/vault-agent-login.sh

  --print-token   print token to stdout (for wrappers)
  --fetch P K     after login, vault kv get -field=K secret/P
EOF
}

PRINT=0
FETCH_PATH=""
FETCH_KEY=""
# When sourced, only consume flags if any were passed intentionally.
while [[ $# -gt 0 ]]; do
  case "$1" in
    --print-token) PRINT=1; shift ;;
    --fetch)
      FETCH_PATH="${2:-}"; FETCH_KEY="${3:-}"
      [[ -n "$FETCH_PATH" && -n "$FETCH_KEY" ]] || { echo "usage: --fetch PATH KEY" >&2; return 2 2>/dev/null || exit 2; }
      shift 3
      ;;
    -h|--help) usage; return 0 2>/dev/null || exit 0 ;;
    *) echo "unknown arg: $1" >&2; usage >&2; return 2 2>/dev/null || exit 2 ;;
  esac
done

command -v vault >/dev/null || { echo "vault CLI required" >&2; return 1 2>/dev/null || exit 1; }
command -v jq >/dev/null || { echo "jq required" >&2; return 1 2>/dev/null || exit 1; }

if [[ ! -f "$APPROLE_ENV" ]]; then
  cat >&2 <<EOF
missing AppRole env: $APPROLE_ENV

Create once (Vault unsealed, root/operator token):

  export VAULT_ADDR=$VAULT_ADDR
  export VAULT_TOKEN=\$(cat $SECRETS_ROOT/vault/root.token)
  ROLE_ID=\$(vault read -field=role_id auth/approle/role/forge-agent/role-id)
  SECRET_ID=\$(vault write -field=secret_id -f auth/approle/role/forge-agent/secret-id)
  umask 077
  printf 'ROLE_ID=%s\nSECRET_ID=%s\n' "\$ROLE_ID" "\$SECRET_ID" > "$APPROLE_ENV"
  chmod 600 "$APPROLE_ENV"

Put worker secrets under secret/forge/agents/* (GitHub App: app_id/client_id + private_key).
EOF
  return 1 2>/dev/null || exit 1
fi

# shellcheck disable=SC1090
source "$APPROLE_ENV"
[[ -n "${ROLE_ID:-}" && -n "${SECRET_ID:-}" ]] || {
  echo "ROLE_ID and SECRET_ID required in $APPROLE_ENV" >&2
  return 1 2>/dev/null || exit 1
}

export VAULT_ADDR
LOGIN_JSON="$(vault write -format=json auth/approle/login role_id="$ROLE_ID" secret_id="$SECRET_ID")"
VAULT_TOKEN="$(jq -r '.auth.client_token' <<<"$LOGIN_JSON")"
export VAULT_TOKEN
TTL="$(jq -r '.auth.lease_duration' <<<"$LOGIN_JSON")"

if [[ "$PRINT" -eq 1 ]]; then
  printf '%s\n' "$VAULT_TOKEN"
fi

if [[ -n "$FETCH_PATH" ]]; then
  vault kv get -field="$FETCH_KEY" "secret/$FETCH_PATH"
fi

# When executed as a program (bash), remind about TTL if nothing was printed.
_SOURCED=0
(return 0 2>/dev/null) && _SOURCED=1 || true
if [[ "$_SOURCED" -eq 0 && "$PRINT" -eq 0 && -z "$FETCH_PATH" ]]; then
  echo "VAULT_TOKEN exported in this process only (ttl=${TTL}s). Prefer: source $0" >&2
fi
