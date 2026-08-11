---
name: public-repo-hygiene
description: Keep secrets and personal data out of this public repo. Use before committing changes that touch configuration, runbooks, ntfy topics, hostnames or IPs, tokens, credentials, Vault paths, or anything that could leak operator details.
---

# Public repo hygiene

This repo is public from day one; every commit is world-readable and CI runs a
**full-history** gitleaks scan (`.github/workflows/gitleaks.yml`) — a leaked value
cannot be quietly amended away and must be rotated.

## Rules

1. Placeholders and examples only in git. Real values live in Vault
   (`docs/runbooks/vault.md`) or under `/media/diestrin/data/secrets/` on the host —
   never in the tree, task YAML, logs, or committed artifacts.
2. Watch for the non-obvious leaks: private ntfy topics, home IPs and router details,
   real hostnames beyond the published `localpower.diegobarahona.com`, Vault unseal
   material, AppRole ids/secrets, GitHub App keys.
3. Cluster manifests reference secrets via ExternalSecret/ESO patterns, never inline
   values.
4. If something leaked: rotate the credential first, then clean up; note the rotation
   in the PR or task `notes:`.
