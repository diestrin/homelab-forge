# Bootstrap on a clean Ubuntu 24.04 machine

Phase 5 exit criterion: the declarative subset of this repo (Nix + Home Manager)
applies on a fresh Ubuntu 24.04 host with no WAN ingress, no k3s, and no secrets.
Verified 2026-08-07 in a pristine `ubuntu:24.04` container (rootless Docker,
no systemd) — the closest cheap approximation of a fresh VM.

## Scope

| Included | Excluded (needs real host / systemd / WAN) |
| --- | --- |
| Single-user Nix install | `./bootstrap --system` (system-manager needs systemd) |
| Repo clone | Phase 0 hardening (sshd/UFW/fail2ban) |
| `./bootstrap` (Home Manager switch) | k3s / Traefik / Vault / Argo CD |
| HM-managed shell, git, CLI, direnv | host-watch timer, router/DDNS setup |

## Procedure

As root (or with sudo), on a fresh Ubuntu 24.04 install:

```bash
apt-get update
apt-get install -y curl git xz-utils ca-certificates

# Skip if your login user already exists; HM config targets user "diestrin".
useradd -m -s /bin/bash diestrin

# Single-user Nix wants /nix owned by the login user.
mkdir -m 0755 /nix && chown diestrin /nix
```

Then as the login user:

```bash
curl -fsSL https://nixos.org/nix/install -o /tmp/install-nix.sh
sh /tmp/install-nix.sh --no-daemon
. ~/.nix-profile/etc/profile.d/nix.sh

git clone https://github.com/diestrin/homelab-forge.git ~/homelab-forge
cd ~/homelab-forge
./bootstrap
```

`./bootstrap` writes `~/.config/nix/nix.conf` (flakes), then runs
`home-manager switch --flake ./nix#diestrin -b backup-phase1`. First run
downloads the closure from cache.nixos.org (a few GB; time depends on
bandwidth).

## Verify

```bash
home-manager --version
cat ~/.homelab-forge-hm     # marker file written by the HM config
```

Log out/in (or `exec zsh`) to pick up the HM-managed shell.

## Adapting to another user/host

`nix/home/diestrin.nix` hardcodes `home.username = "diestrin"` and
`/home/diestrin`. For a different user, copy that file, adjust both values, and
add a matching `homeConfigurations` entry in `nix/flake.nix`.

## Continuing to the full platform

On the real host (with systemd, sudo, and WAN):

1. `./bootstrap --system` — sysctl/journald via system-manager.
2. Phase 0: `security/scripts/` hardening + host-watch install.
3. Phase 3: `k8s/bootstrap/` (k3s → cert-manager → Vault → ESO → Argo CD).
4. Day-2: [operations.md](./operations.md).
