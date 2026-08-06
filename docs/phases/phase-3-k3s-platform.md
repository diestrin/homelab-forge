# Phase 3 — k3s platform + ingress + Vault + Argo CD

**Goal:** Single-node k3s with Traefik on 80/443, Let’s Encrypt, Vault, Argo CD GitOps, storage on the data disk.

## Preconditions

- Phase 0 complete (firewall + monitoring + public SSH hardened + in-tree host-watch).
- WAN model locked: [ADR-003](../decisions/ADR-003-k3s-ingress.md) — direct port-forward + Let’s Encrypt.
- CD model locked: [ADR-008](../decisions/ADR-008-gitops-argocd.md) — Argo CD syncs `main`.
- Confirm **not behind CGNAT** (or have a working workaround) before relying on HTTP-01.
- Router ready to forward 80/443 to the NUC when enabling Ingress.

## Tasks

### 3.1 Install & layout

- [ ] Install k3s (pin version); write install flags into repo.
- [ ] Configure `local-path` (or Longhorn later) data root on `/media/diestrin/data/...`.
- [ ] kubeconfig for user `diestrin`; document `kubectl` via Nix.
- [ ] Validate coexistence with rootless Docker (ADR-003).

### 3.2 Ingress & TLS

- [ ] Confirm Traefik (or chosen ingress) owns host `:80` and `:443`.
- [ ] Open UFW for 80/443; reconcile with k3s; test that non-Ingress ports stay closed.
- [ ] Enable router port-forwards for 80/443 to NUC.
- [ ] Issue Let’s Encrypt cert for `localpower.diegobarahona.com` (or chosen alternate subdomain).
- [ ] Example `Ingress` for a hello-app in namespace `forge-demo` over HTTPS.
- [ ] Update in-tree host-watch allowlists for 80/443 and k3s components.

### 3.3 Platform namespaces

- [ ] `forge-system` — platform services (Vault, Argo CD, cert-manager if used, etc.).
- [ ] `forge-demo` — public demo workloads.
- [ ] `forge-agents` — optional job runners (no public ingress by default).
- [ ] Default-deny NetworkPolicies; ResourceQuotas/LimitRanges per namespace.

### 3.4 HashiCorp Vault (ADR-007)

- [ ] Deploy Vault to `forge-system` with data on the data disk.
- [ ] Document init/unseal/reboot procedure for single-node homelab.
- [ ] Create policies: platform, CI/deployer, agent AppRole (short-lived).
- [ ] Wire secret consumption (Vault Agent and/or External Secrets Operator — pick one).
- [ ] Migrate bootstrap secrets (ntfy, etc.) into Vault; remove plaintext copies.
- [ ] Ensure Vault UI/API is **not** anonymously public (SSH tunnel or authenticated Ingress).

### 3.5 Argo CD GitOps (ADR-008)

- [ ] Bootstrap Argo CD into `forge-system` (one-time apply); then hand ownership of platform apps to Argo where practical.
- [ ] Root Application (app-of-apps) pointing at this repo’s `k8s/` on branch **`main`**.
- [ ] Document sync policy: merge to `main` → Argo sync → cluster converge; no steady-state hand `kubectl apply` for managed apps.
- [ ] Repo credentials / deploy key from Vault; no tokens in git.
- [ ] Argo CD UI **not** anonymously public.
- [ ] Prove end-to-end: merge a trivial manifest change → appears on cluster without manual apply.
- [ ] Update host-watch allowlists if Argo components add new processes/listeners.

### 3.6 Observability (minimal)

- [ ] Cluster + node metrics (even if just `k3s` + a lightweight dashboard later).
- [ ] Ship critical alerts to ntfy (topic from Vault).

### 3.7 Manifest layout

- [ ] Keep manifests in `k8s/` with kustomize bases/overlays.
- [ ] Separate bootstrap (must apply once) from Argo-managed apps clearly in docs.

## Exit criteria

- [ ] `curl -I https://localpower.diegobarahona.com` (or chosen host) succeeds with valid LE cert.
- [ ] Random NodePort from a test Service is **not** reachable from WAN.
- [ ] Vault sealed/unsealed procedure tested across reboot (or auto-unseal documented).
- [ ] Argo CD syncs a change from `main` without manual kubectl for that app.
- [ ] Reboot test: cluster and ingress return (Vault unseal + Argo reconnect documented).
- [ ] Documented uninstall/reinstall notes for disaster recovery.

## Agent notes

- Do not enable WAN 80/443 until Phase 0 gates are done and you are ready to complete LE issuance in the same session window.
- Watch disk: container images + etcd + Vault storage belong on the data volume where possible.
- If UFW breaks cluster networking, fix via documented k3s+UFW pattern — don’t disable the firewall permanently.
- Public git: example Ingress/Vault/Argo values only; real tokens stay in Vault.
- Bootstrap order suggestion: k3s → Ingress/LE → Vault → Argo CD → migrate apps under Argo.
