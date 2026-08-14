# TASK-009 plan — forge-site landing redesign (frontend-design skill)

## What

Refresh the public **forge-site** landing page (`apps/forge-site`, route `/`) using
the **frontend-design** Cursor skill. Operator asks for:

- **Images and icons** to explain Forge components and the factory workflow more clearly
- A **FAQ** section for common questions about Forge and the factory pipeline
- **Interactive background effects** on the landing hero/ambient layer

The task YAML targets `apps/forge-site` (operator said "forge-website"; same app from
TASK-007). The `/dashboard` control-plane UI is out of scope unless a shared header/layout
change is unavoidable.

## Why

The v1 landing (TASK-007) is functional but text-heavy and visually plain. A deliberate
design pass — guided by `.cursor/skills/frontend-design/SKILL.md` — gives visitors a
memorable, scannable story about Forge and reduces repeated questions the FAQ can answer
directly on the site.

## How

1. **Plan gate:** task stays `planning` until the operator approves in the Slack thread
   and `./forge factory approve TASK-009` moves status to `proposed`. Thread feedback
   refines this plan before approval.
2. **Design pass:** worker reads `frontend-design` skill, drafts a compact token system
   (palette, type, layout, signature element) grounded in Forge/homelab subject matter;
   self-critiques against generic AI-template defaults before coding.
3. **Implement in `apps/forge-site`:**
   - Redesign `src/app/page.tsx` (and supporting components/styles as needed)
   - Add in-repo icons/images/SVGs under `public/` or as React components
   - Add FAQ block with accessible expand/collapse and real copy (factory flow, Slack
     intake, Argo deploy path, what is/isn't automated)
   - Add interactive background (canvas/CSS) with `prefers-reduced-motion` fallback
4. **PR:** worker opens/updates the implementation PR on branch
   `factory/task-009-let-s-update-forge-website-to-use-the-fr`; complete
   [`factory/review/CHECKLIST.md`](../review/CHECKLIST.md).
5. **CI:** all GitHub Actions checks green — `ci.yml`, `forge-site-image.yml`, gitleaks.
6. **Deploy:** **human merge to `main` only.** CI builds and publishes the forge-site
   container image; **Argo CD** syncs Application `forge-site` — this is the **sole
   steady-state deploy path** (ADR-008). No worker `kubectl apply` to Argo-managed apps.

## Risks

- **Medium** — public-facing UI change visible after merge; rollback is git revert +
  Argo sync + image rebuild.
- Heavy animation or large assets can hurt mobile performance — keep effects lightweight
  and test at narrow viewports.
- New npm dependencies (icon libs, animation helpers) need license/size review; prefer
  minimal additions.
- Do **not** auto-approve into the worker queue without operator review of this plan.

## Out of scope

- `/dashboard` redesign, new API routes, auth, or control-plane behavior changes
- K8s Ingress, TLS, replica, or ExternalSecret manifest changes
- SSH, UFW, Vault unseal, disabling host-watch, force-push, or silent prod deploy
- Real Slack user IDs, tokens, or private ntfy topics in git
- Scripted `worker_hook` (Cursor SDK worker implements per task YAML)

## Slack iteration

The originating Slack thread may refine FAQ topics, aesthetic direction, or background
effect intensity before approval. Scope changes require an updated plan and explicit
re-approval — not drive-by scope creep after `proposed`.
