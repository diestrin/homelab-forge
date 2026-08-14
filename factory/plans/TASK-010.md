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
3. **GitHub Actions:**
   - PR opened/synchronize → build + push preview image → `kubectl apply` preview
     stack → post URL in PR comment or job summary.
   - Branch deleted / PR closed (with branch removed) → delete preview namespace or
     labeled resources.
   - `workflow_dispatch` inputs for manual create/delete (PR number or branch ref).
   - Cluster access via repo/org secrets (kubeconfig or token); document Vault path
     `secret/forge/ci/*` for human bootstrap — never commit credentials.
4. **Ingress / DNS:** pick a preview hostname pattern (e.g.
   `pr-<n>.preview.localpower.diegobarahona.com` or wildcard under a documented
   subdomain) compatible with existing cert-manager + Traefik; document operator DNS
   steps if needed.
5. **PR:** worker opens/updates the implementation PR on branch
   `factory/task-010-i-want-to-have-deployment-previews-for-t`; complete
   [`factory/review/CHECKLIST.md`](../review/CHECKLIST.md).
6. **Steady-state deploy:** **human merge to `main` only.** Argo CD Application
   `forge-site` syncs the production demo — this remains the **sole steady-state deploy
   path** (ADR-008). Preview CI may `kubectl apply` only to non-Argo preview
   namespaces; workers must not apply to Argo-managed apps.

## Risks

- **High** — new Ingress surface, CI-driven cluster mutations, and preview image
  publishing. Misconfiguration could collide with steady-state `forge-site` or leave
  orphaned resources.
- Requires GitHub Actions secrets / Vault CI credentials on the host — human setup,
  not auto-provisioned by the worker.
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

The originating Slack thread refines hostname pattern, trigger rules, and manual
workflow UX before approval. Plan updates land in this file and the task YAML `notes:`
field — not scope creep in implementation until the operator re-approves expanded
acceptance criteria.
