# Current host state

Re-verified 2026-08-06 during Phase 1 on host `localpower`.

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

## Phase 1 controls (applied)

| Control | Status |
| --- | --- |
| Flake | [`nix/flake.nix`](../nix/flake.nix) — nixpkgs 25.05, Home Manager, system-manager |
| Home Manager | Active for `diestrin` (zsh/OMZ/Spaceship, git, direnv, CLIs) |
| Apply UX | [`./bootstrap`](../bootstrap); docs in [`nix/README.md`](../nix/README.md) |
| L0 sample | [`sandbox/examples/hello-flake/`](../sandbox/examples/hello-flake/) — `use flake` + direnv verified |
| system-manager | Modules for sysctl/journald; activate with `./bootstrap --system` (sudo TTY) |
| Package ownership | [`docs/runbooks/package-ownership.md`](./runbooks/package-ownership.md) |
| Config backups | `backups/phase1_*` + `~/.zshrc.backup-phase1` (gitignored / home) |

## Already present

- **Nix** single-user + **Home Manager** via repo flake.
- **Docker Engine** rootless; no containers publishing host ports after Phase 0 prune of idle test container.
- Projects under `/media/diestrin/data/Projects/`.
- Cursor remote server over SSH (session survived hardening + HM switch).

## Not present / deferred

- `k3s` / `kubectl` / Vault / Argo CD (Phase 3).
- Opening host `:80` / `:443`.
- L1/L2 sandbox runtimes (Phase 2); `../dev-machine` still the L1 idea source.

## Public exposure (redacted)

See [`docs/runbooks/network-exposure.md`](./runbooks/network-exposure.md). Private IPs / router UI notes:
`/media/diestrin/data/secrets/bootstrap/inventory.private.md`.

- Hostname: `localpower.diegobarahona.com` (CNAME → operator DDNS → home public A).
- Public IP matches DNS A (not CGNAT on this path).
- Intended eventual public ports: SSH + 80 + 443; Phase 0/1 allow **SSH only**.

## Implications

1. Incremental Nix on Ubuntu remains the path (ADR-001).
2. Keep heavy state on the data volume.
3. Wi-Fi is the Phase 0 uplink by choice; ethernet stays optional.
4. Do not open 80/443 until Phase 3 ingress work.
5. Phase 1 exit criteria met for HM + sample flake/direnv — proceed to Phase 2 when authorized.
