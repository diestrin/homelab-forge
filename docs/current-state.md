# Current host state

Re-verified 2026-08-08 during Phase 5 on host `localpower`.

## Hardware / OS

| Item | Value |
| --- | --- |
| Machine | Intel NUC, `Intel(R) Core(TM) i7-10710U` (6c/12t) |
| RAM | 62 GiB |
| Root FS | `/` on `nvme0n1p7` ~130G |
| Data FS | `/media/diestrin/data` on `nvme0n1p3` ~562G |
| OS | Ubuntu 24.04.4 LTS (`noble`), kernel `6.8.0-136-generic` |
| Virtualization | VT-x available |
| Primary NIC (Phase 0 default) | Wi-Fi `wlp0s20f3` → LAN `192.168.86.0/24` |
| Ethernet | `eno1` **DOWN** (optional future reliability upgrade; not switched in Phase 0) |

## Phase 0–3 controls

SSH key-only, UFW default-deny, fail2ban, host-watch, Nix HM, forge sandbox CLI, k3s + Traefik/LE,
Vault, ESO, Argo CD remain in effect (see prior snapshots).

## Phase 4 controls (superseded by ADR-012)

**Note:** Custom factory pipeline (ADR-009/010/011) retired 2026-09-01 in favor of
Cursor My Machines (ADR-012). Historical records below for reference.

| Control | Status (Legacy) |
| --- | --- |
| Task schema | ~~`factory/schema/task.schema.json`~~ → GitHub Issues |
| Task board | ~~GitHub Projects~~ → GitHub Issues with labels |
| Worker runtime | ~~host daemon + SDK~~ → Cursor My Machines worker |
| Vault AppRole | `forge-agent` (still present, unused post-migration) |
| systemd units | `forge-factory-{worker,orchestrator}.service` **stopped and disabled** |

## Cursor My Machines (active since 2026-09-01, ADR-012)

| Control | Status |
| --- | --- |
| Agent interface | Cursor My Machines worker on localpower host |
| Request surfaces | Cursor Slack integration, mobile app, cursor.com/agents |
| Task management | GitHub Issues with `task` label and risk tags |
| Environment config | `.cursor/environment.json` (Nix-based setup) |
| MCP servers | Local stdio servers (Vault, internal tools) |
| Worker lifecycle | systemd user unit `cursor-my-machines-worker.service` |
| GitOps | Unchanged: merge to `main` → Argo CD syncs `k8s/` |

## Phase 5 controls (applied)

| Control | Status |
| --- | --- |
| License | MIT at repo root (host-watch keeps its own MIT notice) |
| CI | `.github/workflows/ci.yml`: flake check (eval), markdownlint, kustomize+kubeconform, task schema, shellcheck |
| Secret scan | Full-history gitleaks clean (2026-08-08); enforced in CI (`gitleaks.yml`) |
| Release | `CHANGELOG.md`; tag `v0.1.0` + GitHub release |
| Runbooks | `operations.md` (cold start), `bootstrap-clean-host.md` (verified in clean `ubuntu:24.04` container) |
| Demo | `docs/demo/factory-demo.cast` (TASK-003 → PR #4, awaiting review) |

## Public exposure (redacted)

- Hostname: `localpower.diegobarahona.com` — HTTPS demo hello-app (Phase 4 copy until PR #4 merges).
- SSH remains hardened; Vault/Argo UIs ClusterIP only (port-forward / SSH tunnel).
- Factory Projects board is public; task YAML contains no secrets.

## Implications

1. After reboot: follow [operations.md](./runbooks/operations.md) (unseal Vault, verify certs/Argo, restart Cursor worker).
2. Steady-state cluster changes: merge to `main` ([gitops.md](./runbooks/gitops.md)).
3. Agent requests: Use Cursor Slack (@Cursor), mobile app, or cursor.com/agents.
4. Task management: Create GitHub Issues with `task` label; see `.cursor/skills/homelab-task/`.
5. All planned phases complete — new scope via GitHub Issues + PR workflow.
