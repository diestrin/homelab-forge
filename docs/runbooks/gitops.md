# GitOps with Argo CD (Phase 3)

Argo CD syncs cluster desired state from branch **`main`** (ADR-008).

## Bootstrap vs steady-state

| One-time (bootstrap) | Argo-managed |
| --- | --- |
| `k8s/bootstrap/install-k3s.sh` | `k8s/overlays/root` via Application `forge-root` |
| `k8s/bootstrap/ufw-k3s.sh` | `k8s/apps/forge-demo-hello` |
| `k8s/bootstrap/apply-cert-manager.sh` (+ ClusterIssuers) | Vault manifests, ESO store, metrics CronJob |
| `k8s/bootstrap/apply-argocd.sh` | Child Applications under `k8s/overlays/root/applications.yaml` |
| `k8s/bootstrap/init-vault.sh` | — |

Steady-state: **merge to `main` → Argo syncs**. Do not `kubectl apply` managed apps by hand.

## Merge gates on `main`

The repository ruleset `main` requires a PR with one approval **and** green status
checks before merge: all `ci.yml` jobs (flake check, markdown lint,
kustomize+kubeconform, factory task schema, shellcheck, actionlint) plus the
full-history gitleaks scan. Workers cannot merge around these gates; repo admins
retain bypass for emergencies. GitHub Actions never deploys to the cluster —
Argo CD is the only deploy path (ADR-008).

## Root Application

```bash
kubectl apply -f k8s/apps/root-app.yaml
```

- Repo: `https://github.com/diestrin/homelab-forge.git` (public — no deploy key for this repo).
- Path: `k8s/overlays/root`
- Automated sync + self-heal enabled for demo/platform leaves.

## UI access

Not anonymously public. From the NUC:

```bash
kubectl -n forge-system port-forward svc/argocd-server 8080:443
# Initial password:
kubectl -n forge-system get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d; echo
```

Browser: `https://localhost:8080` (accept self-signed). Change admin password after first login.

## Prove end-to-end

1. Change a label or ConfigMap string under `k8s/apps/forge-demo-hello/`.
2. Merge to `main`.
3. Watch: `kubectl -n forge-system get application forge-demo-hello -w`
4. Confirm pod/config updates without manual apply.

## Disaster recovery

1. Reinstall k3s (`k8s/bootstrap/README.md`).
2. Re-apply cert-manager + issuers, init/unseal Vault from offline backup.
3. Re-apply Argo CD + `k8s/apps/root-app.yaml`.
4. Argo reconciles the rest from `main`.
