# Review checklist (human default)

Gate before merge to `main`. Reviewer-agent may assist; **human merge** remains the
default for v1 (ADR-004).

PR: TASK-012 — Prometheus + Grafana monitoring and alerting (ntfy + Slack)

## Code / task

- [x] Acceptance criteria in the task YAML are met or explicitly waived in the PR.
- [x] Diff matches the task `goal` (no drive-by refactors).
- [x] `risk_level: medium` changes reviewed (Ingress, NetworkPolicy, Vault ExternalSecrets, Helm stack).
- [x] No secrets, private ntfy topics, tokens, or real host inventory in the diff.
- [x] Worker artifacts attached (PR link, logs, `kubectl kustomize` output when manifests change).

## Deploy path

- [x] Steady-state cluster changes remain manifests under `k8s/` synced by Argo — **no**
      instructions to `kubectl apply` Argo-managed apps by hand.
- [x] Application `monitoring` uses multi-source Helm (`kube-prometheus-stack` chart + in-repo values).
- [x] Namespace `monitoring` and NetworkPolicies added; Grafana Ingress uses cert-manager TLS.
- [x] Operator bootstrap documented: Vault paths for ntfy, Slack webhook, Grafana admin.
- [x] After merge: watch `kubectl -n forge-system get application monitoring` → Synced/Healthy.

## Monitoring-specific

- [x] Shell CronJob `forge-node-alert` removed; `PrometheusRule` A1–A8 in git.
- [x] ExternalSecrets project `secret/forge/ntfy` and `secret/forge/alerts/slack` into `monitoring`.
- [x] Three dashboard layers documented (two chart defaults + Forge Overview).
- [x] `kubectl kustomize k8s/platform/metrics` and CI helm template step pass.
- [x] host-watch, UFW, and TASK-011 factory Slack routing unchanged.

## Audit

- [x] Git history on `main` is the durable audit log for code.
- [x] Argo Application status / sync history is the durable audit log for steady-state cluster converge.

## Merge

```bash
gh pr review --approve
gh pr merge --squash
# Operator: bootstrap Vault paths (see k8s/platform/metrics/README.md)
# Confirm: kubectl -n monitoring get externalsecret,pods,prometheusrule
./forge factory set-status TASK-012 done   # via API after merge
```

## Post-merge smoke (operator)

1. ExternalSecrets `SecretSynced` in `monitoring`.
2. Grafana HTTPS login with Vault admin password.
3. Throwaway CrashLoop pod in `forge-agents` fires A6 → ntfy + Slack (see metrics README).
4. Factory task Slack threads unchanged (TASK-011).
