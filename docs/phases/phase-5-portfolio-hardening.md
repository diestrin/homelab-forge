# Phase 5 — Portfolio hardening & open-source polish

**Goal:** Keep the already-public repo presentable as a professional-grade solution others can learn from (and you can demo).

**Status: complete (2026-08-08).** Tagged `v0.1.0`.

## Context

Publishing is **day one** (already decided). This phase is polish, CI, and secret scrubbing discipline — not “go public.”

## Tasks

- [x] Public-safe README with architecture diagram (Mermaid), quickstart, and threat model.
- [x] Audit history/tree for accidental secrets (ntfy topics, tokens, home IPs); rotate anything that leaked.
      *gitleaks over all commits: clean. Only placeholder ntfy topics, no public IPs, no token patterns — nothing to rotate.*
- [x] Examples + placeholders only; real values in Vault.
- [x] CI: `nix flake check`, markdown lint, kubeconform/kustomize build, schema validation.
      *`.github/workflows/ci.yml` — plus shellcheck; flake check is eval-only (`--no-build`) to keep runners light.*
- [x] Tagged release of bootstrap scripts; changelog.
      *`CHANGELOG.md` (Keep a Changelog) + `v0.1.0` GitHub release.*
- [x] NixOS remains deferred (ADR-001); optional “future work” blurb only.
      *README “Future work”.*
- [x] Record short demo video or asciinema of factory flow.
      *`docs/demo/factory-demo.cast` — TASK-003 end to end (proposed → agent-cell → PR → review).*
- [x] LICENSE chosen (recommend Apache-2.0 or MIT; host-watch is already licensed — keep compatibility).
      *MIT at repo root; matches the imported host-watch MIT notice.*
- [x] Document No-IP + port-forward + LE + Vault unseal at operator runbook level (redact personal details in public docs).
      *`docs/runbooks/operations.md` cold-start runbook, cross-linking network-exposure/vault/gitops.*

## Exit criteria

- [x] Cold reader can explain the system from README alone.
- [x] Bootstrap works on a clean Ubuntu 24.04 VM (subset without WAN ingress).
      *Verified in a pristine `ubuntu:24.04` container (single-user Nix → clone → `./bootstrap` → HM switch OK); procedure in `docs/runbooks/bootstrap-clean-host.md`.*
- [x] Explicit “what this is not” section (not a multi-tenant cloud).
- [x] Secret scan clean (gitleaks or equivalent in CI).
      *Full-history scan clean locally; `.github/workflows/gitleaks.yml` enforces it on every push/PR.*
