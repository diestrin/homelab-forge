# homelab-forge — Master Plan

This document is the handoff for follow-up agents. **Do not implement host changes until the human asks to execute a specific phase.**

**Repo posture:** public from day one — treat every commit as world-readable (no secrets, no private ntfy topics, no real tokens).

## Vision

Turn Intel NUC host `localpower` (Ubuntu 24.04, 12 threads, 62 GiB RAM) into a
**portfolio-grade home software forge**:

1. **Remote engineering workstation** — public hardened SSH + Cursor using NUC CPU/RAM/disk.
2. **Declarative host** — Nix-first automation on Ubuntu for tooling and selected system config.
3. **Sandboxed multi-project runtime** — open/run projects without cross-contamination.
4. **Local Kubernetes** — k3s with Ingress on 80/443, Let’s Encrypt, router port-forward via No-IP.
5. **Agentic factory** — orchestrator chats create git tasks (GitHub Projects board); workers in sandboxes; review before deploy.
6. **Secrets** — HashiCorp Vault as system of record (after cluster exists).
7. **GitOps CD** — Argo CD syncs cluster state from `main` after merge.
8. **In-tree host IDS** — `host-watch` imported under `security/host-watch/`.

Success looks like a credible open-source repo demonstrating infrastructure judgment,
not a pile of manual `apt install` notes.

## Non-goals (v1)

- Multi-node HA cluster or multi-tenant SaaS.
- Fully autonomous production deploys without human review (PR review still required; Argo CD deploys what `main` already contains).
- Big-bang NixOS reinstall (Ubuntu + Nix for this roadmap).
- Rewriting `host-watch` during import (port as-is, then evolve).
- Cloudflare Tunnel / Tailscale Funnel as the primary WAN path.
- Long-term dual maintenance of sibling `../host-watch` after import.

## Current reality (summary)

See [`docs/current-state.md`](./docs/current-state.md).

Highlights:

- Nix + Home Manager present (Phase 1 flake under `nix/`); NixOS not in use.
- Phases 0–5 applied (see [`docs/current-state.md`](./docs/current-state.md)); `v0.1.0` tagged.
- Wi-Fi is the active uplink; ethernet is down.
- Data disk has ample space; root disk is smaller — put heavy state on `/media/diestrin/data`.
- WAN: No-IP → home IP → router forward → NUC; `localpower.diegobarahona.com`.

## Architecture (target)

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
            sandboxes (L1/L2)    k3s (containerd)
             agent cells           Traefik :80/:443
                     |              | Let's Encrypt
                     |         forge-system:
                     |           Vault + Argo CD
         PR review → merge main ──┘ syncs k8s/
