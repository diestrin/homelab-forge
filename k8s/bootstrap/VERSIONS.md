# Pinned versions (Phase 3)

Recorded at install time. Bump deliberately; do not float on `latest` in scripts.

| Component | Version | Notes |
| --- | --- | --- |
| k3s | `v1.36.3+k3s1` | Stable channel 2026-08; Traefik + local-path + metrics-server embedded |
| cert-manager | `v1.21.1` | HTTP-01 ClusterIssuer |
| External Secrets Operator | `v2.8.0` | Vault backend |
| Vault (image) | `1.19.0` | File storage on PVC; manual Shamir unseal |
| Argo CD | `v3.5.0` | App-of-apps on `main` |
| GitHub Actions runner (in-cluster) | `2.322.0` | `k8s/ci/runner-deployment.yaml` — bootstrap only |

Install flags for k3s live in [`install-k3s.sh`](./install-k3s.sh).
