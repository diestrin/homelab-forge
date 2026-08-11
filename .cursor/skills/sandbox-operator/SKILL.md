---
name: sandbox-operator
description: Run projects in homelab-forge isolation sandboxes. Use when initializing, entering, or smoke-testing sandboxes, choosing between trusted, devcontainer, incus, k8s-workload, or agent-cell profiles, publishing a local port, or working with agent cells and the forge sandbox CLI.
---

# Sandbox operator

Read and follow `docs/runbooks/sandbox.md` — it is the source of truth
(init, profile selection, resource overrides, agent-cell layout, Incus). Profile
rationale is ADR-002.

## Commands

```bash
./forge sandbox init                                    # once per host
./forge sandbox enter <name-or-path> --profile <p>      # trusted|devcontainer|incus|k8s-workload|agent-cell
./forge sandbox smoke                                   # or: make sandbox-smoke
```

## Hard rules

1. Published ports bind `127.0.0.1` only (`FORGE_PUBLISH_PORT=…`), never `0.0.0.0`.
   Public HTTP(S) goes through k3s Ingress, not Docker publishes
   (`docs/runbooks/docker-hygiene.md`).
2. L1/L4 containers get project-only bind mounts: no Docker socket, no `$HOME`, no
   sibling project trees. Do not weaken this to unblock a task.
3. Secrets stay under `/media/diestrin/data/secrets/`, never under project trees or
   the forge state dirs.
4. After changing profiles or images, run `./forge sandbox smoke` to confirm the
   isolation checks still fail closed.
