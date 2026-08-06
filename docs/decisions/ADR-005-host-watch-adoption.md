# ADR-005: Import `host-watch` into homelab-forge

## Status

Accepted (2026-08-06) — **import** (not external-only dependency)

## Context

[`host-watch`](../../../host-watch) is a completed-but-uninstalled periodic scanner
for suspicious processes, listeners, and peers, with ntfy alerts and allowlists
tuned for Cursor/Docker/Nix workloads. Earlier `local-brain` docs asked for
monitoring that this tool largely implements more cleanly.

Keeping it as a sibling repo splits ownership of allowlists, install scripts, and
platform docs. The forge should own the IDS as a first-class component.

## Decision

1. **Import** the `host-watch` codebase into this repository under
   `security/host-watch/` (preserve Python package layout, systemd units, install scripts).
2. **Do not rewrite** the scanner logic during import — copy/port as-is, then evolve in-tree.
3. License: upstream is MIT; keep copyright/notice and ensure forge LICENSE remains compatible (MIT or Apache-2.0 with MIT component notice).
4. After import:
   - Install from **this** repo (`security/host-watch/scripts/install.sh` or a forge wrapper).
   - Example configs live in-repo; real ntfy URL stays outside git (bootstrap secrets → Vault).
   - Allowlists for forge platforms (k3s, Traefik, Vault, Argo CD) are maintained here.
5. Sibling `../host-watch` becomes **archived / deprecated** once import is verified (README pointer to new path). Do not maintain two active copies.
6. Extend in-tree only when gaps appear (systemd health, unexpected :80/:443 listeners, k3s anomalies).

## Consequences

- Single public OSS surface for platform + host IDS.
- Phase 0 should import (or at least vendor a copy) before or as part of first install.
- Follow-up agents must update in-tree allowlists as Definition of Done for any new public service.
