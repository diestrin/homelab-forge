# Sandbox platform (Phase 2)

Layered isolation profiles from [ADR-002](../docs/decisions/ADR-002-sandbox-model.md).

## Quick start

```bash
./forge sandbox init
./forge sandbox list
./forge sandbox enter sandbox/examples/hello-flake --profile trusted
./forge sandbox enter sandbox/examples/hello-flake --profile devcontainer
./forge sandbox enter sandbox/examples/hello-flake --profile agent-cell
./forge sandbox smoke
```

Make wrappers: `make sandbox-enter PROJECT=sandbox/examples/hello-flake PROFILE=devcontainer`.

## Profiles

| Profile | Layer | Runtime | Guarantees |
| --- | --- | --- | --- |
| `trusted` | L0 | Host + flake/direnv | Full host access; operator trust |
| `devcontainer` | L1 | Rootless Docker | Project bind only; resource caps; no docker.sock; publish `127.0.0.1` only |
| `incus` | L2 | Incus | System container; project disk device only; optional install script |
| `k8s-workload` | L3 | k3s | Apply project `k8s/` into `forge-agents` (or `FORGE_K8S_NAMESPACE`); NetworkPolicy + quotas on namespace |
| `agent-cell` | L4 | Ephemeral L1 | Project-only mount; no `$HOME`; no docker.sock; cell metadata under data disk |

## Filesystem layout

| Path | Role |
| --- | --- |
| `/media/diestrin/data/Projects/` | Project roots (Cursor + forge) |
| `/media/diestrin/data/forge/` | Sandbox state, volumes, agent-cell metadata (mode `700`) |
| `/media/diestrin/data/secrets/` | Secrets only (mode `700`, never in git) |

## Image

[`images/Dockerfile`](./images/Dockerfile) — Ubuntu 24.04 + single-user Nix + direnv + flakes.
Adapted from [`../dev-machine`](../../dev-machine); does **not** ship Docker CLI or expect a socket.

## Docs

- [Sandbox runbook](../docs/runbooks/sandbox.md)
- [Cursor remote DX](../docs/runbooks/cursor-remote.md)
- Threat model paragraph in [README](../README.md)