```

### Control vs data plane

| Concern | Tooling |
| --- | --- |
| Host & user config | Nix flakes + Home Manager (+ system-manager or equivalent) |
| Project toolchains | Per-repo flakes + direnv |
| Isolation | Layered profiles (ADR-002) |
| Serving | k3s + Traefik Ingress + NetworkPolicies + Let’s Encrypt |
| WAN | Direct port-forward via No-IP / home router |
| Secrets | HashiCorp Vault (ADR-007); bootstrap sealed store until then |
| CD / GitOps | Argo CD tracks `main` → syncs `k8s/` (ADR-008) |
| Detection | In-tree `security/host-watch` + cluster/node alerts → ntfy |
| Factory | Git tasks + GitHub Projects board + orchestrator/worker agents (ADR-004) |

## Decision records

| ADR | Topic | Status |
| --- | --- | --- |
| [ADR-001](./docs/decisions/ADR-001-nix-on-ubuntu.md) | Nix on Ubuntu; defer NixOS | Accepted |
| [ADR-002](./docs/decisions/ADR-002-sandbox-model.md) | Layered sandbox profiles | Accepted |
| [ADR-003](./docs/decisions/ADR-003-k3s-ingress.md) | k3s + Traefik + LE + direct ports | Accepted |
| [ADR-004](./docs/decisions/ADR-004-agentic-factory.md) | Git tasks + GitHub Projects | Accepted |
| [ADR-005](./docs/decisions/ADR-005-host-watch-adoption.md) | Import host-watch in-tree | Accepted |
| [ADR-006](./docs/decisions/ADR-006-public-ssh.md) | Hardened public SSH | Accepted |
| [ADR-007](./docs/decisions/ADR-007-secrets-vault.md) | HashiCorp Vault | Accepted |
| [ADR-008](./docs/decisions/ADR-008-gitops-argocd.md) | Argo CD GitOps on `main` | Accepted |
| [ADR-009](./docs/decisions/ADR-009-slack-cursor-factory.md) | Slack intake + Cursor SDK agents | Accepted |

## Accepted answers (formerly open questions)

| # | Question | Decision |
| --- | --- | --- |
| 1 | WAN 80/443 | **Direct port-forward + Let’s Encrypt** (HTTP-01 preferred when 80 is open) |
| 2 | SSH | **Public SSH**, hardened (keys only, fail2ban, UFW) — ADR-006 |
| 3 | OS | **Ubuntu + Nix now**; no NixOS migration in v1 — ADR-001 |
| 4 | Factory board | **Git source of truth + GitHub Projects** board — ADR-004 |
| 5 | OSS timeline | **Public from day one** — scrub every commit |
| 6 | Domain / TLS | Prefer **`localpower.diegobarahona.com`** (No-IP → home IP → NUC); alternate subdomain under the same zone if that name cannot serve HTTPS cleanly |
| — | Secrets | **HashiCorp Vault** on k3s after cluster exists — ADR-007 |
| — | Host IDS | **Import `host-watch`** into `security/host-watch/` — ADR-005 |
| — | CD | **Argo CD** syncs from `main` — ADR-008 |
| — | Slack / unattended factory | **Socket Mode + plan PR gate + Cursor SDK** — ADR-009 |

## What to take from prior work

### `host-watch` — **import into this repo**

Purpose-built IDS for this exact remote-dev pattern (Cursor, Docker, Nix, Node).
Import under `security/host-watch/` (ADR-005); do not leave it as a permanent sibling dependency.

Phase 0:

- Copy/port code into `security/host-watch/` (preserve MIT notice).
- Install from the in-tree scripts + ntfy + linger.
- Maintain allowlists here as platforms (k3s, Traefik, Vault, Argo CD) come online.
- Deprecate `../host-watch` after the import is verified.

### `local-brain` — **requirements mining only**

Useful lessons to preserve in this plan:

- Internet exposure demands SSH hardening, fail2ban, firewall default-deny.
- Never publish admin UIs (e.g. pgAdmin) on `0.0.0.0`.
- Need alerting (email/Telegram ideas → prefer ntfy via host-watch for v1).
- Firmware/updates and ethernet-over-Wi-Fi recommendations still valid.

Do **not** continue growing `local-brain` as the platform home; supersede with `homelab-forge` runbooks.

### `dev-machine` — **sandbox seed**

Dockerfile prototyping Nix + direnv in a container maps cleanly to ADR-002 L1.
Reuse rather than invent a new base image narrative.

## Phased roadmap

Execute **in order**. Each phase has its own checklist file.

| Phase | Doc | Outcome |
| --- | --- | --- |
| 0 | [`docs/phases/phase-0-secure-baseline.md`](./docs/phases/phase-0-secure-baseline.md) | Public SSH hardened + firewall; **import + install** in-tree host-watch; inventory No-IP/forwards; **not** yet opening 80/443 |
| 1 | [`docs/phases/phase-1-nix-foundation.md`](./docs/phases/phase-1-nix-foundation.md) | Declarative user/host tooling via flakes |
| 2 | [`docs/phases/phase-2-sandbox-platform.md`](./docs/phases/phase-2-sandbox-platform.md) | Isolation profiles + Cursor-friendly DX |
| 3 | [`docs/phases/phase-3-k3s-platform.md`](./docs/phases/phase-3-k3s-platform.md) | k3s, Traefik, LE, Vault, **Argo CD**, demo Ingress |
| 4 | [`docs/phases/phase-4-agentic-factory.md`](./docs/phases/phase-4-agentic-factory.md) | Git tasks + GitHub Projects + workers (deploys via Argo on `main`) |
| 5 | [`docs/phases/phase-5-portfolio-hardening.md`](./docs/phases/phase-5-portfolio-hardening.md) | OSS polish, CI, demo narrative |

### Suggested sequencing rationale

Security before ingress. Declarative tooling before sandboxes. Sandboxes before
agents that write code. Cluster (+ Vault + LE + Argo CD) before public demos.
Factory last so it lands on stable rails.

## Agent operating rules

1. Read this file + `docs/current-state.md` + relevant phase + ADRs before changing anything.
2. One phase per working session unless the human expands scope.
3. Prefer idempotent, documented changes; backup configs before editing sshd/UFW.
4. Never disable the firewall to “make k3s work.”
5. Update phase checkboxes and ADRs as work completes.
6. New public listener ⇒ update in-tree host-watch allowlists in the same change set.
7. Do not commit secrets; do not force-push; do not open 80/443 before Phase 0 exit criteria.
8. Assume the GitHub remote is or will be **public** — examples and placeholders only.
9. Cluster changes ship by merging to `main` for Argo CD to sync — do not bypass GitOps for steady-state deploys.

## Immediate next action (when execution is authorized)

**Phase 5 complete** (2026-08-08) — all planned phases done; `v0.1.0` released.
Steady state: merge PRs to `main` for Argo CD, keep host-watch allowlists current,
and queue factory tasks intentionally. New scope requires a new phase doc + human sign-off.
