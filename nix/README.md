# Nix foundation (`localpower`)

Declarative user + selected host config for Ubuntu (ADR-001).

## Layout

| Path | Role |
| --- | --- |
| `flake.nix` / `flake.lock` | Pinned inputs (`nixpkgs` 25.05, Home Manager, system-manager) |
| `home/diestrin.nix` | Home Manager entry for user `diestrin` |
| `modules/home/*` | Shell (zsh/OMZ/Spaceship), git, direnv, CLIs |
| `hosts/localpower/` | system-manager entry (sysctl + journald only) |
| `modules/system/*` | Root-owned drop-ins under `/etc` |
| `scripts/apply-system-privileged.sh` | `sudo` apply for system-manager |

SSH / UFW / fail2ban stay under [`../security/scripts/`](../security/scripts/) (Phase 0).

## Apply (agents / humans)

From repo root:

```bash
./bootstrap                 # Home Manager only (no sudo)
./bootstrap --system        # + system-manager (interactive sudo)
```

Or step by step:

```bash
# User tooling
nix run home-manager/release-25.05 -- switch --flake ./nix#diestrin -b backup-phase1

# Host knobs (TTY + sudo)
./nix/scripts/apply-system-privileged.sh
```

## Checks

```bash
nix flake check ./nix
```

Builds the Home Manager activation package and the system-manager toplevel (no host mutation).

## Notes

- **Flakes must be git-tracked** — Nix ignores untracked files in a dirty worktree.
- First HM switch may move conflicting dotfiles to `*.backup-phase1`. Pre-switch copies also live under gitignored `backups/phase1_*`.
- Imperative `nix-env -i` packages (e.g. older `gh` / `age`) conflict with HM; remove them before switch (`nix-env -e <pkg>`). Keep the installer `nix` package.
- `system-manager` uses its own nixpkgs pin (not `follows` 25.05) for evaluation compatibility.
- Project environments: copy [`../sandbox/templates/flake-direnv/`](../sandbox/templates/flake-direnv/) and `direnv allow`.
