# Security components

## host-watch

In-tree host IDS imported from the former sibling repo (ADR-005).

```bash
./security/scripts/install-host-watch.sh
```

Runtime config (ntfy URL, allowlists) lives under `~/.config/host-watch/` — not in git.
Bootstrap secrets: [`docs/runbooks/bootstrap-secrets.md`](../docs/runbooks/bootstrap-secrets.md).

## Phase 0 host hardening

Requires a real TTY + sudo (physical console break-glass available):

```bash
./security/scripts/apply-phase0-privileged.sh
```

This backs up sshd/UFW/fail2ban, applies key-only SSH (`99-homelab-forge.conf`),
enables UFW default-deny with `limit 22/tcp` (80/443 stay closed), starts fail2ban,
and enables user linger for host-watch.
