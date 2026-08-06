# ADR-006: Hardened public SSH

## Status

Accepted (2026-08-06)

## Context

The MacBook Air reaches this NUC via Cursor over SSH. The operator wants SSH
reachable from the internet (not VPN-only), historically via No-IP DDNS to the
home IP and router port-forward to the NUC.

## Decision

1. Keep **public SSH** as the remote-dev entry path.
2. Require **key-only** authentication; disable password auth on any WAN-reachable listener.
3. `PermitRootLogin no` (or `prohibit-password` only if a short transition needs it — prefer `no`).
4. Firewall: allow SSH explicitly; rate-limit; fail2ban (or equivalent) mandatory.
5. Prefer a non-default forward target only if it reduces noise without breaking Cursor; document the actual port in private runbooks, not necessarily in the public README.
6. Break-glass: physical/LAN console access must remain available before tightening SSH.

## Consequences

- Phase 0 is non-negotiable before other exposure.
- host-watch + fail2ban are part of the baseline, not optional niceties.
- Portfolio narrative must include SSH hardening as a first-class control.
