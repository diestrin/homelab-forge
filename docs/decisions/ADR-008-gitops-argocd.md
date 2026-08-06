# ADR-008: GitOps CD with Argo CD

## Status

Accepted (2026-08-06)

## Context

Cluster changes should land on the NUC when merges hit `main`, without manual
`kubectl apply` as the steady state. The factory already requires a review gate
before production-like deploys; GitOps makes `main` the deploy contract.

Alternatives considered: Flux CD (also excellent), raw Actions `kubectl` pushes
(weaker drift detection), exclusive manual apply (not portfolio-grade).

## Decision

1. Use **Argo CD** as the continuous delivery controller on k3s (`forge-system`).
2. **App-of-apps** (or equivalent root Application) watches this repo (and later app repos) and syncs desired state from **`main`**.
3. Deploy path:
   - PR → review/CI → merge to `main` → Argo CD syncs → cluster converges.
   - No silent agent deploys that bypass git/`main`.
4. Prefer **automated sync** for platform/demo apps once health checks exist; keep **manual sync** or sync windows for high-risk apps if needed initially.
5. Argo CD UI/API: **not** anonymously public — SSH tunnel, SSO later, or authenticated Ingress only.
6. Repo credentials / deploy keys: stored in Vault (ADR-007); bootstrap via sealed secret or one-time apply.
7. Manifests live under `k8s/` (kustomize bases/overlays). Argo Applications declare those paths.
8. Flux remains an acceptable substitute only if Argo CD proves too heavy on this NUC — default is Argo CD; document a swap ADR if replaced.

## Consequences

- Phase 3 must install Argo CD after (or with) core cluster networking; chicken-egg bootstrap: apply Argo CD once, then let it own the rest.
- Drift becomes visible; portfolio story includes real GitOps.
- Human/agent review still happens at PR time; Argo CD does not replace the review gate — it replaces hand-applying after merge.
- Public repo means Application manifests must not embed secrets (use External Secrets / Vault / sealed-secrets pattern).
