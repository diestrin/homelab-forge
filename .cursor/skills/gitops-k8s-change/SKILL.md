---
name: gitops-k8s-change
description: Make cluster changes in homelab-forge the GitOps way. Use when editing anything under k8s/ (manifests, kustomizations, Argo Applications, Ingress, NetworkPolicies, ExternalSecrets) or when asked to deploy, apply, or update something on the k3s cluster.
---

# GitOps k8s change

Read and follow `docs/runbooks/gitops.md` — it is the source of truth
(bootstrap vs Argo-managed split, root Application, UI access, DR).

## Hard rules

1. Steady-state deploys are **merge to `main` → Argo CD syncs** (ADR-008). Never
   `kubectl apply` Argo-managed apps by hand; only the one-time scripts under
   `k8s/bootstrap/` are applied directly.
2. Edit the kustomize trees under `k8s/` (platform bases, apps, `overlays/root`).
   New apps get an Application entry under `k8s/overlays/root/`.
3. Secrets via ExternalSecret + `ClusterSecretStore/vault-backend` (values in Vault,
   ADR-007) — never inline Secret values in manifests.
4. Validate locally the same way CI does before opening a PR:

   ```bash
   kubectl kustomize <dir-with-kustomization> \
     | kubeconform -strict -ignore-missing-schemas -summary
   ```

5. After merge, verify convergence instead of hand-applying:

   ```bash
   kubectl -n forge-system get application <app> -w   # expect Synced/Healthy
   ```
