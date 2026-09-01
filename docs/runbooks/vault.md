# Vault (Phase 3)

HashiCorp Vault is the secrets system of record (ADR-007). Runs in `forge-system`
with file storage on a `local-path` PVC under `/media/diestrin/data/forge/k3s/local-path`.

## Access

- Service: `http://vault.forge-system.svc:8200` (ClusterIP only — **not** on Ingress).
- From the host:

```bash
kubectl -n forge-system port-forward svc/vault 8200:8200
export VAULT_ADDR=http://127.0.0.1:8200
export VAULT_TOKEN="$(cat /media/diestrin/data/secrets/vault/root.token)"
vault status
```

Or SSH tunnel from a laptop: `ssh -L 8200:127.0.0.1:8200 localpower` then port-forward on the NUC.

## Init / unseal (single-node)

Bootstrap: `./k8s/bootstrap/init-vault.sh`

- Shamir: **1 share / threshold 1** (homelab).
- Init JSON (unseal key + root token): `/media/diestrin/data/secrets/vault/init.json` (mode 600).
- **Back up `init.json` offline.** Never commit it.

After every reboot Vault seals:

```bash
kubectl -n forge-system port-forward svc/vault 8200:8200 &
export VAULT_ADDR=http://127.0.0.1:8200
vault operator unseal "$(jq -r '.unseal_keys_b64[0]' /media/diestrin/data/secrets/vault/init.json)"
```

Phase 3 verified: `vault operator seal` then unseal with the stored key succeeds; Ingress HTTPS continues via Traefik while Vault is sealed (demo app does not depend on Vault for serving).

## Policies (examples in git)

| Policy | Path | Use |
| --- | --- | --- |
| `platform` | `secret/data/forge/*`, `secret/data/family-agile/*` | Operators / ESO |
| `ci-deployer` | `secret/data/forge/ci/*` | CI read |
| `agent` | `secret/data/forge/agents/*` | AppRole for Phase 4 workers |

AppRole role: `forge-agent` (15m login token; non-expiring `secret_id` on the host
file). Worker login helper:
[`factory/scripts/vault-agent-login.sh`](../../factory/scripts/vault-agent-login.sh).
GitHub bot identity: [`factory/scripts/github-app-token.sh`](../../factory/scripts/github-app-token.sh)
reads `secret/forge/agents/github` (`app_id`, `private_key`, optional `client_id` /
`client_secret` / `installation_id`) and mints an installation token (see
[`factory.md`](./factory.md)).

Slack + Cursor SDK (ADR-009):

| Vault path | Fields (examples) | Use |
| --- | --- | --- |
| `secret/forge/agents/slack` | `bot_token`, `app_token`, `signing_secret`, `allowlist_user_ids` | Socket Mode orchestrator |
| `secret/forge/agents/cursor` | `api_key` | Cursor SDK orchestrator + worker |

`forge-agent` AppRole already covers `secret/data/forge/agents/*`. Fetch Cursor key:
[`factory/scripts/fetch-cursor-key.sh`](../../factory/scripts/fetch-cursor-key.sh).

## ESO

`ClusterSecretStore/vault-backend` uses Secret `forge-system/vault-eso-token`
(token created with the `platform` policy). Example: `ExternalSecret` →
`forge-system/ntfy` from `secret/forge/ntfy`. Family Agile sync reads
`secret/family-agile/notion` (`token`) and `secret/family-agile/habitica`
(`<member>_user` and `<member>_key` for each account).

After unseal, if the store stays `Ready=False` with "Vault is sealed", restart
the operator so it re-validates:

```bash
kubectl -n default rollout restart deploy/external-secrets
kubectl get clustersecretstore vault-backend   # Ready True
```

## Bootstrap migration

After secrets live in Vault, remove plaintext leftovers under
`/media/diestrin/data/secrets/bootstrap/` except age key / inventory notes needed
for disaster recovery. Keep Vault unseal material forever offline.
