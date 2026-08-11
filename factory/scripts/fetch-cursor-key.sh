#!/usr/bin/env bash
# Mint CURSOR_API_KEY from Vault secret/forge/agents/cursor (ADR-009).
# Prints the key to stdout; do not log it. Requires VAULT_TOKEN (+ VAULT_ADDR).
set -euo pipefail

VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
SECRET_PATH="${FORGE_CURSOR_VAULT_PATH:-secret/forge/agents/cursor}"

die() { echo "fetch-cursor-key: $*" >&2; exit 1; }
command -v vault >/dev/null || die "vault CLI required"
[[ -n "${VAULT_TOKEN:-}" ]] || die "VAULT_TOKEN required (AppRole login first)"

export VAULT_ADDR
# Prefer api_key; accept CURSOR_API_KEY as alias field name
RAW="$(vault kv get -format=json "$SECRET_PATH" 2>/dev/null)" || die "cannot read $SECRET_PATH"
KEY="$(jq -r '.data.data.api_key // .data.data.CURSOR_API_KEY // empty' <<<"$RAW")"
[[ -n "$KEY" && "$KEY" != "null" ]] || die "no api_key in $SECRET_PATH"
printf '%s' "$KEY"
