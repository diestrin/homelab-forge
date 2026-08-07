# Phase 3 — k3s platform + ingress + Vault + Argo CD

**Goal:** Single-node k3s with Traefik on 80/443, Let’s Encrypt, Vault, Argo CD GitOps, storage on the data disk.

**Status:** Complete (2026-08-07) — picks: **cert-manager** + **External Secrets Operator**.

## Preconditions

- Phase 0 complete (firewall + monitoring + public SSH hardened + in-tree host-watch).
- WAN model locked: [ADR-003](../decisions/ADR-003-k3s-ingress.md) — direct port-forward + Let’s Encrypt.
- CD model locked: [ADR-008](../decisions/ADR-008-gitops-argocd.md) — Argo CD syncs `main`.
- Confirm **not behind CGNAT** (or have a working workaround) before relying on HTTP-01.
- Router ready to forward 80/443 to the NUC when enabling Ingress.

## Tasks

### 3.1 Install & layout

- [x] Install k3s (pin version); write install flags into repo.
- [x] Configure `local-path` (or Longhorn later) data root on `/media/diestrin/data/...`.
- [x] kubeconfig for user `diestrin`; document `kubectl` via Nix.
- [x] Validate coexistence with rootless Docker (ADR-003).

### 3.2 Ingress & TLS

- [x] Confirm Traefik (or chosen ingress) owns host `:80` and `:443`.
- [x] Open UFW for 80/443; reconcile with k3s; test that non-Ingress ports stay closed.
- [x] Enable router port-forwards for 80/443 to NUC.
- [x] Issue Let’s Encrypt cert for `localpower.diegobarahona.com` (or chosen alternate subdomain).
- [x] Example `Ingress` for a hello-app in namespace `forge-demo` over HTTPS.
- [x] Update in-tree host-watch allowlists for 80/443 and k3s components.

### 3.3 Platform namespaces

- [x] `forge-system` — platform services (Vault, Argo CD, cert-manager if used, etc.).
- [x] `forge-demo` — public demo workloads.
- [x] `forge-agents` — optional job runners (no public ingress by default).
- [x] Default-deny NetworkPolicies; ResourceQuotas/LimitRanges per namespace.

### 3.4 HashiCorp Vault (ADR-007)

- [x] Deploy Vault to `forge-system` with data on the data disk.
- [x] Document init/unseal/reboot procedure for single-node homelab.
- [x] Create policies: platform, CI/deployer, agent AppRole (short-lived).
- [x] Wire secret consumption (External Secrets Operator).
- [x] Migrate bootstrap secrets (ntfy, etc.) into Vault; remove plaintext copies.
- [x] Ensure Vault UI/API is **not** anonymously public (SSH tunnel or authenticated Ingress).

### 3.5 Argo CD GitOps (ADR-008)

- [x] Bootstrap Argo CD into `forge-system` (one-time apply); then hand ownership of platform apps to Argo where practical.
- [x] Root Application (app-of-apps) pointing at this repo’s `k8s/` on branch **`main`**.
- [x] Document sync policy: merge to `main` → Argo sync → cluster converge; no steady-state hand `kubectl apply` for managed apps.
- [x] Repo credentials / deploy key from Vault; no tokens in git. (public repo — anonymous clone)
- [x] Argo CD UI **not** anonymously public.
- [x] Prove end-to-end: merge a trivial manifest change → appears on cluster without manual apply.
- [x] Update host-watch allowlists if Argo components add new processes/listeners.

### 3.6 Observability (minimal)

- [x] Cluster + node metrics (even if just `k3s` + a lightweight dashboard later).
- [x] Ship critical alerts to ntfy (topic from Vault).

### 3.7 Manifest layout

- [x] Keep manifests in `k8s/` with kustomize bases/overlays.
- [x] Separate bootstrap (must apply once) from Argo-managed apps clearly in docs.

## Exit criteria

- [x] `curl -I https://localpower.diegobarahona.com` (or chosen host) succeeds with valid LE cert.
- [x] Random NodePort from a test Service is **not** reachable from WAN.
- [x] Vault sealed/unsealed procedure tested across reboot (or auto-unseal documented).
- [x] Argo CD syncs a change from `main` without manual kubectl for that app.
- [x] Reboot test: cluster and ingress return (Vault unseal + Argo reconnect documented).
- [x] Documented uninstall/reinstall notes for disaster recovery.

## Agent notes

- Do not enable WAN 80/443 until Phase 0 gates are done and you are ready to complete LE issuance in the same session window.
- Watch disk: container images + etcd + Vault storage belong on the data volume where possible.
- If UFW breaks cluster networking, fix via documented k3s+UFW pattern — don’t disable the firewall permanently.
- Public git: example Ingress/Vault/Argo values only; real tokens stay in Vault.
- Bootstrap order suggestion: k3s → Ingress/LE → Vault → Argo CD → migrate apps under Argo.
