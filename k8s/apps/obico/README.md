# Obico printer monitoring (ADR-016)

Operator runbook: [`docs/runbooks/obico.md`](../../../docs/runbooks/obico.md).

Argo CD Application `obico` renders the upstream Helm chart with
[`helm/values.yaml`](./helm/values.yaml) and syncs this directory (namespace,
quota, NetworkPolicies, ExternalSecrets). Do not `kubectl apply` it.
