#!/usr/bin/env bash
# Phase 0: key-only SSH, UFW default-deny + limit 22, fail2ban.
# Requires physical/LAN console break-glass. Keep AllowTcpForwarding for Cursor.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
ALLOW_USER="${ALLOW_USER:-diestrin}"
LAN_CIDR="${LAN_CIDR:-192.168.86.0/24}"

if [[ "${EUID}" -ne 0 ]]; then
  echo "Re-running with sudo..."
  exec sudo ALLOW_USER="$ALLOW_USER" LAN_CIDR="$LAN_CIDR" bash "$0" "$@"
fi

if [[ ! -s "/home/${ALLOW_USER}/.ssh/authorized_keys" ]]; then
  echo "error: /home/${ALLOW_USER}/.ssh/authorized_keys is empty — aborting" >&2
  exit 1
fi

echo "==> Ensuring backup exists"
bash "$REPO_ROOT/security/scripts/backup-ssh-firewall.sh"

echo "==> Installing fail2ban + ufw if needed"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq fail2ban ufw >/dev/null

echo "==> Writing sshd drop-in 99-homelab-forge.conf"
cat >/etc/ssh/sshd_config.d/99-homelab-forge.conf <<EOF
# homelab-forge Phase 0 — hardened public SSH (ADR-006)
# Managed by security/scripts/harden-ssh-ufw-fail2ban.sh

PasswordAuthentication no
PermitEmptyPasswords no
KbdInteractiveAuthentication no
ChallengeResponseAuthentication no

PubkeyAuthentication yes
AuthenticationMethods publickey

PermitRootLogin no
AllowUsers ${ALLOW_USER}

MaxAuthTries 3
MaxStartups 10:30:60
LoginGraceTime 30
ClientAliveInterval 300
ClientAliveCountMax 2

# Cursor / SSH tunnels need forwarding; do not disable.
AllowTcpForwarding yes
X11Forwarding no
GatewayPorts no
PermitTunnel no

UsePAM yes
LogLevel VERBOSE
SyslogFacility AUTH

Ciphers chacha20-poly1305@openssh.com,aes256-gcm@openssh.com,aes128-gcm@openssh.com,aes256-ctr,aes192-ctr,aes128-ctr
MACs hmac-sha2-256-etm@openssh.com,hmac-sha2-512-etm@openssh.com,hmac-sha2-256,hmac-sha2-512
KexAlgorithms curve25519-sha256@libssh.org,ecdh-sha2-nistp521,ecdh-sha2-nistp384,ecdh-sha2-nistp256,diffie-hellman-group16-sha512,diffie-hellman-group18-sha512,diffie-hellman-group14-sha256

Banner /etc/ssh/banner.txt
EOF

# Supersede older local-brain drop-in that re-enabled password auth.
if [[ -f /etc/ssh/sshd_config.d/99-security-hardening.conf ]]; then
  mv /etc/ssh/sshd_config.d/99-security-hardening.conf \
    /etc/ssh/sshd_config.d/99-security-hardening.conf.disabled-by-homelab-forge
  echo "    disabled conflicting 99-security-hardening.conf"
fi

if [[ ! -f /etc/ssh/banner.txt ]]; then
  cat >/etc/ssh/banner.txt <<'EOF'
***************************************************************************
                    AUTHORIZED ACCESS ONLY
***************************************************************************
Unauthorized access is prohibited. All activity may be monitored.
***************************************************************************
EOF
fi

echo "==> Configuring fail2ban"
cat >/etc/fail2ban/jail.local <<EOF
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 3
backend = systemd
ignoreip = 127.0.0.1/8 ::1 ${LAN_CIDR}

[sshd]
enabled = true
port = ssh
filter = sshd
maxretry = 3
bantime = 86400
findtime = 600
EOF

systemctl enable fail2ban
systemctl restart fail2ban

echo "==> Configuring UFW (SSH only; 80/443 stay closed)"
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw limit 22/tcp comment 'SSH rate-limited (homelab-forge Phase 0)'
ufw deny 5050/tcp comment 'Block legacy pgAdmin if present'
ufw --force enable

echo "==> Validating sshd config"
sshd -t

echo "==> Reloading ssh"
systemctl reload ssh || systemctl restart ssh

echo
echo "==> Phase 0 host hardening applied"
echo "    sshd:   /etc/ssh/sshd_config.d/99-homelab-forge.conf"
echo "    ufw:    $(ufw status | head -1)"
echo "    fail2ban: $(systemctl is-active fail2ban)"
echo
echo "NEXT: verify key-only SSH (second session) and Cursor remote."
echo "Break-glass: physical console; restore from backups/phase0_*"
