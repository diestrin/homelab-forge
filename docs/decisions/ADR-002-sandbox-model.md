# ADR-002: Layered sandbox model

## Status

Accepted (2026-08-06) — layered model confirmed; Phase 2 runtimes locked below

## Context

Many projects will run on one host. Agents will execute untrusted or half-trusted
code. Cursor remote sessions need access to the workspace. Isolation must be
strong enough for confidence, light enough for a NUC.

## Decision

Use **layered isolation**, pick the layer per risk:

| Layer | Profile | Mechanism (Phase 2) | Use when |
| --- | --- | --- | --- |
| L0 Workspace | `trusted` | Project on data disk + Nix flake/`direnv` | Trusted personal code, shared tooling |
| L1 Devcontainer | `devcontainer` | Rootless Docker + `sandbox/images/Dockerfile` + project bind only | Language/runtime isolation, CI-like parity |
| L2 System container / microVM | `incus` | Incus (optional install); Firecracker deferred | Higher risk deps, different OS, noisy neighbors |
| L3 Cluster workload | `k8s-workload` | k3s Deployment + NetworkPolicy + ResourceQuota (Phase 3) | Long-running services, public ingress apps |
| L4 Agent task cell | `agent-cell` | Ephemeral L1 + no host Docker socket + project-only mount | Factory worker agents |

CLI: `./forge sandbox enter <project> --profile <name>` (see [`sandbox/README.md`](../../sandbox/README.md)).

Hard rules:

1. **No shared Docker socket** into agent cells by default.
2. **No bind-mount of `$HOME` or `/var/run/docker.sock`** into untrusted cells.
3. Default publish mode for local apps: `127.0.0.1` only; public exposure only via k3s Ingress.
4. Resource caps (CPU/mem/pids/disk) required at L1+.
5. Reuse ideas from `../dev-machine` (Nix + direnv inside a container) as the L1 baseline image.

## Consequences

- More profiles to maintain, but matches real risk levels.
- Cursor can attach to L0/L1 easily; L2 needs explicit “enter sandbox” DX.
- Portfolio story: defense-in-depth sandboxing, not “everything in Docker.”
