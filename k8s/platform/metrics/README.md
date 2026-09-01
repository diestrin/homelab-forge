# Platform observability — Prometheus + Grafana + Loki

Observability stack for the homelab-forge k3s cluster: **kube-prometheus-stack**
(Prometheus Operator, Prometheus, Grafana, Alertmanager, kube-state-metrics,
node-exporter), **Loki** (log store) + **Grafana Alloy** (log shipper), plus
git-managed `PrometheusRule` alerts and Grafana provisioning.

Steady-state deploy: merge to `main` → Argo CD syncs Applications from
`k8s/overlays/root/applications.yaml` (ADR-008):

1. **`monitoring`** — kube-prometheus-stack Helm chart (installs operator CRDs).
2. **`loki`** — Grafana Loki Helm chart (monolithic, filesystem, 7-day retention).
3. **`alloy`** — Grafana Alloy DaemonSet that tails pod logs into Loki.
4. **`monitoring-manifests`** — `k8s/platform/metrics` kustomize overlay (rules, ingress,
   ExternalSecrets, dashboards, Loki datasource). Sync-wave 1 so PrometheusRules land
   after `monitoring.coreos.com/v1` exists.

Do **not** `kubectl apply` the Helm releases or metrics manifests by hand.
Loki and Alloy stay ClusterIP-only — do not add an Ingress.

## URLs

| Service | URL |
| --- | --- |
| Grafana | `https://grafana.localpower.diegobarahona.com` |
| Grafana Alerting | `https://grafana.localpower.diegobarahona.com/alerting/list` |
| Prometheus (in-cluster) | `http://monitoring-prometheus.monitoring.svc:9090` |
| Alertmanager (in-cluster) | `http://monitoring-alertmanager.monitoring.svc:9093` |
| Loki gateway (in-cluster) | `http://loki-gateway.monitoring.svc:80` |

Slack alert links use the **Grafana Alerting** URL (public Ingress). Prometheus,
Alertmanager, and Loki stay ClusterIP-only — do not expose them.

Explore logs in Grafana → **Explore** → datasource **Loki** (label filters such as
`{namespace="family-agile"}` or `{pod=~"vault.*"}`).

Grafana login uses the admin password from Vault (`secret/forge/grafana`). Username
defaults to `admin` unless overridden in Vault.

## Vault bootstrap (operator)

Run after Vault is unsealed. Placeholders only — never commit real values.

```bash
export VAULT_ADDR=http://127.0.0.1:8200   # via port-forward if needed

# Existing ntfy topic (shared with host-watch pattern)
vault kv put secret/forge/ntfy url='https://ntfy.example.com/your-topic-placeholder'

# Slack Incoming Webhook for dedicated ops channel (#forge-alerts)
vault kv put secret/forge/alerts/slack \
  webhook_url='https://hooks.slack.com/services/PLACEHOLDER/PLACEHOLDER/PLACEHOLDER'

# Grafana admin credentials
vault kv put secret/forge/grafana \
  admin_user=admin \
  admin_password="$(openssl rand -base64 24)"
```

Confirm ExternalSecrets sync:

```bash
kubectl -n monitoring get externalsecret alertmanager-notifications grafana-admin
kubectl -n monitoring get secret grafana-admin alertmanager-notifications
```

`alertmanager-notifications` merges ntfy and Slack webhook keys from Vault in one
ExternalSecret. Until the Slack webhook path is set, Alertmanager still delivers ntfy;
the Slack leg is skipped when `slack_webhook_url` is empty.

## Resource budget (single-node NUC)

Approximate incremental footprint after sync:

| Component | Requests (CPU / RAM) |
| --- | --- |
| Prometheus | 100m / 512Mi |
| Grafana | 100m / 256Mi |
| Alertmanager | 25m / 64Mi |
| Operator + exporters | ~100m / ~160Mi |
| Loki (single binary) | 100m / 256Mi |
| Loki gateway | 25m / 32Mi |
| Alloy (DaemonSet) | 25m / 64Mi |
| **Total (requests)** | **~475m / ~1.3Gi** |

Prometheus PVC: 10Gi (`local-path`). Grafana PVC: 2Gi. Loki PVC: 10Gi. Metrics and
logs both retain **7 days**.

On single-node k3s, **node-exporter** uses pod networking (not `hostNetwork`) so Prometheus
scrapes a pod IP instead of the node LAN IP (same-node hairpin breaks). **Kubelet**
ServiceMonitor is disabled for the same reason; host/container CPU and memory come from
node-exporter and kube-state-metrics.

## Dashboard tour (portfolio)

Three dashboard layers for demos:

1. **Kubernetes / Compute Resources / Cluster** — chart default; cluster-wide CPU/memory
   and pod counts.
2. **Node Exporter / Nodes** — chart default; per-node CPU, memory, disk, network from
   node-exporter.
3. **Forge Overview** (`forge-overview`) — custom dashboard in `dashboards/forge-overview.json`:
   node Ready count, host memory %, Argo CD app health table, workload Running ratio,
   Vault ready replicas.

Open Grafana → Dashboards → browse folders. Refresh interval 30s on Forge Overview.

## Logs (Loki)

