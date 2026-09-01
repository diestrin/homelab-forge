# Operations — cold start & day-2 checks

Single-page operator runbook: what to do after a reboot (or power loss) and how to
verify the platform is healthy. Public and redacted — personal externals (router UI,
exact forward mappings, ntfy topic) live in the private bootstrap inventory outside
git (`/media/diestrin/data/secrets/bootstrap/inventory.private.md`).

## Cold-start sequence (after reboot)

Everything below assumes SSH access to the host as the operator user.

### 1. Host basics

k3s, rootless Docker, fail2ban, and UFW start automatically. Verify:

```bash
sudo ufw status verbose                 # default-deny, 22 limited, 80/443 allowed
sudo fail2ban-client status sshd
systemctl --user status host-watch.timer
kubectl get nodes                       # Ready
```

### 2. WAN path (No-IP + router)

DNS and forwarding are external state; nothing to start, only to verify:

```bash
dig +short localpower.diegobarahona.com   # resolves to home public IP
curl -fsSI https://localpower.diegobarahona.com | head -3
```

- The hostname is a CNAME to an operator-controlled DDNS (No-IP) name; the router
  keeps the A record fresh and forwards 22/80/443 to the NUC.
- If DNS is stale: check the router's DDNS client status (details in the private
  inventory). If HTTPS fails but DNS is fine, continue — Traefik/LE checks below.

### 3. Unseal Vault

Vault always starts **sealed** (Shamir 1-of-1, ADR-007). Until unsealed, ESO cannot
refresh secrets and factory workers cannot mint tokens. See [vault.md](./vault.md).

```bash
kubectl -n forge-system port-forward svc/vault 8200:8200 &
export VAULT_ADDR=http://127.0.0.1:8200
vault operator unseal "$(jq -r '.unseal_keys_b64[0]' /media/diestrin/data/secrets/vault/init.json)"
vault status                            # Sealed: false
```

Keep the port-forward running (or restart it later) if factory workers need
AppRole logins; the demo app serves fine with Vault sealed.

Confirm ESO re-validated the store (it caches "Vault is sealed" across unseal):

```bash
kubectl get clustersecretstore vault-backend   # Ready True
# If still InvalidProviderConfig / "Vault is sealed":
kubectl -n default rollout restart deploy/external-secrets
```

### 4. Let's Encrypt / Traefik

cert-manager renews automatically while 80/443 are reachable. Verify:

```bash
kubectl get certificates -A             # READY True
kubectl -n forge-system get pods        # traefik, cert-manager, vault, argocd Running
curl -fsS https://localpower.diegobarahona.com | head -3
```

If a cert is stuck: `kubectl describe certificaterequest -A` — the usual cause is
port 80 unreachable from the internet (router forward or UFW), not cert-manager.

### 5. Argo CD

Argo reconnects to GitHub on its own; no action needed. Verify sync:

```bash
kubectl -n forge-system get applications.argoproj.io
```

All apps `Synced`/`Healthy`. Steady-state changes ship by merging to `main`
([gitops.md](./gitops.md)); never `kubectl apply` around Argo.

### 6. Factory (optional)

Only if agent work is queued ([factory.md](./factory.md)):

```bash
./forge factory list                    # review the proposed queue first
systemctl --user start forge-factory-worker
```

The worker needs the Vault port-forward from step 3 for AppRole + GitHub App tokens.

## Quick health matrix

| Check | Command | Expected |
| --- | --- | --- |
| Firewall | `sudo ufw status` | default-deny; 22 limit; 80,443 allow |
| Node | `kubectl get nodes` | `Ready` |
| Vault | `vault status` | `Sealed: false` |
| Certs | `kubectl get certificates -A` | `READY True` |
| GitOps | `kubectl -n forge-system get applications.argoproj.io` | `Synced/Healthy` |
| Public HTTPS | `curl -fsSI https://localpower.diegobarahona.com` | `HTTP/2 200` |
| Grafana | `curl -fsSI https://grafana.localpower.diegobarahona.com` | `HTTP/2 200` or `302` |
| Monitoring | `kubectl -n monitoring get pods` | Prometheus/Grafana/Alertmanager Running |
| IDS | `systemctl --user status host-watch.timer` | active |

## Observability

Prometheus + Grafana stack (TASK-012) runs in namespace `monitoring`, synced by Argo CD
Applications `monitoring` (Helm) and `monitoring-manifests` (rules, ingress, secrets).
See [k8s/platform/metrics/README.md](../../k8s/platform/metrics/README.md)
for Vault paths, dashboard tour, and alert smoke-test procedure.

Vault paths used by ExternalSecrets:

| Path | Purpose |
| --- | --- |
| `secret/forge/ntfy` | ntfy topic URL (Alertmanager webhook) |
| `secret/forge/alerts/slack` | Slack Incoming Webhook for `#forge-alerts` |
| `secret/forge/grafana` | Grafana admin credentials |

After reboot: unseal Vault (step 3) before expecting fresh ESO sync or Grafana login.
The former shell CronJob `forge-node-alert` is superseded by PrometheusRule alerts.

## Related runbooks

- [network-exposure.md](./network-exposure.md) — WAN path, ports, SSH hardening.
- [vault.md](./vault.md) — init, unseal, policies, ESO.
- [gitops.md](./gitops.md) — Argo CD flow from `main`.
- [factory.md](./factory.md) — task queue, worker daemon, review gate.
- [restore.md](./restore.md) — disaster recovery.
- [bootstrap-clean-host.md](./bootstrap-clean-host.md) — provisioning a fresh machine.
