# Object storage (Garage)

S3-compatible file sharing for family, friends, and forge workloads (ADR-015).
One Garage node, two HTTPS names, path-style requests.

| Who | URL |
| --- | --- |
| Internet (family, friends, you away from home) | `https://s3.localpower.diegobarahona.com` |
| Home LAN | `https://s3.lan.localpower.diegobarahona.com` |
| Pods in the cluster | `http://garage.storage.svc:3900` |

Region for every client: `garage`. Path-style addressing (not virtual-host).
A presigned URL works only on the hostname it was signed against.

Data lives on the data disk at `/media/diestrin/data/forge/storage`. There is
no second copy. Do not use this as the only copy of something you cannot lose.

## Before merge

1. DNS. Both names must resolve on the public internet to the home WAN address
   so Let's Encrypt HTTP-01 can run. On the LAN resolver, also point
   `s3.lan.localpower.diegobarahona.com` at the forge host so LAN clients stay
   on the LAN. Do not commit that address.
2. Vault (after unseal). Generate the two server secrets locally and load them.
   Do not paste them into git, issues, or chat logs.

```bash
vault kv put secret/forge/garage \
  rpc_secret="$(openssl rand -hex 32)" \
  admin_token="$(openssl rand -base64 32)"
```

`rpc_secret` is fixed for the life of the metadata directory. Replacing it
later makes the node unable to read its own layout.

## Deploy

Merge to `main`. Argo CD Application `storage` syncs `k8s/apps/storage/`.
Do not `kubectl apply` it.

```bash
kubectl -n forge-system get application storage
kubectl -n storage get pods,ingress,certificate
```

Expect `garage` Ready, and both certificates Ready once DNS answers.

## Keys and a shared bucket

Admin API listens on `127.0.0.1:3903` inside the pod. Create one key per
person. Store the secret in Vault; Garage will not show it again.

```bash
kubectl -n storage exec deploy/garage -- /garage key create family-diego
kubectl -n storage exec deploy/garage -- /garage bucket create family
kubectl -n storage exec deploy/garage -- /garage bucket allow \
  --read --write --owner family --key family-diego
```

Repeat `key create` + `bucket allow` for each person. Drop `--owner` on later
keys if they should not administer the bucket. Then:

```bash
vault kv patch secret/forge/garage \
  family_diego_access_key='GK…' \
  family_diego_secret_key='…'
```

Hand someone their key out of band. They should not get the admin token or
the RPC secret.

## Clients

rclone remote (public; swap the endpoint for the LAN name when at home):

```text
[family]
type = s3
provider = Other
access_key_id = <their key>
secret_access_key = <their secret>
endpoint = https://s3.localpower.diegobarahona.com
region = garage
force_path_style = true
```

Cyberduck and Mountain Duck: S3 profile, the same endpoint, path-style,
region `garage`.

Share one object without giving out a key (public endpoint, expires in one
day):

```bash
aws --endpoint-url https://s3.localpower.diegobarahona.com \
  s3 presign s3://family/some-file --region garage --expires-in 86400
```

That URL is reachable from the internet. A LAN-signed URL is not, unless the
recipient is on the LAN and uses the LAN hostname.

## Firewall and host-watch

No new host bind and no UFW change. Traefik still owns 80/443. The admin port
is not on an Ingress.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| Pod `CreateContainerConfigError` | Vault `secret/forge/garage` missing `rpc_secret` or `admin_token`; ESO `garage-secrets` |
| Public cert `False` | DNS for `s3.localpower.diegobarahona.com`; HTTP-01 on port 80 |
| LAN cert `False` | Public DNS for `s3.lan.localpower.diegobarahona.com` must also reach this host for issuance |
| LAN URL slow or fails at home | LAN resolver still sends that name to the WAN address; add the split-horizon record |
| `AuthorizationHeaderMalformed` | Client region is not `garage`, or path-style is off |
| Presigned link 403 from another network | Link was signed for the other hostname |
| Garage refuses to start after a secret change | `rpc_secret` no longer matches the metadata dir; restore the original value |

## Related

- [gitops.md](./gitops.md) — merge → Argo.
- [vault.md](./vault.md) — unseal, ESO.
- [network-exposure.md](./network-exposure.md) — WAN 80/443.
