# TASK-009 plan — forge-site landing redesign + PR preview infra

## What

Two deliverables on one task:

1. **Landing redesign** — refresh the public **forge-site** landing page (`apps/forge-site`,
   route `/`) using the **frontend-design** Cursor skill:
   - Images and icons for Forge components and the factory workflow
   - FAQ section for common Forge/factory questions
   - Interactive background effects on the hero/ambient layer

2. **PR preview bridge** — install a **GitHub Actions self-hosted runner inside the k3s
   cluster** so CI jobs that need cluster access can reach the k3s control plane without
   exposing the API publicly. Use it to stand up **ephemeral preview environments** for
   open PRs at:

   `https://pr-{PR_NUMBER}.localpower.diegobarahona.com`

   (e.g. PR #16 → `https://pr-16.localpower.diegobarahona.com`)

The task YAML targets `apps/forge-site` (operator said "forge-website"; same app from
TASK-007). The `/dashboard` control-plane UI is out of scope unless a shared header/layout
change is unavoidable.

## Why

The v1 landing (TASK-007) is functional but text-heavy and visually plain. A deliberate
design pass — guided by `.cursor/skills/frontend-design/SKILL.md` — gives visitors a
memorable, scannable story about Forge and reduces repeated questions the FAQ can answer
directly on the site.

Hosted GitHub runners cannot reach the homelab k3s API. An in-cluster runner is the
communication bridge for ephemeral preview deploys: workflow jobs labeled for the cluster
runner build the PR image, apply a short-lived preview Deployment/Ingress in-cluster, and
tear it down when the PR closes. Operators can review landing changes on a real HTTPS URL
before merge without overwriting steady-state `localpower.diegobarahona.com`.

## How

1. **Plan gate:** task stays `planning` until the operator approves in the Slack thread
   and `./forge factory approve TASK-009` moves status to `proposed`. Thread feedback
   refines this plan before approval.
2. **Fix CI on the implementation PR** ([#16](https://github.com/diestrin/homelab-forge/pull/16)):
   resolve markdown lint and any other failing checks; re-run all workflows until green.
3. **Design pass:** worker reads `frontend-design` skill, drafts a compact token system
   (palette, type, layout, signature element) grounded in Forge/homelab subject matter;
   self-critiques against generic AI-template defaults before coding.
4. **Implement landing in `apps/forge-site`:**
   - Redesign `src/app/page.tsx` (and supporting components/styles as needed)
   - Add in-repo icons/images/SVGs under `public/` or as React components
   - Add FAQ block with accessible expand/collapse and real copy (factory flow, Slack
     intake, Argo deploy path, what is/isn't automated)
   - Add interactive background (canvas/CSS) with `prefers-reduced-motion` fallback
5. **In-cluster GitHub runner (k3s):**
   - Add Argo-managed manifests under `k8s/` (suggested home: `forge-agents` namespace,
     alongside existing agent workload isolation and NetworkPolicies)
   - Deploy `actions-runner-controller` or a pinned single-runner Deployment pattern;
     runner registration token sourced from Vault via External Secrets (never in git)
   - Label runner(s) for preview jobs (e.g. `homelab-k3s`, `forge-preview`)
   - Runner ServiceAccount RBAC: scoped to create/update/delete preview resources in a
     dedicated namespace (e.g. `forge-previews`), not cluster-admin
6. **Ephemeral PR preview workflow:**
   - Extend `.github/workflows/forge-site-image.yml` (or add a sibling workflow) so PR
     jobs that need previews run on the in-cluster runner label
   - On `pull_request` (opened/synchronize): build forge-site image tagged with PR number,
     apply preview Deployment + Service + Ingress with host
     `pr-{number}.localpower.diegobarahona.com` and cert-manager HTTP-01 TLS
   - On `pull_request` (closed): delete preview resources and drop the PR-tagged image
   - Steady-state root host `localpower.diegobarahona.com` remains the Argo-managed
     forge-site Application; previews must not mutate it
7. **DNS/TLS prerequisites (operator):**
   - Ensure `*.localpower.diegobarahona.com` resolves to the homelab public IP (No-IP
     wildcard or equivalent); HTTP-01 per preview host requires each `pr-NNNN` name to
     resolve before cert issuance
8. **PR:** worker opens/updates the implementation PR on branch
   `factory/task-009-let-s-update-forge-website-to-use-the-fr`; complete
   [`factory/review/CHECKLIST.md`](../review/CHECKLIST.md).
9. **CI:** all GitHub Actions checks green — `ci.yml`, `forge-site-image.yml`, gitleaks.
10. **Deploy:** **human merge to `main` only.** CI builds and publishes the forge-site
    container image; **Argo CD** syncs Application `forge-site` and the runner manifests —
    this is the **sole steady-state deploy path** (ADR-008). Ephemeral previews are applied
    by the in-cluster runner workflow, not by worker `kubectl apply` to Argo-managed apps.

## Risks

- **Medium** — public-facing UI change visible after merge; rollback is git revert +
  Argo sync + image rebuild.
- **Medium** — self-hosted runner in-cluster is a trust boundary; scope RBAC narrowly,
  rotate registration credentials, and audit preview namespace NetworkPolicies.
- **Medium** — stale preview resources if cleanup workflow fails; add TTL or periodic
  janitor and document manual `kubectl delete` fallback.
- Wildcard DNS or per-PR DNS must be in place before HTTPS previews work; HTTP-01 rate
  limits apply when many PRs are open concurrently.
- Heavy animation or large assets can hurt mobile performance — keep effects lightweight
  and test at narrow viewports.
- New npm dependencies (icon libs, animation helpers) need license/size review; prefer
  minimal additions.
- Do **not** auto-approve into the worker queue without operator review of this plan.

## Out of scope

- `/dashboard` redesign, new API routes, auth, or control-plane behavior changes
- Changing steady-state forge-site Ingress/TLS on `localpower.diegobarahona.com`
- SSH, UFW, Vault unseal, disabling host-watch, force-push, or silent prod deploy
- Real Slack user IDs, tokens, GitHub runner registration tokens, or private ntfy topics
  in git
- Scripted `worker_hook` (Cursor SDK worker implements per task YAML)

## Slack iteration

The originating Slack thread may refine FAQ topics, aesthetic direction, preview workflow
details, or background effect intensity before approval. Scope changes require an updated
plan and explicit re-approval — not drive-by scope creep after `proposed`.

## Operator feedback (2026-08-14)

**CI checks are failing** on the draft implementation PR
([#16](https://github.com/diestrin/homelab-forge/pull/16)).

| Check | Result (2026-08-14 early runs) |
| --- | --- |
| markdown lint (`ci.yml`) | **FAIL** — `.cursor/skills/frontend-design/SKILL.md` MD047 (single trailing newline) |
| nix flake check, kustomize/kubeconform, factory schema, shellcheck, actionlint | pass |
| forge-site image (Next.js build, container build) | pass |
| gitleaks | pass |

A later push may have cleared markdown lint; **worker must confirm all checks green on
the PR head** before requesting review/merge. Run markdownlint locally on any new/edited
`*.md` (see `.markdownlint-cli2.yaml`).

**Ephemeral previews:** install a **GitHub Actions runner inside the k3s cluster** as the
bridge to the control plane when a PR needs a short-lived environment. Preview hostname
pattern: **`pr-{PR_NUMBER}.localpower.diegobarahona.com`** (e.g. `pr-16.localpower.diegobarahona.com`).

Task stays **`planning`** until the operator re-approves this updated plan.
