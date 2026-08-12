# TASK-006 plan — forge-demo hello HTML copy

## What

Update the `hello-html` ConfigMap in `k8s/apps/forge-demo-hello/deployment.yaml` so the
public demo page greets visitors with copy from **Forge Software Factory** (operator
Slack request).

## Why

Refresh the portfolio demo surface to reflect the Forge Software Factory branding instead
of the Phase 5 release line currently shown on
[localpower.diegobarahona.com](https://localpower.diegobarahona.com).

## How

1. After `./forge factory approve TASK-006` moves status to `proposed`, a Cursor SDK
   worker claims TASK-006 on branch
   `factory/task-006-let-s-update-forge-demo-hello-html-to-sa`.
2. Edit `index.html` inside the `hello-html` ConfigMap — keep valid HTML; include the
   phrase `Forge Software Factory` in visible body copy.
3. Open/update the implementation PR; complete
   [`factory/review/CHECKLIST.md`](../review/CHECKLIST.md) before merge.
4. **Deploy:** human merge to `main` only. Argo CD Application `forge-demo-hello` syncs
   the change — this is the sole steady-state deploy path (ADR-008). No worker
   `kubectl apply` to Argo-managed apps.

## Risks

- **Low** — single ConfigMap string change; no Ingress, UFW, SSH, or Vault changes.
- Brief public copy change after merge; rollback is another git revert + Argo sync.

## Out of scope

- Ingress, TLS, image, or replica changes
- New dependencies or host/systemd changes
- Silent prod deploy or merge from Slack
- Scripted `worker_hook` (SDK worker implements per task YAML)

## Operator approval

Slack operator replied `approve` in the originating thread (2026-08-12). Plan content
is accepted. Task YAML stays `planning` on this PR until
`./forge factory approve TASK-006` transitions to `proposed` for worker claim.
