# Current host state

Re-verified 2026-08-07 during Phase 4 on host `localpower`.

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

## Phase 4 controls (applied)

| Control | Status |
| --- | --- |
| Task schema | `factory/schema/task.schema.json` + YAML tasks under `factory/tasks/` |
| GitHub Projects | Public board [homelab-forge factory](https://github.com/users/diestrin/projects/1); git → board via `./forge factory sync` |
| Orchestrator / worker playbooks | `factory/orchestrator/PLAYBOOK.md`, `factory/worker/PLAYBOOK.md` |
| Worker runtime | `forge factory worker` daemon; isolated git worktree + `agent-cell`; budget watchdog |
| Vault AppRole | `forge-agent`; host file `/media/diestrin/data/secrets/vault/approle-forge-agent.env` (mode 600, not in git) |
| Review gate | `factory/review/CHECKLIST.md`; demo PR [#2](https://github.com/diestrin/homelab-forge/pull/2) at `review` |
| systemd unit | `factory/systemd/forge-factory-worker.service` installed under user units; **disabled** until explicitly started |
| Artifacts | `/media/diestrin/data/forge/factory/artifacts/` (logs, diffs, PR urls) |

## Public exposure (redacted)

- Hostname: `localpower.diegobarahona.com` — HTTPS demo hello-app (Phase 3 copy until PR #2 merges).
- SSH remains hardened; Vault/Argo UIs ClusterIP only (port-forward / SSH tunnel).
- Factory Projects board is public; task YAML contains no secrets.

## Implications

1. After reboot: unseal Vault ([vault.md](./runbooks/vault.md)); start Vault port-forward if workers need AppRole; Argo reconnects to git automatically.
2. Steady-state cluster changes: merge to `main` ([gitops.md](./runbooks/gitops.md)).
3. Factory: keep `proposed` queue intentional before `systemctl --user start forge-factory-worker`.
4. Next phase: Phase 5 portfolio hardening.
