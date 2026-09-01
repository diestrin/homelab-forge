# TASK-010 plan — forge-site PR preview environments (local k8s)

## What

Ephemeral **preview deployments** for `apps/forge-site` in the operator's local k3s
cluster:

- **Automatic:** opening or updating a PR builds a branch/SHA image and deploys an
  isolated preview with its own URL.
- **Automatic cleanup:** deleting the PR branch removes that preview's k8s resources.
- **Manual:** GitHub Actions `workflow_dispatch` (or equivalent documented jobs) to
  create or delete a preview on demand for a given PR or branch ref.

Previews are **not** managed by Argo CD and must not touch the steady-state
`forge-site` Application.

## Why

Operators need to exercise forge-site changes in a real cluster before merge — the same
TLS, Ingress, and Postgres dependencies as production — without waiting for merge or
risking the Argo-synced demo on
[localpower.diegobarahona.com](https://localpower.diegobarahona.com).

## How

1. **Plan gate:** task stays `planning` until the operator approves in the Slack thread
   (`approve` / `lgtm` / `/forge approve`) and `./forge factory approve TASK-010`
   moves status to `proposed`.
2. **Preview model:** define a repeatable pattern — e.g. namespace
   `forge-preview-<pr-number>`, Deployment/Service/Ingress templated from PR metadata,
   image tag `ghcr.io/.../forge-site:pr-<n>-<sha>` (or similar). Keep manifests under
   a dedicated path (e.g. `k8s/preview/` or workflow-rendered templates) **outside**
   `k8s/apps/forge-site/` so Argo does not reconcile them.
3. **In-cluster GitHub Actions runner (communication bridge):**
   - Install a self-hosted GitHub Actions runner **inside the k3s cluster** (e.g.
     Deployment in `forge-agents` or a dedicated `forge-ci` namespace) so preview
     workflows run with in-cluster API access instead of pushing kubeconfig from a
     hosted runner.
   - The runner is the **communication bridge** between GitHub Actions job dispatch and
     the k3s control plane when an ephemeral preview environment is needed: jobs that
     build/push the preview image and `kubectl apply` / delete preview resources execute
     on the in-cluster runner using the pod's service account (RBAC-scoped to preview
     namespaces only).
   - Runner registration token lives in Vault / GitHub org secrets — human bootstrap
     only; document Vault path `secret/forge/ci/*` and secret names; never commit
     tokens or kubeconfig.
   - Manifests for the runner Deployment, ServiceAccount, Role/RoleBinding, and
     NetworkPolicy land in-repo under a non-Argo or bootstrap-owned path; document
     one-time operator steps to register the runner with the repo/org.
4. **GitHub Actions workflows** (targeting the in-cluster runner via `runs-on` label):
   - PR opened/synchronize → build + push preview image → `kubectl apply` preview
     stack → post URL in PR comment or job summary.
   - Branch deleted / PR closed (with branch removed) → delete preview namespace or
     labeled resources.
   - `workflow_dispatch` inputs for manual create/delete (PR number or branch ref).
5. **Ingress / DNS:** preview hostname pattern
   **`pr-<n>.localpower.diegobarahona.com`** (e.g. `pr-42.localpower.diegobarahona.com`
   for PR #42). Each preview Ingress requests a cert via existing cert-manager +
   Traefik (HTTP-01). Document operator DNS: wildcard `*.localpower.diegobarahona.com`
   → NUC (or per-PR records if wildcard is not used).
6. **PR:** worker opens/updates the implementation PR on branch
   `factory/task-010-i-want-to-have-deployment-previews-for-t`; complete
   [`factory/review/CHECKLIST.md`](../review/CHECKLIST.md).
7. **Steady-state deploy:** **human merge to `main` only.** Argo CD Application
   `forge-site` syncs the production demo — this remains the **sole steady-state deploy
   path** (ADR-008). Preview CI may `kubectl apply` only to non-Argo preview
   namespaces; workers must not apply to Argo-managed apps.

## Risks

- **High** — new Ingress surface (`pr-*.localpower.diegobarahona.com`), CI-driven
  cluster mutations from an in-cluster runner, and preview image publishing.
  Misconfiguration could collide with steady-state `forge-site` or leave orphaned
  resources.
- In-cluster runner adds a long-lived pod with cluster RBAC — scope permissions narrowly
  to preview namespaces; document rotation/re-registration of runner credentials.
- Requires GitHub Actions runner registration token and Vault CI credentials on the
  host — human setup, not auto-provisioned by the worker.
- Do **not** auto-approve this task into the worker queue without operator review;
  ephemeral cluster deploy from CI is human-gated.

## Out of scope

- Making previews the steady-state or Argo-managed deploy path
- Preview environments for apps other than forge-site (follow-on task if needed)
- SSH, UFW, Vault unseal, disabling host-watch, force-push, or `kubectl apply` to
  Argo-managed Applications
- Committing secrets, tokens, Slack user IDs, or private ntfy topics
- Scripted `worker_hook` (Cursor SDK worker implements per task YAML)

## Slack iteration

Operator feedback (2026-08-14): use an **in-cluster GitHub Actions runner** as the
bridge to the k3s control plane for ephemeral previews; hostname pattern
**`pr-<n>.localpower.diegobarahona.com`**. Further Slack thread iteration refines
trigger rules and manual workflow UX before approval. Plan updates land in this file
and the task YAML `notes:` field — not scope creep in implementation until the
operator re-approves expanded acceptance criteria.
