# Review checklist (human default)

Gate before merge to `main`. Reviewer-agent may assist; **human merge** remains the
default for v1 (ADR-004).

PR: TASK-012 — forge-site landing redesign (ADR-011 factory story) — [#19](https://github.com/diestrin/homelab-forge/pull/19)

## Code / task

- [x] Acceptance criteria in the task YAML are met or explicitly waived in the PR.
- [x] Diff matches the task `goal` (no drive-by refactors).
- [x] `risk_level: medium` — public landing + shared layout/header fonts only; no
      Ingress, NetworkPolicy, Vault, or SSH changes.
- [x] No secrets, private ntfy topics, tokens, or real host inventory in the diff.
- [x] PR preview runner / ephemeral envs waived here — that work lives on TASK-010
      ([#18](https://github.com/diestrin/homelab-forge/pull/18)).
- [x] TASK-009 id is Family Agile on `main`; this PR does not overwrite that YAML.

## Deploy path

- [x] Cluster changes are manifests under `k8s/` only — **no** instructions to
      `kubectl apply` around Argo. This PR has no `k8s/` changes.
- [ ] After merge: watch `kubectl -n forge-system get application forge-site`
      → Synced/Healthy (new forge-site image from CI).
- [ ] Public demo: HTTPS root path shows redesigned landing with FAQ, icons, and
      background effect; copy matches ADR-011 (control plane as Slack↔agent hub).
- [ ] Verify `prefers-reduced-motion` shows static fallback (no animated sparks).
- [ ] Dashboard `/dashboard` and task/run pages still render (shared header/fonts).

## Audit

- [x] Git history on `main` is the durable audit log for code.
- [x] Argo Application status / sync history is the durable audit log for cluster converge.
- [x] Postgres task messages + `agent_runs` transcripts are runtime audit for
      factory coordination (ADR-010/ADR-011).

## Merge

```bash
gh pr review --approve
gh pr merge --squash
./forge factory set-status TASK-012 done   # via API after merge
```
