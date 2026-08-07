# homelab-forge

Declarative, agent-operated home lab platform for a single powerful workstation/server
(Intel NUC class): remote development, sandboxed project execution, local Kubernetes,
and an agentic software factory.

> **Status:** Phase 4 complete — git tasks + GitHub Projects + worker daemon + Vault AppRole.
> Next: Phase 5 (portfolio hardening). Follow [`PLAN.md`](./PLAN.md) and [`docs/phases/`](./docs/phases/).
>
> **Public from day one** — never commit secrets. Vault is SoR; see [`docs/runbooks/vault.md`](./docs/runbooks/vault.md).

## Goals

- Treat the host as infrastructure-as-code (Nix on Ubuntu), reproducible and portfolio-grade.
- Support Cursor over hardened public SSH without compromising isolation between projects.
- Run k3s with Traefik on 80/443, Let’s Encrypt, and home router port-forward (No-IP).
- Enable an agentic workflow: chat → git tasks (+ GitHub Projects) → sandboxed workers → review.
- Store secrets in Vault; continuous deliver with Argo CD from `main`.
- **Import** `host-watch` in-tree; mine `local-brain` lessons instead of reinventing them.

## Architecture

```text
                         Internet
                             |
              No-IP DDNS → home router forwards
                     22/tcp, 80/tcp, 443/tcp
                             |
          +------------------+-------------------+
          |         Ubuntu host (Nix+HM)         |
          |  public SSH (keys) | UFW | host-watch |
          +----------+--------------+------------+
                     |              |
            sandboxes (L1/L4)    k3s (containerd)
             agent cells           Traefik :80/:443
                     |              | Let's Encrypt
         factory/tasks (git SoT)    forge-system:
         GitHub Projects mirror       Vault + Argo CD
                     |                    ^
         worker daemon → PR → review → merge main ─┘
```

Factory details: [`factory/README.md`](./factory/README.md) · board:
[homelab-forge factory](https://github.com/users/diestrin/projects/1).

## Quick start (this host)

```bash
./bootstrap                 # Home Manager
./bootstrap --system        # + system-manager sysctl/journald (sudo TTY)

./forge sandbox init
./forge sandbox enter sandbox/examples/hello-flake --profile trusted
./forge sandbox smoke

./forge factory validate
./forge factory sync
./forge factory demo        # guided task → worker PR → Argo path
```

Details: [`nix/README.md`](./nix/README.md), [`sandbox/README.md`](./sandbox/README.md),
[`docs/runbooks/factory.md`](./docs/runbooks/factory.md).

## Threat model

The host is a single-user forge: hardened public SSH, UFW default-deny, and host-watch IDS.
Projects share one kernel, so isolation is **layered**, not absolute hypervisor multi-tenant security.

**Sandboxes:** `trusted` (L0) is the operator’s full host session. `devcontainer` (L1) and
`agent-cell` (L4) run in rootless Docker with **project-only bind mounts**, resource caps,
**no Docker socket**, and localhost-only publish — so a compromised cell should not reach
sibling project trees or the host dockerd control plane. Writable agent-cells run as root
*inside* the container (rootless uid remap); isolation is the mount set, not the container uid.
`incus` (L2) raises the boundary to a system container when installed. `k8s-workload` (L3)
uses NetworkPolicies in `forge-agents`.

**Factory:** Orchestrator writes git tasks only. Workers claim one task, use Vault AppRole
short-lived tokens, and stop at `review`. Merge to `main` is a human gate; Argo CD is the only
steady-state deploy path. The opt-in worker daemon can push branches if credentials exist —
keep the `proposed` queue intentional. Residual risk: container escape / kernel bugs, and
anything the operator runs under `trusted`. Secrets stay off the git tree and off shared mounts.

## Repository layout

```
homelab-forge/
  PLAN.md                 # Master plan + agent handoff
  README.md               # This file
  bootstrap               # Idempotent HM (+ optional system-manager) apply
  forge                   # Sandbox + factory CLI
  Makefile                # sandbox-* / factory-* convenience targets
  docs/
    current-state.md      # Snapshot of the host
    decisions/            # Architecture Decision Records (ADRs)
    phases/               # Ordered implementation phases
    runbooks/             # network, restore, secrets, docker, sandbox, factory, cursor
  nix/                    # flakes, home-manager, system-manager modules
  sandbox/
    images/               # L1/L4 Dockerfile (Nix + direnv)
    profiles/             # trusted, devcontainer, incus, k8s-workload, agent-cell
    templates/            # flake+direnv project template
    examples/             # hello-flake sample
    scripts/              # smoke tests, layout, optional Incus install
  k8s/                    # cluster manifests; Argo CD syncs from main
  factory/                # task schema, tasks, worker daemon, playbooks
  security/
    host-watch/           # imported host IDS (from ../host-watch)
    scripts/              # install-host-watch + Phase 0 harden/apply helpers
```

## Locked decisions (summary)

See [`PLAN.md`](./PLAN.md) “Accepted answers” and ADRs 001–008: direct LE + port-forward,
public SSH, Ubuntu+Nix, git+GitHub Projects, public repo, `localpower.diegobarahona.com`,
Vault, in-tree host-watch, Argo CD.

## Related existing projects

| Path | Role relative to this repo |
| --- | --- |
| [`../host-watch`](../host-watch) | Host IDS — **import** into `security/host-watch/`, then deprecate sibling. |
| [`../local-brain`](../local-brain) | Earlier security/performance notes for this NUC. **Mine for requirements**, then supersede. |
| [`../dev-machine`](../dev-machine) | Prototype Nix+direnv Docker image — ideas reused in `sandbox/images/Dockerfile`. |

## For follow-up agents

1. Read [`PLAN.md`](./PLAN.md) end-to-end.
2. Read [`docs/current-state.md`](./docs/current-state.md).
3. Execute **one phase at a time** from [`docs/phases/`](./docs/phases/), updating checkboxes and ADRs as decisions solidify.
4. Do **not** install cluster/ingress or expose ports 80/443 until Phase 0 security gates pass.
