# Review checklist (human default)

Gate before merge to `main`. Reviewer-agent may assist; **human merge** remains the
default for v1 (ADR-004).

PR: TASK-010 — forge-site PR preview environments (local k8s)

## Code / task

- [ ] Acceptance criteria in the task YAML are met or explicitly waived in the PR.
- [ ] Diff matches the task `goal` (no drive-by refactors).
- [ ] `risk_level: high` changes get a second look (Ingress, NetworkPolicy, Vault, SSH, Postgres, in-cluster runner RBAC).
- [ ] No secrets, private ntfy topics, tokens, or real host inventory in the diff.
- [ ] Worker artifacts attached (PR link, logs, `kubectl diff` when manifests change).

## Deploy path

- [ ] Steady-state cluster changes remain manifests under `k8s/` synced by Argo — **no**
      instructions to `kubectl apply` Argo-managed apps by hand.
- [ ] Preview stack (`k8s/preview/`, `k8s/ci/`) is bootstrap/CI-owned, not registered as Argo Applications.
- [ ] Postgres NetworkPolicy allows `forge.homelab/preview: "true"` namespaces.
- [ ] Operator bootstrap documented: in-cluster runner (`k8s/ci/`), registration token secret, wildcard DNS.
- [ ] After merge: watch `kubectl -n forge-system get application forge-site` → Synced/Healthy (unchanged steady-state).

## Preview-specific

- [ ] In-cluster runner registered with labels `self-hosted`, `k3s`, `forge-preview`.
- [ ] Test PR on `apps/forge-site/**` posts preview URL comment and serves HTTPS at `pr-<n>.localpower.diegobarahona.com`.
- [ ] PR close / branch delete removes `forge-preview-<n>` namespace.
- [ ] Manual workflow deploy + delete verified once.

## Audit

- [ ] Git history on `main` is the durable audit log for code.
- [ ] Argo Application status / sync history is the durable audit log for steady-state cluster converge.
- [ ] Preview namespaces labeled `forge.homelab/preview: "true"` for inventory.

## Merge

```bash
gh pr review --approve
gh pr merge --squash
# Operator: bootstrap k8s/ci runner + registration secret; wildcard DNS if not present
./forge factory set-status TASK-010 done   # via API after merge
```
