# Current host state

Re-verified 2026-08-07 during Phase 3 on host `localpower`.

## Hardware / OS

| Item | Value |
| --- | --- |
| Machine | Intel NUC, `Intel(R) Core(TM) i7-10710U` (6c/12t) |
| RAM | 62 GiB |
| Root FS | `/` on `nvme0n1p7` ~130G |
| Data FS | `/media/diestrin/data` on `nvme0n1p3` ~562G |
| OS | Ubuntu 24.04.4 LTS (`noble`), kernel `6.8.0-136-generic` |
| Virtualization | VT-x available |
| Primary NIC (Phase 0 default) | Wi-Fi `wlp0s20f3` → LAN `192.168.86.0/24` |
| Ethernet | `eno1` **DOWN** (optional future reliability upgrade; not switched in Phase 0) |

## Phase 0–2 controls

See prior snapshots. SSH key-only, UFW default-deny, fail2ban, host-watch, Nix HM, forge sandbox CLI remain in effect.

## Phase 3 controls (applied)

| Control | Status |
| --- | --- |
| k3s | `v1.36.3+k3s1`; data-dir `/media/diestrin/data/forge/k3s` |
| Traefik | Host `:80`/`:443` via ServiceLB; LE cert for `localpower.diegobarahona.com` |
| UFW | `80`/`443` allowed; CNI/flannel rules; API `6443` localhost+LAN only |
| Namespaces | `forge-system`, `forge-demo`, `forge-agents` + NetworkPolicies/quotas |
| cert-manager | `v1.21.1` + `letsencrypt-prod` ClusterIssuer |
| Vault | File storage PVC; Shamir 1/1; secrets under `/media/diestrin/data/secrets/vault/` |
| ESO | `v2.8.0`; `ClusterSecretStore/vault-backend`; ntfy ExternalSecret |
| Argo CD | `v3.5.0` in `forge-system`; root Application `forge-root` → `k8s/overlays/root` on `main` |
| Tooling | `kubectl` / `helm` / `vault` via Nix HM |
| L3 profile | `k8s-workload` applies project manifests into `forge-agents` |
| host-watch | `allow_ports` includes 80/443; k3s process substrings |

## Public exposure (redacted)

- Hostname: `localpower.diegobarahona.com` — HTTPS demo hello-app.
- SSH remains hardened; Vault/Argo UIs ClusterIP only (port-forward / SSH tunnel).

## Implications

1. After reboot: unseal Vault ([vault.md](./runbooks/vault.md)); Argo reconnects to git automatically.
2. Steady-state cluster changes: merge to `main` ([gitops.md](./runbooks/gitops.md)).
3. Next phase: Phase 4 agentic factory.
