# Review checklist (human default)

Gate before merge to `main`. Reviewer-agent may assist; **human merge** remains the
default for v1 (ADR-004).

PR: [homelab-forge#10](https://github.com/diestrin/homelab-forge/pull/10) (TASK-007)

## Code / task

- [x] Acceptance criteria in the task YAML are met or explicitly waived in the PR.
- [x] Diff matches the task `goal` (no drive-by refactors).
- [x] `risk_level: high` changes get a second look (Ingress, NetworkPolicy, Vault, SSH).
- [x] No secrets, private ntfy topics, tokens, or real host inventory in the diff.
- [x] Worker artifacts attached (PR link, logs, `kubectl diff` when manifests change).

## Deploy path

- [x] Cluster changes are manifests under `k8s/` only — **no** instructions to
      `kubectl apply` around Argo.
- [ ] After merge: watch `kubectl -n forge-system get application forge-site`
      (or relevant app) → Synced/Healthy.
- [ ] Public demo: `curl -fsSI https://localpower.diegobarahona.com` still OK.

## Audit

- [x] Git history on `main` is the durable audit log for code.
- [x] Argo Application status / sync history is the durable audit log for cluster converge.
- [ ] Task YAML moved to `done` (or `failed`) and `./forge factory sync` refreshed the board.

## Merge

```bash
gh pr review 10 --approve   # or GitHub UI
gh pr merge 10 --squash
./forge factory set-status TASK-007 done
./forge factory sync
```
