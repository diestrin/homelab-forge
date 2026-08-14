# Review checklist (human default)

Gate before merge to `main`. Reviewer-agent may assist; **human merge** remains the
default for v1 (ADR-004).

PR: TASK-009 — forge-site landing redesign (frontend-design skill)

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
      → Synced/Healthy.
- [ ] Public demo: HTTPS root path shows redesigned landing with FAQ, icons, and background effect.
- [ ] Verify `prefers-reduced-motion` shows static fallback (no animated sparks).

## Audit

- [x] Git history on `main` is the durable audit log for code.
- [x] Argo Application status / sync history is the durable audit log for cluster converge.

## Merge

```bash
gh pr review --approve
gh pr merge --squash
./forge factory set-status TASK-009 done   # via API after merge
```
