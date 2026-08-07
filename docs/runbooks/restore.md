# Restore rundown

One-page recovery notes. Backups are mostly manual until later automation.

## What must be backed up

| Asset | Typical location | Notes |
| --- | --- | --- |
| SSH host keys + sshd drop-ins | `/etc/ssh/` | Phase 0 scripts snapshot under `backups/phase0_*` |
| User authorized keys | `~/.ssh/authorized_keys` | Keep offline copy of private keys used by Cursor |
| Bootstrap secrets | `/media/diestrin/data/secrets/bootstrap/` | age identity + `secrets.age` (ntfy, interim tokens) |
| host-watch runtime config | `~/.config/host-watch/` | Not in git; ntfy URL is secret |
| Nix / Home Manager | `nix/` in this repo + HM profile | Re-apply with `./bootstrap` |
| system-manager state | `/run/system-manager`, `/etc` drop-ins | Re-apply with `./bootstrap --system` |
| Dotfile backups | `backups/phase1_*`, `~/.zshrc.backup-phase1` | Pre-HM shell |
| Project data | `/media/diestrin/data/Projects/` | Data disk; largest restore surface |
| Future cluster / Vault / Argo | data-disk volumes + Vault unseal | Phase 3+ |

## Break-glass

1. Physical console on the NUC (confirmed available for Phase 0).
2. Log in as `diestrin` (local account).
3. If SSH is broken after a hardening change:
   - Restore latest `backups/phase0_*/sshd_config.d/` into `/etc/ssh/sshd_config.d/`
   - Or move aside `99-homelab-forge.conf` and restore the previous drop-in
   - `sudo sshd -t && sudo systemctl restart ssh`
4. If UFW locked you out on LAN unexpectedly: from console,
   `sudo ufw allow from 192.168.86.0/24 to any port 22` then re-apply the rate-limit policy intentionally.

## Minimal restore order

1. OS boots; network (Wi-Fi default in Phase 0).
2. Restore SSH access (keys + sshd + UFW allow SSH).
3. Decrypt bootstrap secrets with age; restore host-watch `notify.url`.
4. Reinstall host-watch from this repo: `./security/scripts/install-host-watch.sh`.
5. Re-apply declarative tooling: `./bootstrap` then `./bootstrap --system`.
6. Re-clone / remount project data on the data disk.
7. Later: unseal Vault / re-sync Argo from `main` (Phase 3).

## Phase 3 secret migration reminder

Bootstrap age store is temporary. After Vault is SoR, migrate ntfy and tokens,
then destroy or shrink the bootstrap store to unseal materials only (ADR-007).
