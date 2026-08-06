# ADR-004: Agentic software factory shape

## Status

Accepted (2026-08-06)

## Context

Owner wants development to happen via agents: chat with an orchestrator that
creates tasks worker agents pick up. Must be credible as a portfolio system,
runnable on this host, and safe given sandbox constraints. Repo is public from
day one.

## Decision

Define a minimal **factory control plane** with clear contracts before picking a
fancy UI:

1. **Orchestrator** (human chat interface — Cursor agent / future custom UI):
   - Clarifies intent, writes structured Tasks, does not mutate production by default.
2. **Task store:**
   - **Source of truth:** Git-backed YAML/Markdown under `factory/tasks/` (auditable, OSS-friendly).
   - **Board UX:** **GitHub Projects** mirrored/synced for kanban (status columns map to task state machine).
   - Schema fields: `id`, `title`, `goal`, `acceptance_criteria`, `sandbox_profile`, `repo_path`, `status`, `assignee_agent`, `artifacts[]`, `risk_level`, optional `github_project_item_id`.
3. **Worker agents:**
   - Claim one task → provision sandbox (ADR-002) → implement → open PR / write artifacts → mark ready-for-review.
   - Secrets (GH tokens, etc.) from Vault (ADR-007), never from committed files.
4. **Reviewer gate** (human or specialized agent):
   - Required before merge or deploy to k3s production-like namespaces.
5. **Deployer:**
   - After merge to `main`, **Argo CD** (ADR-008) syncs approved manifests — workers/humans do not bypass GitOps for steady-state cluster changes.

Out of scope for v1: multi-tenant SaaS, billing, fully autonomous production deploys without review, ClickUp as primary board.

## Consequences

- Works with Cursor today; GitHub Projects gives a shareable board for the public repo.
- Sync logic (git ↔ Projects) must be documented; if sync fails, **git wins**.
- Safety depends on sandbox profiles + PR review gate + Argo CD drift visibility.
- Factory Definition of Done for cluster work: PR merged to `main` and Argo healthy sync.
