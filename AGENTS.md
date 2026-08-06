# Agent handoff

You are working in **homelab-forge**, a planning-first repo for a home software forge.

## Before any host change

1. Read [`PLAN.md`](./PLAN.md).
2. Read [`docs/current-state.md`](./docs/current-state.md) and re-verify live facts that matter to your task.
3. Open the single phase the human authorized under [`docs/phases/`](./docs/phases/).
4. Respect ADRs in [`docs/decisions/`](./docs/decisions/).

## Defaults

- No implementation unless the human asks to execute a phase.
- Phase 0 before ingress/k3s.
- Adopt [`../host-watch`](../host-watch); do not rewrite it.
- Prefer reversible, documented changes; never disable the firewall to unblock networking.
- Repo is **public** — no secrets in git; Vault is SoR after Phase 3 (ADR-007).
- Import `host-watch` into `security/host-watch/` (ADR-005); do not dual-maintain the sibling.
- Cluster steady-state deploys go through Argo CD from `main` (ADR-008).
- Locked product decisions live in [`PLAN.md`](./PLAN.md) (Accepted answers) and ADRs 001–008.
