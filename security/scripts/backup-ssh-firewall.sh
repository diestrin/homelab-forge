#!/usr/bin/env bash
# Backup sshd + UFW + fail2ban configs before Phase 0 hardening.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_DIR="${BACKUP_DIR:-$REPO_ROOT/backups/phase0_${STAMP}}"

mkdir -p "$BACKUP_DIR"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Re-running with sudo..."
  exec sudo BACKUP_DIR="$BACKUP_DIR" bash "$0" "$@"
fi

echo "==> Backing up to $BACKUP_DIR"
cp -a /etc/ssh/sshd_config "$BACKUP_DIR/sshd_config"
mkdir -p "$BACKUP_DIR/sshd_config.d"
cp -a /etc/ssh/sshd_config.d/. "$BACKUP_DIR/sshd_config.d/" 2>/dev/null || true
cp -a /etc/ssh/banner.txt "$BACKUP_DIR/banner.txt" 2>/dev/null || true

if [[ -d /etc/fail2ban ]]; then
  mkdir -p "$BACKUP_DIR/fail2ban"
  cp -a /etc/fail2ban/. "$BACKUP_DIR/fail2ban/" 2>/dev/null || true
fi

if command -v ufw >/dev/null 2>&1; then
  ufw status verbose >"$BACKUP_DIR/ufw-status.txt" 2>&1 || true
  cp -a /etc/ufw "$BACKUP_DIR/ufw" 2>/dev/null || true
fi

ss -tlnp >"$BACKUP_DIR/listeners.txt" 2>/dev/null || true
chmod -R go-rwx "$BACKUP_DIR" || true

echo "$BACKUP_DIR" >"$REPO_ROOT/backups/LATEST_PHASE0"
echo "==> Backup complete: $BACKUP_DIR"
