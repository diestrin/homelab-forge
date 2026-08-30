# Review checklist (human default)

Gate before merge to `main`. Reviewer-agent may assist; **human merge** remains the
default for v1 (ADR-004).

PR: TASK-011 — Factory control-plane hub, CI watch, and agent observability (ADR-011)

## Code / task

- [x] Acceptance criteria in the task YAML are met or explicitly waived in the PR.
- [x] Diff matches the task `goal` (no drive-by refactors).
- [x] `risk_level: high` changes get a second look (Ingress, NetworkPolicy, Vault, SSH, Postgres).
- [x] No secrets, private ntfy topics, tokens, or real host inventory in the diff.
- [x] Worker artifacts attached (PR link, logs, `kubectl diff` when manifests change).

## Deploy path

- [x] Cluster changes are manifests under `k8s/` only — **no** instructions to
      `kubectl apply` around Argo.
- [ ] Before sync: add `bot_token` consumer path — Vault `secret/forge/agents/slack`
      already holds it (step 5 of the runbook); ExternalSecret picks it up.
- [ ] After merge: watch `kubectl -n forge-system get application forge-site` →
      Synced/Healthy; `agent_runs` table created by startup migrations.
- [ ] Operator: restart `forge-factory-orchestrator` + `forge-factory-worker`
      user units (thin intake + multi-kind concurrent daemon), ensure
      `markdownlint-cli2` is installed on the host for the lint gate.
- [ ] Smoke: `/forge plan …` → plan PR once → approve → implement on same PR →
      watch-checks green notify; task page shows runs + transcripts.

## Audit

- [x] Git history on `main` is the durable audit log for code.
- [x] Argo Application status / sync history is the durable audit log for cluster converge.
- [x] Postgres task messages + `agent_runs` transcripts are runtime audit for
      factory coordination (ADR-010/ADR-011).

## Merge

```bash
gh pr review --approve
gh pr merge --squash
./forge factory set-status TASK-011 done   # via API after merge
```
