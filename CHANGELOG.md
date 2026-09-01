# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow
[Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- Cluster log aggregation: Grafana Loki (7-day filesystem retention) and a Grafana Alloy
  DaemonSet, queried from Grafana Explore. Loki stays ClusterIP-only.

### Changed

- Alertmanager Slack `#forge-alerts` now posts when alerts resolve (ntfy already did).

## [0.1.0] - 2026-08-07

First tagged release: Phases 0–5 of [`PLAN.md`](./PLAN.md) complete on host
`localpower` (Ubuntu 24.04, Intel NUC).

### Added

- **Phase 0 — secure baseline:** hardened public SSH (keys only, fail2ban, UFW
  default-deny), in-tree `security/host-watch/` IDS with ntfy alerts, WAN
  inventory runbooks, host backups of sshd/UFW config.
- **Phase 1 — Nix foundation:** `nix/` flake with Home Manager
  (`diestrin@localpower`) and system-manager (sysctl/journald); idempotent
  `./bootstrap`.
- **Phase 2 — sandbox platform:** `./forge sandbox` CLI with layered isolation
  profiles (ADR-002): trusted L0, devcontainer L1, Incus L2, k8s-workload L3,
  agent-cell L4; rootless Docker, project-only mounts, smoke tests.
- **Phase 3 — k3s platform:** k3s + Traefik on 80/443 with Let's Encrypt
  (HTTP-01), Vault (ADR-007) + External Secrets Operator, Argo CD GitOps from
  `main` (ADR-008), namespaces/quotas/NetworkPolicies, node alert CronJob,
  public demo app at `localpower.diegobarahona.com`.
- **Phase 4 — agentic factory:** git task schema + YAML queue
  (`factory/tasks/`), GitHub Projects mirror (`forge factory sync`),
  orchestrator/worker playbooks, worker daemon in isolated worktree +
  agent-cell with budget watchdog, Vault AppRole + GitHub App token minting,
  human review gate before merge (ADR-004).
- **Phase 5 — portfolio hardening:** MIT `LICENSE`, CI on GitHub Actions
  (nix flake check, markdownlint, kustomize + kubeconform, factory schema
  validation, shellcheck) and full-history gitleaks scan, README with Mermaid
  architecture + threat model + "what this is not", operator cold-start
  runbook, clean Ubuntu 24.04 bootstrap test, asciinema demo of the factory
  flow, this changelog.

[Unreleased]: https://github.com/diestrin/homelab-forge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/diestrin/homelab-forge/releases/tag/v0.1.0
