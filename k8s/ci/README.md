# In-cluster GitHub Actions runner (bootstrap)

Self-hosted runner for **forge-site PR preview** deploy/cleanup jobs. **Not**
managed by Argo CD — operator applies once after cluster bootstrap (ADR-008).

Preview CI `kubectl apply`s only to `forge-preview-*` namespaces; it must never
touch Argo-managed Applications (`forge-site`, `forge-root`, platform leaves).

## Layout

| File | Purpose |
| --- | --- |
| `namespace.yaml` | `forge-ci` namespace |
| `serviceaccount.yaml` | `forge-ci-runner` ServiceAccount |
| `rbac.yaml` | ClusterRole for preview namespace lifecycle + preview resources |
| `admission-policy.yaml` | ValidatingAdmissionPolicy: runner may only mutate `forge-preview-*` |
| `networkpolicies.yaml` | Default-deny + DNS/HTTPS egress (same pattern as `forge-agents`) |
| `entrypoint.sh` | Register runner, persist credentials, install kubectl/envsubst |
| `runner-deployment.yaml` | Long-lived runner pod |
| `runner-pvc.yaml` | Persist runner credentials at `/runner-state` (not `/home/runner`) |

## One-time operator setup

### 1. DNS

Preview hostnames use `pr-<n>.localpower.diegobarahona.com`. Prefer a wildcard
record `*.localpower.diegobarahona.com` → NUC public IP (same path as
[`docs/runbooks/network-exposure.md`](../../docs/runbooks/network-exposure.md)).

### 2. GitHub runner registration token

Create a **registration token** (short-lived) for repo `diestrin/homelab-forge`:

```bash
gh api -X POST repos/diestrin/homelab-forge/actions/runners/registration-token \
  --jq .token
```

Or from GitHub → Settings → Actions → Runners → New self-hosted runner.

Store in Vault (preferred) or apply directly as a Kubernetes Secret (never commit):

```bash
# Vault path documented for CI credentials (ADR-007)
vault kv put secret/forge/ci/github-runner registration_token='…'

# Bootstrap secret on cluster (replace TOKEN)
kubectl create namespace forge-ci --dry-run=client -o yaml | kubectl apply -f -
kubectl -n forge-ci create secret generic github-runner-registration \
  --from-literal=token='TOKEN' \
  --dry-run=client -o yaml | kubectl apply -f -
```

Optional: store a PAT for re-registration in `secret/forge/ci/github` (`pat` key)
— see [`docs/runbooks/forge-site-preview.md`](../../docs/runbooks/forge-site-preview.md).

### 3. Apply runner stack

```bash
kubectl apply -k k8s/ci/
kubectl -n forge-ci rollout status deployment/github-actions-runner
kubectl -n forge-ci logs -l app=github-actions-runner --tail=50
```

Confirm runner appears under GitHub → Actions → Runners with labels:
`self-hosted`, `k3s`, `forge-preview`.

### 4. Enable preview workflows

GitHub → Settings → Secrets and variables → Actions → Variables:

- Name: `FORGE_PREVIEW_ENABLED`
- Value: `true`

Until this is set, preview **build** still runs on hosted runners; **deploy** and
**cleanup** jobs skip so they do not wait 24h for a missing self-hosted runner.

### 5. Rotate / re-register

1. Remove stale runner in GitHub UI if needed.
2. Mint new registration token → update `github-runner-registration` secret.
3. Delete runner PVC if credentials are corrupt: `kubectl -n forge-ci delete pvc github-actions-runner-data`
4. Restart: `kubectl -n forge-ci rollout restart deployment/github-actions-runner`

## RBAC scope

`forge-ci-runner` may:

- Create/delete/get/list **namespaces** (API cannot prefix-restrict; admission policy does)
- Manage Deployments, Services, Ingresses, NetworkPolicies, ExternalSecrets,
  ResourceQuotas, and LimitRanges

ValidatingAdmissionPolicy `forge-ci-preview-scope` **denies** those mutations unless
the object is a `forge-preview-*` Namespace or lives in such a namespace.

It may **not** modify Argo CD Applications, Secrets in other namespaces, or
steady-state manifests under `k8s/apps/forge-site/`.
