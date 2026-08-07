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

## Policies (examples in git)

| Policy | Path | Use |
| --- | --- | --- |
| `platform` | `secret/data/forge/*` | Operators / ESO |
| `ci-deployer` | `secret/data/forge/ci/*` | CI read |
| `agent` | `secret/data/forge/agents/*` | AppRole for Phase 4 workers |

AppRole role: `forge-agent` (short TTL).

## ESO

`ClusterSecretStore/vault-backend` uses Secret `forge-system/vault-eso-token`.
Example: `ExternalSecret` → `forge-system/ntfy` from `secret/forge/ntfy`.

## Bootstrap migration

After secrets live in Vault, remove plaintext leftovers under
`/media/diestrin/data/secrets/bootstrap/` except age key / inventory notes needed
for disaster recovery. Keep Vault unseal material forever offline.
