# ADR-017: Self-hosted GBrain memory server

- Status: Proposed
- Date: 2026-11-09
- Related: ADR-003 (ingress), ADR-007 (Vault), ADR-008 (GitOps), ADR-015 (data disk)

## Context

The operator wants a personal [GBrain](https://github.com/garrytan/gbrain) (MIT)
so agents (Claude Code, Cursor worker, ChatGPT) share one explicit memory over MCP.
Upstream publishes no container image and is installed with
`bun install -g github:garrytan/gbrain#stable` (not npm). `gbrain serve --http`
provides MCP with OAuth 2.1 and an admin dashboard on port 3131.

`forge-postgres` is `postgres:16-alpine` without pgvector, which GBrain's Postgres
engine requires. Swapping its image to Debian would risk the other databases on it
(file ownership, text-sort order), so GBrain gets its own instance.

## Decision

1. Build our own image from `apps/gbrain/` (CI: `gbrain-image.yml`, GHCR).
2. Run one gbrain replica (Recreate) in namespace `gbrain`, keyless
   (`--no-embedding`), against a **dedicated `pgvector/pgvector:0.8.0-pg16`**
   Deployment (`gbrain-postgres`) with data on the data disk at
   `/media/diestrin/data/forge/gbrain-pg`. Only gbrain may reach it (NetworkPolicy).
3. Expose through Traefik at `gbrain.localpower.diegobarahona.com` with
   cert-manager TLS. Auth is GBrain's own OAuth/bearer tokens; owner credential
   `GBRAIN_ADMIN_BOOTSTRAP_TOKEN` comes from Vault `secret/forge/gbrain`.
4. Default-deny NetworkPolicies; egress limited to DNS and HTTPS (unused while keyless).

## Consequences

- A second Postgres to back up and patch; it is not covered by forge-postgres backups.
- Embeddings can be enabled later without a migration.
- Semantic search/synthesis later needs API keys in Vault and an egress review.
- Public reachability is intentional; revisit with an IP allowlist if desired.
