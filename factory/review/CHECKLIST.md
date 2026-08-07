# Review checklist (human default)

Gate before merge to `main`. Reviewer-agent may assist; **human merge** remains the
default for v1 (ADR-004).

## Code / task

- [ ] Acceptance criteria in the task YAML are met or explicitly waived in the PR.
- [ ] Diff matches the task `goal` (no drive-by refactors).
- [ ] `risk_level: high` changes get a second look (Ingress, NetworkPolicy, Vault, SSH).
- [ ] No secrets, private ntfy topics, tokens, or real host inventory in the diff.
- [ ] Worker artifacts attached (PR link, logs, `kubectl diff` when manifests change).

## Deploy path

- [ ] Cluster changes are manifests under `k8s/` only — **no** instructions to
      `kubectl apply` around Argo.
- [ ] After merge: watch `kubectl -n forge-system get application forge-demo-hello`
      (or relevant app) → Synced/Healthy.
- [ ] Public demo: `curl -fsSI https://localpower.diegobarahona.com` still OK.

## Audit

- [ ] Git history on `main` is the durable audit log for code.
- [ ] Argo Application status / sync history is the durable audit log for cluster converge.
- [ ] Task YAML moved to `done` (or `failed`) and `./forge factory sync` refreshed the board.

## Merge

```bash
gh pr review <n> --approve   # or GitHub UI
gh pr merge <n> --squash
./forge factory set-status TASK-NNN done
./forge factory sync
```
