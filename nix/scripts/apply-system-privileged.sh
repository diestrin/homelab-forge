#!/usr/bin/env bash
# Privileged Phase 1 host bits via system-manager (requires sudo TTY).
#   ./nix/scripts/apply-system-privileged.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
FLAKE="$REPO_ROOT/nix"

echo "==> Caching sudo credentials"
sudo -v

echo "==> system-manager switch (localpower)"
nix run 'github:numtide/system-manager' -- switch --flake "$FLAKE#localpower" --sudo

echo "==> Verification"
test -f /etc/sysctl.d/99-homelab-forge.conf
test -f /etc/systemd/journald.conf.d/99-homelab-forge.conf
sysctl fs.inotify.max_user_watches fs.inotify.max_user_instances || true
systemctl is-active homelab-forge-sysctl.service || true

echo
echo "==> Privileged Phase 1 system-manager apply complete."
echo "    SSH/UFW/fail2ban remain under security/scripts/ (Phase 0)."
