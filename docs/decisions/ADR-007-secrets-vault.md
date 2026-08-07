# ADR-007: Secrets with HashiCorp Vault

## Status

Accepted (2026-08-06) — adopt Vault; size the deployment for a single-node home lab

## Context

The forge will hold secrets: Let’s Encrypt account material (or cert-manager
credentials), ntfy topics, agent/API tokens, kubeconfig fragments, app DB
passwords, No-IP if API-driven, GitHub tokens for factory workers, etc.
The repo is **public from day one**, so secrets must never live in git.

## Decision

1. Adopt **HashiCorp Vault** as the secrets system of record for forge platform secrets.
2. **Deploy Vault on k3s** (namespace `forge-system`) once Phase 3 cluster exists:
   - Single-node / integrated storage suitable for homelab (document HA as non-goal for v1).
   - Unseal strategy documented (manual shamir for v1 is acceptable; auto-unseal optional later).
   - Persist Vault data on the data disk volume.
3. **Bootstrap chicken-egg:** before Vault exists, use a minimal sealed local path
   (e.g. age-encrypted file outside the repo, or `pass`/SOPS) only for bootstrap
   secrets needed to stand up Vault + Traefik. Migrate into Vault and delete the bootstrap store.
4. **Consumers:**
   - k8s workloads: **Phase 3 pick: External Secrets Operator** (`ClusterSecretStore` → Vault KV). Vault Agent deferred for short-lived agent tokens in Phase 4.
   - Agents/sandboxes: short-lived Vault tokens or AppRole per task; no long-lived PATs in env files.
   - Humans: Vault CLI/UI over SSH tunnel or authenticated Ingress (UI not anonymously public).
5. **Never** commit Vault unseal keys, root token, or `.vault-token` to git.
6. Public docs describe the pattern with example policies; real host paths/policies stay out of the default tree or use placeholders.

## Consequences

- Phase 3 gains a Vault install + policy skeleton; Phase 4 workers depend on AppRole/token issuance.
- Operational burden: unseal after reboot unless auto-unseal is added later.
- Strong portfolio signal: proper secret lifecycle on a home lab, not `.env` in the repo.
- Alternatives considered and deferred: cloud secret managers (extra vendor), git-crypt alone (no dynamic credentials).
