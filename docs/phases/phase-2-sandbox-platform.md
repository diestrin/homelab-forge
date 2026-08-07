# Phase 2 — Sandbox platform

**Goal:** Operators and agents can open a project in an isolation profile with clear guarantees.

**Status:** Complete (2026-08-06) for trusted + devcontainer + agent-cell. Incus optional via install script; k8s-workload stubbed for Phase 3.

## Preconditions

- Phase 1 flake/direnv baseline working.

## Tasks

### 2.1 Profiles

- [x] Implement profiles from ADR-002: `trusted`, `devcontainer`, `incus` (or microVM), `k8s-workload`, `agent-cell`.
- [x] CLI or Make targets: `forge sandbox enter <project> --profile ...`.
- [x] Enforce resource limits and no Docker socket by default for `agent-cell`.

### 2.2 Filesystem layout

- [x] Standardize project roots on `/media/diestrin/data/Projects/`.
- [x] Put sandbox state/volumes under `/media/diestrin/data/forge/` (or similar), not on the small root FS.
- [x] Separate secrets dir with strict permissions (never in git).

### 2.3 Cursor remote-dev compatibility

- [x] Document how Cursor SSH attaches for L0 vs L1.
- [x] For L1/L2, provide “agent workspace” path that is still editable remotely.
- [x] Ensure linger/systemd user services don’t break inside sandboxes.

### 2.4 Guardrails

- [x] Default network policy for sandboxes: outbound allowlist optional later; inbound localhost-only.
- [x] host-watch allowlist updates when new runtimes appear.
- [x] Smoke tests: escape attempts (docker.sock, write outside mount) fail closed.

## Exit criteria

- [x] Can launch the same demo app in `trusted` and `devcontainer` profiles.
- [x] Agent-cell profile cannot see unrelated project directories.
- [x] Written threat model paragraph for portfolio/README.

## Agent notes

- Prefer Incus if microVMs are needed without heavy kube overhead; revisit Firecracker if density matters.
- Reuse/adapt `dev-machine/Dockerfile` rather than starting from scratch.

## Apply / verify

```bash
./forge sandbox init
./forge sandbox smoke
# Optional L2:
./sandbox/scripts/install-incus.sh   # sudo TTY
./bootstrap                          # PATH alias for forge via HM
```
