# Forge-site PR preview environments (TASK-010)

Ephemeral HTTPS previews for `apps/forge-site` in local k3s. **Outside Argo CD**
(ADR-008) — merge to `main` remains the only steady-state deploy path.

## Architecture

```text
GitHub PR event
  → hosted runner: build + push ghcr.io/.../forge-site:pr-<n>-<sha>
  → in-cluster runner (forge-ci): kubectl apply k8s/preview/forge-site templates
  → Traefik + cert-manager: https://pr-<n>.localpower.diegobarahona.com
```

Cleanup: PR closed, branch deleted, or manual workflow → delete `forge-preview-<n>` namespace.

## Operator one-time setup

### 1. Wildcard DNS

Add `*.localpower.diegobarahona.com` → NUC (same WAN path as production host). See
[`network-exposure.md`](./network-exposure.md).

### 2. Vault CI credentials (optional SoR)

Documented paths (never commit values):

| Vault path | Keys | Purpose |
| --- | --- | --- |
| `secret/forge/ci/github-runner` | `registration_token` | Runner bootstrap |
| `secret/forge/ci/github` | `pat` | Optional PAT for re-registration automation |

Vault policy `ci-deployer` (`k8s/platform/vault/policies/ci-deployer.hcl`) grants read on
`secret/forge/ci/*`.

### 3. GitHub Actions secrets

| Secret | Required | Notes |
| --- | --- | --- |
| *(none for cluster)* | — | In-cluster runner uses ServiceAccount RBAC, not kubeconfig in git |
| `GITHUB_TOKEN` | auto | Used to push preview images to ghcr.io |

Runner registration token is **not** a GitHub Actions secret — it is applied to the
cluster as `forge-ci/github-runner-registration` (see [`k8s/ci/README.md`](../../k8s/ci/README.md)).

### 4. Bootstrap in-cluster runner

```bash
# Mint registration token (short-lived)
gh api -X POST repos/diestrin/homelab-forge/actions/runners/registration-token --jq .token

kubectl apply -k k8s/ci/
kubectl -n forge-ci create secret generic github-runner-registration \
  --from-literal=token='TOKEN' --dry-run=client -o yaml | kubectl apply -f -
kubectl -n forge-ci rollout status deployment/github-actions-runner
```

Confirm runner labels: `self-hosted`, `k3s`, `forge-preview`.

Then set the repository Actions variable `FORGE_PREVIEW_ENABLED=true` so deploy
and cleanup jobs run on that runner. Until it is set, those jobs skip (build still
runs on `ubuntu-latest`).

## Workflows

| Workflow | Triggers |
| --- | --- |
| [`.github/workflows/forge-site-preview.yml`](../../.github/workflows/forge-site-preview.yml) | PR open/sync on `apps/forge-site/**`; PR close; branch delete |
| [`.github/workflows/forge-site-preview-manual.yml`](../../.github/workflows/forge-site-preview-manual.yml) | `workflow_dispatch` deploy/delete by PR number |

Preview paths that trigger automatic deploy (extend in workflow `paths:` if needed):

- `apps/forge-site/**`
- `k8s/preview/**`

## Manual preview

GitHub → Actions → **forge-site preview (manual)** → Run workflow:

- **deploy:** set `pr_number`, `ref` (branch or SHA)
- **delete:** set `pr_number`, action `delete`

## Verify

```bash
kubectl get ns -l forge.homelab/preview=true
kubectl -n forge-preview-<n> get deploy,ingress
curl -sS "https://pr-<n>.localpower.diegobarahona.com/api/v1/health"
```

After PR close + cleanup:

```bash
kubectl get ns forge-preview-<n>   # should be NotFound
```

Steady-state demo unchanged:

```bash
kubectl -n forge-system get application forge-site   # Synced / Healthy
curl -sS https://localpower.diegobarahona.com/api/v1/health
```

## Safety rules

- Preview CI must **only** `kubectl apply` / delete `forge-preview-*` namespaces.
- Do **not** apply to Argo-managed paths (`k8s/apps/forge-site/`, `forge-root`, platform).
- Runner RBAC plus ValidatingAdmissionPolicy `forge-ci-preview-scope` restrict
  mutations to `forge-preview-*` namespaces.
- Previews share the **production** Postgres database and API token (same Vault
  paths as `forge-site`). They can read/write factory data and run migrations —
  treat preview PRs as trusted; a dedicated preview database is follow-on work.

## Rotate runner credentials

See [`k8s/ci/README.md`](../../k8s/ci/README.md).
