# ADR-015: S3-compatible object storage (Garage)

- Status: Accepted
- Date: 2026-09-24
- Related: ADR-003 (k3s / Traefik / Let's Encrypt), ADR-007 (Vault), ADR-008
  (GitOps)

## Context

Family and friends need a place to exchange files, and forge workloads need an
S3 API. The operator wants two URLs for the same store:

- a public HTTPS URL, reachable from the internet over the existing
  Traefik + Let's Encrypt path
- an internal HTTPS URL, used from the home LAN so clients do not hairpin
  out through the router

Constraints: single NUC, data on `/media/diestrin/data`, no secrets in git,
no new host listeners, no UFW changes.

## Decision

1. **Store: Garage** (`dxflrs/garage`), single node, `replication_factor = 1`,
   metadata on Sqlite. MinIO is rejected because current community builds no
   longer ship a console, and a single `MINIO_SERVER_URL` rewrites presigned
   links onto one host. Garage accepts path-style SigV4 on whatever `Host`
   reached it, so two ingress hostnames are both valid endpoints.
2. **URLs.**
   - Public: `https://s3.localpower.diegobarahona.com`
   - LAN: `https://s3.lan.localpower.diegobarahona.com`
   - In-cluster (not a third public name): `http://garage.storage.svc:3900`
   Path-style only. No vhost `root_domain`, so no wildcard DNS or certificate.
3. **GitOps.** Manifests under `k8s/apps/storage/`. Merge to `main` → Argo CD
   Application `storage` syncs (ADR-008). Admin API and RPC stay on the pod;
   only the S3 port is reachable from Traefik.
4. **Storage.** hostPath `/media/diestrin/data/forge/storage` on the data disk
   (metadata and objects). Same pattern as the media library (ADR-014).
5. **Secrets.** `rpc_secret` and `admin_token` live in Vault
   `secret/forge/garage` and are injected with an ExternalSecret (ADR-007).
   Per-person S3 keys are created with the `garage` CLI after boot and stored
   in that same Vault path. Nothing is anonymous by default.
6. **LAN DNS.** Public DNS for both names points at the home WAN address so
   HTTP-01 can issue certificates. The LAN resolver additionally maps only
   `s3.lan.localpower.diegobarahona.com` to the forge host. The LAN address
   stays out of git.

## Consequences

- A presigned URL is bound to the host it was signed for. Links shared with
  people off-site must use the public hostname. LAN clients configure the
  LAN hostname as their endpoint.
- One disk, one node: a dead host or a full data disk takes the store down.
  This is file sharing, not a backup target.
- Family members use an S3 client (rclone, Cyberduck, `aws` CLI) or a
  presigned URL. There is no web file browser in this decision.
- host-watch sees no new host listener. Traefik still owns 80/443.

## Alternatives considered

- **MinIO.** Familiar console and share links, but one configured server URL
  fights the two-endpoint requirement, and the community image no longer
  includes the console.
- **SeaweedFS / Ceph.** More machinery than a single-node share needs.
- **Nextcloud.** Better for non-technical browsing, and not an S3 API.
