# Deprecated: task YAML ConfigMap mirror (pre–ADR-010)

Task runtime state now lives in Postgres (`k8s/platform/postgres/`). The forge-site
dashboard reads the control plane API. These files are kept only as historical reference;
`kustomization.yaml` no longer mounts them.

To refresh an optional git mirror from the API:

```bash
./forge factory export-yaml
```
