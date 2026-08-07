# ADR-003: k3s + Traefik ingress on 80/443

## Status

Accepted (2026-08-06)

## Context

Need local Kubernetes suitable for a home server, with public HTTP(S) on 80/443.
Host has rootless Docker today; RAM/CPU are ample (62 GiB / 12 threads).
Home WAN path: No-IP DDNS → home public IP → router port-forward → NUC.
Preferred public hostname: `localpower.diegobarahona.com` (or another subdomain
under the same zone if that name must stay SSH-only / No-IP-shaped).

## Decision

1. Install **k3s** (single-node initially) with:
   - Embedded **Traefik** ingress (default) unless Cilium/Gateway API is chosen later.
   - `local-path` storage pointing at a directory on `/media/diestrin/data/...`.
   - Disable components not needed (e.g. local ServiceLB if MetalLB/Traefik host ports suffice).
2. Bind host ports **80/443** exclusively via k3s/Traefik (or a thin host reverse proxy in front). Do not also bind host nginx/caddy on those ports.
3. **WAN model:** router **direct port-forward** of TCP 80 and 443 to the NUC. No Cloudflare Tunnel / Tailscale Funnel for v1.
4. **TLS:** **Let’s Encrypt** via ACME (HTTP-01 is acceptable once 80 is forwarded; DNS-01 if HTTP-01 is impractical). **Phase 3 pick: cert-manager** + Traefik Ingress (`ClusterIssuer` `letsencrypt-prod`).
5. **Hostname:** prefer `localpower.diegobarahona.com` for HTTPS apps if DNS can point that name at the No-IP target (CNAME/ALIAS) **or** serve HTTPS on that name while keeping A/AAAA via No-IP. If the apex/name conflicts with SSH-only expectations, use e.g. `forge.diegobarahona.com` / `*.localpower.diegobarahona.com` and document the split.
6. Coexistence with Docker:
   - Short term: keep rootless Docker for L1 sandboxes; k3s uses `containerd`.
   - Document IP ranges / iptables interaction; prefer **not** running a second cluster-ish runtime (minikube/kind) permanently.
7. Expose only Ingress-selected Services publicly; all other NodePorts/hostPorts denied by default firewall policy.
8. Do not open WAN 80/443 until Phase 0 security gates pass and cert issuance is ready.

## Consequences

- k3s is the right size for a NUC and looks professional in a portfolio.
- Must reconcile firewall (UFW) with k3s iptables/nft — known footgun; Phase 3 must test carefully.
- Rootless Docker + k3s is workable if responsibilities stay split (dev vs serve).
- Operator must maintain No-IP + router forwards; ISP CGNAT would block this model (verify before Phase 3).
- HTTP-01 requires port 80 reachable from the public internet during issuance/renewal.
