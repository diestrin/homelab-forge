# Sandbox runbook

Operator guide for Phase 2 isolation profiles ([ADR-002](../decisions/ADR-002-sandbox-model.md)).

## Init (once per host)

```bash
./forge sandbox init
# creates /media/diestrin/data/forge/{state,volumes,agent-cells,images,workspaces}
```

Secrets stay under `/media/diestrin/data/secrets/` (see [bootstrap-secrets.md](./bootstrap-secrets.md)) — never under `forge/` git or project trees.

## Enter a project

```bash
./forge sandbox enter <name-or-path> --profile trusted
./forge sandbox enter hello-flake --profile devcontainer   # under Projects/ or repo-relative
./forge sandbox enter sandbox/examples/hello-flake --profile agent-cell -- hello
```

Resource overrides: `FORGE_MEM=1g FORGE_CPUS=1 FORGE_PIDS=512`.

Local publish (inbound localhost only):

```bash
FORGE_PUBLISH_PORT=8080 ./forge sandbox enter myapp --profile devcontainer
# binds 127.0.0.1:8080 -> container :8080
```

## Network policy (v1)

- Default: **no** published ports.
- If publishing: **always** `127.0.0.1` (never `0.0.0.0`).
- Outbound allowlists: deferred; rely on host UFW + k3s NetworkPolicy for L3.
- Public HTTP(S) only via k3s Ingress — not Docker publishes ([docker-hygiene.md](./docker-hygiene.md)).

## k8s-workload (L3)

```bash
./forge sandbox enter myapp --profile k8s-workload
# applies myapp/k8s/ into FORGE_K8S_NAMESPACE (default forge-agents)
```

## Incus (L2, optional)

```bash
./sandbox/scripts/install-incus.sh   # sudo TTY
newgrp incus-admin                   # or re-login
./forge sandbox enter <project> --profile incus
```

LXD snap may remain installed but inactive; do not dual-run LXD + Incus for forge workloads.

## Agent cells

- Metadata: `/media/diestrin/data/forge/agent-cells/<id>/`
- `agent-workspace.path` — host path operators/Cursor can open alongside the project
- Container sees **only** `/workspace` (the project). No Docker socket. No sibling projects.
- Writable mounts (`FORGE_AGENT_RW=true`, default): cell runs as root inside the
  container because rootless Docker remaps host uid binds to `root:root`. Isolation
  still comes from mount + no docker.sock, not from an unprivileged container uid.

## Smoke tests

```bash
./forge sandbox smoke
# or: make sandbox-smoke
```

Checks: trusted + devcontainer run `hello`; agent-cell cannot see `docker.sock` or unrelated Projects paths; write-outside-mount fails closed; publish binds localhost.

## host-watch

New runtime process names for Incus (when installed) are listed in
`security/host-watch/config/allowlists.example.toml`. After install, merge into
`~/.config/host-watch/allowlists.toml` if alerts fire on `incusd` / `incus`.
