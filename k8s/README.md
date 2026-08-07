# Kubernetes manifests (Phase 3)

Argo CD syncs [`overlays/root`](./overlays/root) from branch **`main`** (ADR-008).

| Path | Owner |
| --- | --- |
| [`bootstrap/`](./bootstrap/) | One-time host/cluster bootstrap (not Argo) |
| [`platform/`](./platform/) | Namespaces, policies, Vault, ESO, metrics |
| [`apps/`](./apps/) | Workloads + root Application |
| [`overlays/root/`](./overlays/root/) | App-of-apps kustomize entry |

See [`docs/runbooks/gitops.md`](../docs/runbooks/gitops.md) and [`docs/runbooks/vault.md`](../docs/runbooks/vault.md).
