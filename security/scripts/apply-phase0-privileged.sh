#!/usr/bin/env bash
# Privileged Phase 0 steps (requires sudo). Run from a real TTY:
#   ./security/scripts/apply-phase0-privileged.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

echo "==> Caching sudo credentials"
sudo -v

echo "==> Hardening SSH / UFW / fail2ban"
"$REPO_ROOT/security/scripts/harden-ssh-ufw-fail2ban.sh"

echo "==> Enabling linger for host-watch user timer"
sudo loginctl enable-linger "${SUDO_USER:-$USER}"

echo "==> Verification"
sshd -T 2>/dev/null | grep -Ei 'passwordauthentication|permitrootlogin|authenticationmethods|allowusers|allowtcpforwarding' || \
  sudo sshd -T | grep -Ei 'passwordauthentication|permitrootlogin|authenticationmethods|allowusers|allowtcpforwarding'
sudo ufw status verbose
sudo fail2ban-client status sshd || sudo fail2ban-client status
loginctl show-user "${SUDO_USER:-$USER}" -p Linger
ss -tlnp | grep -E ':22|:80|:443' || true

echo
echo "==> Privileged Phase 0 steps complete."
echo "    Verify Cursor SSH from outside the LAN when convenient."