Loki runs as a **single replica** (filesystem store, no MinIO, no memcached caches)
sized for this NUC. Compactor retention is **168h**; `max_query_lookback` matches so
Explore cannot query older than a week.

Alloy is a DaemonSet (pod networking, not `hostNetwork`). It keeps only the local
node's pods via `HOSTNAME` = `spec.nodeName`, tails through the Kubernetes API
(`loki.source.kubernetes`), and pushes to `loki-gateway`.

## Alerts (PrometheusRule A1–A8)

Rules live in `rules/forge-alerts.yaml`. Labels include `forge_alert_id` and
`severity` for Alertmanager routing.

| ID | Alert | Severity | `for` |
| --- | --- | --- | --- |
| A1 | Node NotReady | critical | 5m |
| A2 | Node pressure (memory/disk/PID) | critical | 5m |
| A3 | Node memory >85% or CPU >90% | warning | 10m |
| A4 | Argo app Degraded/Missing/Unknown | critical | 15m |
| A5 | Argo app OutOfSync | warning | 30m |
| A6 | CrashLoopBackOff / ImagePullBackOff | warning | 10m |
| A7 | Deployment replicas unavailable | warning | 15m |
| A8 | Vault deployment not ready | critical | 5m |

Routing (Alertmanager):

- **critical** → ntfy + Slack `#forge-alerts`
- **warning** → ntfy + Slack
- **info** → ntfy only

Slack messages include status/severity in the title, the alert **description** (not
summary-only), key labels (ns/pod/job/…), optional runbook link, and a button/title
link to Grafana Alerting. Chart default rules that cannot scrape on single-node k3s
(`KubeletDown`, `KubeSchedulerDown`, and related) are disabled.

Factory task-thread Slack (TASK-011) is separate; this stack uses an Incoming Webhook.

Explore firing alerts: Grafana → Alerting → Alert rules (or Prometheus UI via
port-forward).

## Operator smoke test (post-merge)

1. **Sync health**

   ```bash
   kubectl -n forge-system get application monitoring loki alloy monitoring-manifests
   kubectl -n monitoring get pods
   kubectl -n monitoring get prometheus,alertmanager
   ```

   Expect those Applications `Synced`/`Healthy`; Loki, Alloy, and core metrics pods `Running`.

2. **Grafana HTTPS**

   ```bash
   curl -fsSI https://grafana.localpower.diegobarahona.com | head -3
   ```

   Log in with Vault-sourced admin password; confirm three dashboard layers above.

3. **Prometheus targets**

   Port-forward Prometheus and check `/targets` includes `kube-state-metrics`,
   `node-exporter`, and `argocd-*` ServiceMonitors.

4. **Safe alert trigger (A6)**

   Create a throwaway CrashLoop pod in `forge-agents` (never commit):

   ```bash
   kubectl -n forge-agents run alert-smoke --image=busybox --restart=Never \
     --command -- sh -c 'exit 1'
   ```

   Wait ~10–15 minutes (rule `for: 10m` + Alertmanager group wait). Expect
   `ForgePodCrashLooping` in Grafana/Prometheus and notifications on ntfy + Slack.

   Clean up:

   ```bash
   kubectl -n forge-agents delete pod alert-smoke --ignore-not-found
   ```

5. **Verify Argo metrics**

   In Prometheus, query `argocd_app_info` — series must exist for A4/A5 to work.

6. **Log round-trip**

   In Grafana Explore, datasource Loki, query `{namespace="monitoring"}` over the last
   15 minutes. Expect lines from Grafana/Prometheus/Loki pods. A missing datasource
   usually means the Grafana sidecar has not picked up `grafana-datasource-loki` yet
   (`kubectl -n monitoring rollout restart deploy/monitoring-grafana`).

## Maintenance silences

During planned work, silence alerts in Grafana (Alerting → Silences) or with
`amtool` against the in-cluster Alertmanager service. Remove silences after maintenance.

## Layout

```text
k8s/platform/metrics/
├── helm/kube-prometheus-stack-values.yaml   # Helm values (Argo $values ref)
├── helm/loki-values.yaml                    # Loki monolithic + 7d retention
├── helm/alloy-values.yaml                   # Alloy DaemonSet log shipper
├── rules/forge-alerts.yaml                  # PrometheusRule A1–A8
├── dashboards/forge-overview.json           # Provisioned via ConfigMap label
├── grafana-ingress.yaml                     # HTTPS via cert-manager + Traefik
├── grafana-datasource-loki.yaml             # Grafana sidecar Loki datasource
├── externalsecret-*.yaml                    # Vault → Grafana + Alertmanager secrets
└── kustomization.yaml
```

Helm releases: Applications `monitoring`, `loki`, and `alloy`. Git-managed
rules/ingress/secrets/datasource: Application `monitoring-manifests`. All four are
declared in `k8s/overlays/root/applications.yaml`.

## Related

- [factory/plans/TASK-012.md](../../../factory/plans/TASK-012.md) — design and acceptance
- [docs/runbooks/operations.md](../../../docs/runbooks/operations.md) — cold-start checks
- [docs/runbooks/vault.md](../../../docs/runbooks/vault.md) — Vault / ESO
