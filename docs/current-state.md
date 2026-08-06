# Current host state (planning baseline)

Captured 2026-08-06 on host `localpower`. Re-verify before applying changes.

## Hardware / OS

| Item | Value |
| --- | --- |
| Machine | Intel NUC, `Intel(R) Core(TM) i7-10710U` (6c/12t) |
| RAM | 62 GiB |
| Root FS | `/` on `nvme0n1p7` ~130G (≈98G free) |
| Data FS | `/media/diestrin/data` on `nvme0n1p3` ~562G (≈381G free) |
| OS | Ubuntu 24.04.4 LTS (`noble`), kernel `6.8.0-136-generic` |
| Virtualization | VT-x available |
| Primary NIC in use | Wi-Fi `wlp0s20f3` → `192.168.86.123/24` |
| Ethernet | `eno1` **DOWN** (prefer enabling for server reliability) |

## Already present

- **Nix** 2.31.0 via `~/.nix-profile` (no Home Manager / no NixOS).
- **Docker Engine** 29.4.3 in **rootless** mode, cgroup v2, overlay2. Mostly idle (1 stopped container, many images).
- **SSH** listening on `:22` (all interfaces). Password auth still **enabled** in `sshd_config.d` hardening snippet (local-network oriented).
- Projects live under `/media/diestrin/data/Projects/`.
- Cursor remote server processes active for SSH-based development.

## Not present / not active

- `k3s` / `kubectl` not installed.
- `podman` / `home-manager` not installed.
- `host-watch` timer/service **not installed** (repo exists; no `~/.config/host-watch`).
- No listener on public `:80` / `:443` at planning time.
- UFW / fail2ban status should be re-checked before Phase 0 (prior `local-brain` docs assumed incomplete hardening).

## Public exposure context

**Intended (accepted):** No-IP DDNS → home public IP → router port-forward → NUC.
Preferred app/SSH hostname: `localpower.diegobarahona.com` (verify exact DNS
spelling/zone in Phase 0; older notes used `diegbarahona.com` without the `o`).

Historical `local-brain` docs also mention nonstandard SSH ports. Treat live
reachability, forwards, and CGNAT status as **unknown until Phase 0 re-audit**.

## Implications for the plan

1. Prefer **incremental Nix on Ubuntu** over a big-bang NixOS reinstall while this box is the daily remote-dev host.
2. Disk layout already separates OS vs data — keep cluster/state and project sandboxes on the data volume where possible.
3. Rootless Docker coexists awkwardly with k3s (often needs root/privileged components). Plan networking & runtime coexistence explicitly (ADR-003).
4. Wi-Fi as uplink is a reliability risk for ingress/HA demos; Phase 0 should prefer ethernet.
