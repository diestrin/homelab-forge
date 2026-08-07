# homelab-forge

Declarative, agent-operated home lab platform for a single powerful workstation/server
(Intel NUC class): remote development, sandboxed project execution, local Kubernetes,
and an agentic software factory.

> **Status:** Phase 3 complete — k3s + Traefik/LE + Vault + ESO + Argo CD.
> Next: Phase 4 (agentic factory). Follow [`PLAN.md`](./PLAN.md) and [`docs/phases/`](./docs/phases/).
>
> **Public from day one** — never commit secrets. Vault is SoR; see [`docs/runbooks/vault.md`](./docs/runbooks/vault.md).

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

./forge sandbox init
./forge sandbox enter sandbox/examples/hello-flake --profile trusted
./forge sandbox smoke
```

Details: [`nix/README.md`](./nix/README.md), [`sandbox/README.md`](./sandbox/README.md).

## Threat model (sandboxes)

The host is a single-user forge: hardened public SSH, UFW default-deny, and host-watch IDS.
Projects share one kernel, so isolation is **layered**, not absolute hypervisor multi-tenant security.
`trusted` (L0) is the operator’s full host session. `devcontainer` (L1) and `agent-cell` (L4) run in
rootless Docker with **project-only bind mounts**, resource caps, **no Docker socket**, and
localhost-only publish — so a compromised cell should not reach sibling project trees or the
host dockerd control plane. `incus` (L2) raises the boundary to a system container when installed.
`k8s-workload` (L3) waits on Phase 3 NetworkPolicies. Residual risk: container escape / kernel bugs,
and anything the operator runs under `trusted`. Secrets stay off the git tree and off shared mounts.

## Repository layout

```
homelab-forge/
  PLAN.md                 # Master plan + agent handoff
  README.md               # This file
  bootstrap               # Idempotent HM (+ optional system-manager) apply
  forge                   # Sandbox CLI (Phase 2)
  Makefile                # sandbox-* convenience targets
  docs/
    current-state.md      # Snapshot of the host
    decisions/            # Architecture Decision Records (ADRs)
    phases/               # Ordered implementation phases
    runbooks/             # network, restore, secrets, docker, sandbox, cursor
  nix/                    # flakes, home-manager, system-manager modules
  sandbox/
    images/               # L1/L4 Dockerfile (Nix + direnv)
    profiles/             # trusted, devcontainer, incus, k8s-workload, agent-cell
    templates/            # flake+direnv project template
    examples/             # hello-flake sample
    scripts/              # smoke tests, layout, optional Incus install
  k8s/                    # cluster manifests; Argo CD syncs from main
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
| [`../dev-machine`](../dev-machine) | Prototype Nix+direnv Docker image — ideas reused in `sandbox/images/Dockerfile`. |

## For follow-up agents

1. Read [`PLAN.md`](./PLAN.md) end-to-end.
2. Read [`docs/current-state.md`](./docs/current-state.md).
3. Execute **one phase at a time** from [`docs/phases/`](./docs/phases/), updating checkboxes and ADRs as decisions solidify.
4. Do **not** install cluster/ingress or expose ports 80/443 until Phase 0 security gates pass.
