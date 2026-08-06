# homelab-forge

Declarative, agent-operated home lab platform for a single powerful workstation/server
(Intel NUC class): remote development, sandboxed project execution, local Kubernetes,
and an agentic software factory.

> **Status:** Phase 0 complete — hardened public SSH, UFW, fail2ban, in-tree `security/host-watch/`.
> Next: Phase 1 (Nix foundation). Follow [`PLAN.md`](./PLAN.md) and [`docs/phases/`](./docs/phases/).
>
> **Public from day one** — never commit secrets. Bootstrap age store on the data disk until Vault (Phase 3).

## Goals

- Treat the host as infrastructure-as-code (Nix on Ubuntu), reproducible and portfolio-grade.
- Support Cursor over hardened public SSH without compromising isolation between projects.
- Run k3s with Traefik on 80/443, Let’s Encrypt, and home router port-forward (No-IP).
- Enable an agentic workflow: chat → git tasks (+ GitHub Projects) → sandboxed workers → review.
- Store secrets in Vault; continuous deliver with Argo CD from `main`.
- **Import** `host-watch` in-tree; mine `local-brain` lessons instead of reinventing them.

## Repository layout (planned)

```
homelab-forge/
  PLAN.md                 # Master plan + agent handoff
  README.md               # This file
  docs/
    current-state.md      # Snapshot of the host when planning started
    decisions/            # Architecture Decision Records (ADRs)
    phases/               # Ordered implementation phases for follow-up agents
  nix/                    # (future) flakes, home-manager, system modules
  k8s/                    # (future) cluster manifests; Argo CD syncs from main
  factory/                # (future) agent orchestration contracts & task schemas
  sandbox/                # (future) project sandbox profiles & tooling
  security/
    host-watch/           # imported host IDS (from ../host-watch)
    scripts/              # install-host-watch + Phase 0 harden/apply helpers
  docs/runbooks/          # network exposure, restore, bootstrap secrets, docker hygiene
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
| [`../dev-machine`](../dev-machine) | Prototype Nix+direnv Docker image for sandboxed shells. **Reuse ideas**. |

## For follow-up agents

1. Read [`PLAN.md`](./PLAN.md) end-to-end.
2. Read [`docs/current-state.md`](./docs/current-state.md).
3. Execute **one phase at a time** from [`docs/phases/`](./docs/phases/), updating checkboxes and ADRs as decisions solidify.
4. Do **not** install cluster/ingress or expose ports 80/443 until Phase 0 security gates pass.
