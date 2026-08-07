# Network exposure (Phase 0)

Public, redacted runbook. Home IPs and router UI details live in the private
bootstrap inventory (outside git): `/media/diestrin/data/secrets/bootstrap/inventory.private.md`.

## Uplink

| Interface | Role (Phase 0) |
| --- | --- |
| `wlp0s20f3` (Wi-Fi) | **Active default** uplink |
| `eno1` (ethernet) | Present but unused; optional future reliability hardening |

## Intended WAN path

```text
Internet → DDNS hostname → home router port-forward → NUC
```

- Preferred app/SSH hostname: `localpower.diegobarahona.com`
- DNS resolves via a CNAME to an operator-controlled DDNS name, then to the home
  public A record (verified at Phase 0; not CGNAT for this path).
- Historical note: router may forward a non-default external SSH port to NUC `:22`.
  Confirm in the router UI; do not publish the external port mapping in this file.

## Public ports

| Port | Phase 0 | Later |
| --- | --- | --- |
| SSH (`22` on host) | **Allowed** (UFW rate-limit + fail2ban) | Keep hardened |
| `80` / `443` | Open with Traefik (Phase 3) | UFW allow + router port-forward; LE HTTP-01 |

Open 80/443 only when Traefik is ready to serve ACME in the same session (`k8s/bootstrap/ufw-k3s.sh`).

## Controls

- SSH: key-only (`PasswordAuthentication no`), `PermitRootLogin no`, `AllowUsers` set — ADR-006.
- Firewall: UFW default-deny inbound; `ufw limit 22/tcp`.
- IDS: in-tree `security/host-watch/` user timer + ntfy (topic outside git).

## Operator checks

```bash
ss -tlnp | grep -E ':22|:80|:443'
sudo ufw status verbose
sudo fail2ban-client status sshd
dig +short localpower.diegobarahona.com
```
