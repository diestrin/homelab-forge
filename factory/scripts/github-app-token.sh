#!/usr/bin/env bash
# Fetch GitHub App credentials from Vault and mint an installation access token.
# Prints token to stdout. Does not use personal user PATs.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
VAULT_PATH="${FORGE_GITHUB_VAULT_PATH:-secret/forge/agents/github}"
OWNER="${GITHUB_OWNER:-diestrin}"
REPO="${GITHUB_REPO:-homelab-forge}"

die() { echo "github-app-token: $*" >&2; exit 1; }

command -v vault >/dev/null || die "vault CLI required"
command -v python3 >/dev/null || die "python3 required"
command -v jq >/dev/null || die "jq required"
[[ -n "${VAULT_TOKEN:-}" ]] || die "VAULT_TOKEN not set (source factory/scripts/vault-agent-login.sh first)"
export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"

# Pull JSON; tolerate missing optional fields.
RAW="$(vault kv get -format=json "$VAULT_PATH" 2>/dev/null)" \
  || die "missing $VAULT_PATH — see docs/runbooks/factory.md"

DATA="$(jq -c '.data.data // .data' <<<"$RAW")"

# Prefer App credentials; fall back to legacy pre-minted token field only if App fields absent.
HAS_KEY="$(jq -r '(.private_key // "") | length' <<<"$DATA")"
HAS_APP="$(jq -r '(.app_id // "") | tostring | length' <<<"$DATA")"
if [[ "$HAS_KEY" -gt 0 && "$HAS_APP" -gt 0 ]]; then
  jq -c '{
    app_id: (.app_id // "" | tostring),
    client_id: (.client_id // "" | tostring),
    private_key: .private_key,
    installation_id: (.installation_id // "" | tostring)
  }' <<<"$DATA" \
    | python3 "$REPO_ROOT/factory/scripts/github-app-token.py" --from-json \
        --owner "$OWNER" --repo "$REPO"
  exit 0
fi

LEGACY="$(jq -r '.token // empty' <<<"$DATA")"
if [[ -n "$LEGACY" ]]; then
  echo "github-app-token: warning: using legacy secret/forge/agents/github token= (migrate to App private_key)" >&2
  printf '%s\n' "$LEGACY"
  exit 0
fi

die "Vault path $VAULT_PATH needs private_key + numeric app_id (client_id/client_secret optional). client_secret alone is not enough."
