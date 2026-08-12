# Review checklist (human default)

Gate before merge to `main`. Reviewer-agent may assist; **human merge** remains the
default for v1 (ADR-004).

PR: TASK-008 — DB-backed factory control plane (ADR-010)

## Code / task

- [x] Acceptance criteria in the task YAML are met or explicitly waived in the PR.
- [x] Diff matches the task `goal` (no drive-by refactors).
- [x] `risk_level: high` changes get a second look (Ingress, NetworkPolicy, Vault, SSH, Postgres).
- [x] No secrets, private ntfy topics, tokens, or real host inventory in the diff.
- [x] Worker artifacts attached (PR link, logs, `kubectl diff` when manifests change).

## Deploy path

- [x] Cluster changes are manifests under `k8s/` only — **no** instructions to
      `kubectl apply` around Argo.
- [ ] After merge: watch `kubectl -n forge-system get application forge-site`
      and Postgres pods in `forge-system` → Synced/Healthy.
- [ ] Seed Vault paths `secret/forge/postgres` and `secret/forge/control-plane` before sync.
- [ ] Run `./forge factory migrate-yaml` once after API is reachable.
- [ ] Public demo: dashboard shows live tasks from Postgres.

## Audit

- [x] Git history on `main` is the durable audit log for code.
- [x] Argo Application status / sync history is the durable audit log for cluster converge.
- [x] Postgres + task messages are runtime audit for factory coordination (ADR-010).

## Merge

```bash
gh pr review --approve
gh pr merge --squash
# Operator: migrate YAML, restart orchestrator/worker with FORGE_CONTROL_PLANE_URL + FORGE_API_TOKEN
./forge factory set-status TASK-008 done   # via API after merge
```
