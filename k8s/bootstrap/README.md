# k3s bootstrap (one-time)

These scripts are **not** managed by Argo CD. Run once (or for disaster recovery), then hand steady-state to Argo.

## Order

1. `./install-k3s.sh` — pin in [`VERSIONS.md`](./VERSIONS.md); data under `/media/diestrin/data/forge/k3s`.
2. Apply platform namespaces (or let Argo sync after Argo is up):  
   `kubectl apply -k ../platform/namespaces`
3. `./ufw-k3s.sh` — flannel/UFW rules + open 80/443 (**same session** as LE readiness).
4. Operator: enable router port-forward TCP 80/443 → NUC.
5. Install cert-manager / Vault / ESO / Argo per [`docs/runbooks/gitops.md`](../../docs/runbooks/gitops.md).
6. Apply root Application; thereafter merge to `main`.

## Uninstall / reinstall

```bash
# Destructive — removes cluster state under data-dir
sudo /usr/local/bin/k3s-uninstall.sh
# Data dir may remain; remove only if intentional:
# sudo rm -rf /media/diestrin/data/forge/k3s
./install-k3s.sh
./ufw-k3s.sh
# Restore Vault unseal keys from offline backup; re-apply bootstrap + Argo root app
```

## Coexistence

- Rootless Docker: L1/L4 sandboxes only.
- k3s: `containerd` under `--data-dir`.
- Do not run kind/minikube permanently on this host.
