# Phase 2 — Sandbox platform

**Goal:** Operators and agents can open a project in an isolation profile with clear guarantees.

## Preconditions

- Phase 1 flake/direnv baseline working.

## Tasks

### 2.1 Profiles

- [ ] Implement profiles from ADR-002: `trusted`, `devcontainer`, `incus` (or microVM), `k8s-workload`, `agent-cell`.
- [ ] CLI or Make targets: `forge sandbox enter <project> --profile ...`.
- [ ] Enforce resource limits and no Docker socket by default for `agent-cell`.

### 2.2 Filesystem layout

- [ ] Standardize project roots on `/media/diestrin/data/Projects/`.
- [ ] Put sandbox state/volumes under `/media/diestrin/data/forge/` (or similar), not on the small root FS.
- [ ] Separate secrets dir with strict permissions (never in git).

### 2.3 Cursor remote-dev compatibility

- [ ] Document how Cursor SSH attaches for L0 vs L1.
- [ ] For L1/L2, provide “agent workspace” path that is still editable remotely.
- [ ] Ensure linger/systemd user services don’t break inside sandboxes.

### 2.4 Guardrails

- [ ] Default network policy for sandboxes: outbound allowlist optional later; inbound localhost-only.
- [ ] host-watch allowlist updates when new runtimes appear.
- [ ] Smoke tests: escape attempts (docker.sock, write outside mount) fail closed.

## Exit criteria

- [ ] Can launch the same demo app in `trusted` and `devcontainer` profiles.
- [ ] Agent-cell profile cannot see unrelated project directories.
- [ ] Written threat model paragraph for portfolio/README.

## Agent notes

- Prefer Incus if microVMs are needed without heavy kube overhead; revisit Firecracker if density matters.
- Reuse/adapt `dev-machine/Dockerfile` rather than starting from scratch.
