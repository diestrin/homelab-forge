# Docker hygiene

Rootless Docker is present on this host. Public exposure must not come from
container `-p 0.0.0.0:...` publishes.

## Rules

1. Bind local services to `127.0.0.1` (or omit publish and use `docker exec` / SSH tunnels).
2. Public HTTP(S) only via future k3s Ingress (Phase 3) — not ad-hoc Docker publishes.
3. Prefer pruning unused images/containers after confirming nothing depends on them.

## Audit commands

```bash
docker ps -a --format 'table {{.Names}}\t{{.Status}}\t{{.Ports}}'
docker image ls
ss -tlnp | grep -i docker || true
```

Phase 0 audit: only a stopped test container; no published host ports.
