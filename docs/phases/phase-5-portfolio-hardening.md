# Phase 5 — Portfolio hardening & open-source polish

**Goal:** Keep the already-public repo presentable as a professional-grade solution others can learn from (and you can demo).

## Context

Publishing is **day one** (already decided). This phase is polish, CI, and secret scrubbing discipline — not “go public.”

## Tasks

- [ ] Public-safe README with architecture diagram (Mermaid), quickstart, and threat model.
- [ ] Audit history/tree for accidental secrets (ntfy topics, tokens, home IPs); rotate anything that leaked.
- [ ] Examples + placeholders only; real values in Vault.
- [ ] CI: `nix flake check`, markdown lint, kubeconform/kustomize build, schema validation.
- [ ] Tagged release of bootstrap scripts; changelog.
- [ ] NixOS remains deferred (ADR-001); optional “future work” blurb only.
- [ ] Record short demo video or asciinema of factory flow.
- [ ] LICENSE chosen (recommend Apache-2.0 or MIT; host-watch is already licensed — keep compatibility).
- [ ] Document No-IP + port-forward + LE + Vault unseal at operator runbook level (redact personal details in public docs).

## Exit criteria

- [ ] Cold reader can explain the system from README alone.
- [ ] Bootstrap works on a clean Ubuntu 24.04 VM (subset without WAN ingress).
- [ ] Explicit “what this is not” section (not a multi-tenant cloud).
- [ ] Secret scan clean (gitleaks or equivalent in CI).
