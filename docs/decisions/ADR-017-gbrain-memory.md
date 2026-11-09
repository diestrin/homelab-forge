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
engine requires. GBrain's default engine, PGLite, needs nothing external.

## Decision

1. Build our own image from `apps/gbrain/` (CI: `gbrain-image.yml`, GHCR).
2. Run one replica (Recreate) in namespace `gbrain` using **PGLite**, keyless
   (`--no-embedding`), data on the data disk at `/media/diestrin/data/forge/gbrain`.
3. Expose through Traefik at `gbrain.localpower.diegobarahona.com` with
   cert-manager TLS. Auth is GBrain's own OAuth/bearer tokens; owner credential
   `GBRAIN_ADMIN_BOOTSTRAP_TOKEN` comes from Vault `secret/forge/gbrain`.
4. Default-deny NetworkPolicies; egress limited to DNS and HTTPS (unused while keyless).

## Consequences

- PGLite is single-writer, so no scale-out and no concurrent CLI use on the same files.
- Moving to Postgres later needs a pgvector-capable instance
  (`gbrain migrate --to postgres`); a follow-up ADR if wanted.
- Semantic search/synthesis later needs API keys in Vault and an egress review.
- Public reachability is intentional; revisit with an IP allowlist if desired.
