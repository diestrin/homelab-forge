# TASK-012 plan — forge-site landing redesign (ADR-011)

## What

Refresh the public **forge-site** landing page (`apps/forge-site`, route `/`) using
the **frontend-design** Cursor skill, and describe the factory as it actually works
after [ADR-011](../../docs/decisions/ADR-011-control-plane-hub.md):

- forge-site is the Slack↔agent communication hub
- Slack Socket Mode is a thin intake client (`POST /api/v1/slack/intake`)
- One pinned branch and one PR per task
- Agent runs are inspectable on the dashboard
- Lint before push; CI watch after; humans still merge

Work continues on the **already-open** PR
[#19](https://github.com/diestrin/homelab-forge/pull/19) (`factory/task-009`).
That is the ADR-011 rule that this task exists to demonstrate.

PR preview environments stay on TASK-010 /
[#18](https://github.com/diestrin/homelab-forge/pull/18).

## Why

The v1 landing (TASK-007) is text-heavy, and its factory story still describes a
host orchestrator that drafts PRs. After TASK-011 that story is wrong: the
control plane owns intake, jobs, notify, and transcripts.

PR #19 already has the design pass (icons, FAQ, ember background). Merging `main`
into that branch and correcting the copy is cheaper and safer than opening a
third landing PR — the failure mode ADR-011 was written to stop.

## How

1. Merge `main` into `factory/task-009` (no force-push, no branch rename).
2. Drop the stale TASK-009 landing YAML so it cannot collide with Family Agile.
3. Keep the landing visual system; rewrite pipeline + FAQ for ADR-011.
4. Shared `layout.tsx` / `site-header.tsx` fonts apply to `/dashboard`; do not
   redesign dashboard pages.
5. Lint locally; push the pinned branch; human merge only.

## Out of scope

- `/dashboard` redesign, new API routes, auth, or control-plane behavior
- In-cluster GitHub runner / `pr-{N}` preview hosts (TASK-010)
- Overwriting TASK-009 Family Agile files
- SSH, UFW, Vault unseal, or `kubectl apply` around Argo
