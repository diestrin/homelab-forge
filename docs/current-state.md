# Current host state

Re-verified 2026-08-06 during Phase 0 on host `localpower`.

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

## Phase 0 controls (applied)

| Control | Status |
| --- | --- |
| SSH | Key-only; `PermitRootLogin no`; `AllowUsers diestrin`; `AllowTcpForwarding yes` (`99-homelab-forge.conf`) |
| UFW | Active; default deny inbound; `limit 22/tcp`; deny `5050`; **80/443 closed** |
| fail2ban | Active sshd jail; LAN `ignoreip` |
| host-watch | In-tree; user timer + linger; ntfy via bootstrap secrets |
| Bootstrap secrets | age store on data disk (outside git) — [`docs/runbooks/bootstrap-secrets.md`](./runbooks/bootstrap-secrets.md) |
| Config backups | `backups/phase0_*` (gitignored) |

## Already present

- **Nix** via `~/.nix-profile` (no Home Manager / no NixOS yet). **age** installed into the Nix profile for bootstrap encryption.
- **Docker Engine** rootless; no containers publishing host ports after Phase 0 prune of idle test container.
- Projects under `/media/diestrin/data/Projects/`.
- Cursor remote server over SSH (session survived hardening).

## Not present / deferred

- `k3s` / `kubectl` / Vault / Argo CD (Phase 3).
- Home Manager (Phase 1).
- Opening host `:80` / `:443`.

## Public exposure (redacted)

See [`docs/runbooks/network-exposure.md`](./runbooks/network-exposure.md). Private IPs / router UI notes:
`/media/diestrin/data/secrets/bootstrap/inventory.private.md`.

- Hostname: `localpower.diegobarahona.com` (CNAME → operator DDNS → home public A).
- Public IP matches DNS A (not CGNAT on this path).
- Intended eventual public ports: SSH + 80 + 443; Phase 0 allows **SSH only**.

## Implications

1. Incremental Nix on Ubuntu remains the path (ADR-001).
2. Keep heavy state on the data volume.
3. Wi-Fi is the Phase 0 uplink by choice; ethernet stays optional.
4. Do not open 80/443 until Phase 3 ingress work.
5. Phase 0 exit criteria met — proceed to Phase 1 when authorized.
