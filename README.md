# homelab-forge

Declarative, agent-operated home lab platform for a single powerful workstation/server
(Intel NUC class): remote development, sandboxed project execution, local Kubernetes,
and an agentic software factory.

> **Status:** Phase 1 complete — Nix flake + Home Manager + flake/direnv sample.
> Next: Phase 2 (sandbox platform). Follow [`PLAN.md`](./PLAN.md) and [`docs/phases/`](./docs/phases/).
>
> **Public from day one** — never commit secrets. Bootstrap age store on the data disk until Vault (Phase 3).

## Goals

- Treat the host as infrastructure-as-code (Nix on Ubuntu), reproducible and portfolio-grade.
- Support Cursor over hardened public SSH without compromising isolation between projects.
- Run k3s with Traefik on 80/443, Let’s Encrypt, and home router port-forward (No-IP).
- Enable an agentic workflow: chat → git tasks (+ GitHub Projects) → sandboxed workers → review.
- Store secrets in Vault; continuous deliver with Argo CD from `main`.
- **Import** `host-watch` in-tree; mine `local-brain` lessons instead of reinventing them.

## Quick start (this host)

```bash
./bootstrap                 # Home Manager
./bootstrap --system        # + system-manager sysctl/journald (sudo TTY)
```

Details: [`nix/README.md`](./nix/README.md). L0 project template: [`sandbox/templates/flake-direnv/`](./sandbox/templates/flake-direnv/).

## Repository layout

```
homelab-forge/
  PLAN.md                 # Master plan + agent handoff
  README.md               # This file
  bootstrap               # Idempotent HM (+ optional system-manager) apply
  docs/
    current-state.md      # Snapshot of the host
    decisions/            # Architecture Decision Records (ADRs)
    phases/               # Ordered implementation phases
    runbooks/             # network, restore, secrets, docker, package ownership
  nix/                    # flakes, home-manager, system-manager modules
  sandbox/
    templates/            # flake+direnv project template
    examples/             # hello-flake sample
  k8s/                    # (future) cluster manifests; Argo CD syncs from main
  factory/                # (future) agent orchestration contracts & task schemas
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
| [`../dev-machine`](../dev-machine) | Prototype Nix+direnv Docker image for sandboxed shells. **Reuse ideas** (Phase 2 L1). |

## For follow-up agents

1. Read [`PLAN.md`](./PLAN.md) end-to-end.
2. Read [`docs/current-state.md`](./docs/current-state.md).
3. Execute **one phase at a time** from [`docs/phases/`](./docs/phases/), updating checkboxes and ADRs as decisions solidify.
4. Do **not** install cluster/ingress or expose ports 80/443 until Phase 0 security gates pass.
