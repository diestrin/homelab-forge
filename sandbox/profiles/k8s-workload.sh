# L3 — deploy/run a project as a k3s workload (Phase 3).
# shellcheck shell=bash

profile_enter() {
  local project="$1"
  shift || true

  forge_require_cmd kubectl

  local ns="${FORGE_K8S_NAMESPACE:-forge-agents}"
  local kubeconfig="${KUBECONFIG:-$HOME/.kube/config}"
  [[ -f "$kubeconfig" ]] || forge_die "missing kubeconfig at $kubeconfig (run k8s/bootstrap/install-k3s.sh)"

  export KUBECONFIG="$kubeconfig"

  if ! kubectl cluster-info >/dev/null 2>&1; then
    forge_die "kubectl cannot reach cluster — is k3s running?"
  fi

  kubectl get ns "$ns" >/dev/null 2>&1 || forge_die "namespace $ns missing (apply k8s/platform/namespaces)"

  local manifest=""
  if [[ -f "$project/k8s/kustomization.yaml" ]]; then
    manifest="kustomize:$project/k8s"
  elif [[ -d "$project/k8s" ]]; then
    manifest="dir:$project/k8s"
  elif [[ -f "$project/kustomization.yaml" ]]; then
    manifest="kustomize:$project"
  fi

  if [[ $# -gt 0 ]]; then
    # Explicit command (e.g. kubectl …) with project as cwd context
    (cd "$project" && "$@")
    return
  fi

  if [[ -n "$manifest" ]]; then
    forge_info "Applying manifests to namespace $ns ($manifest)"
    case "$manifest" in
      kustomize:*)
        kubectl apply -k "${manifest#kustomize:}" -n "$ns"
        ;;
      dir:*)
        kubectl apply -f "${manifest#dir:}" -n "$ns"
        ;;
    esac
    kubectl -n "$ns" get pods,svc,ingress
    return
  fi

  cat <<EOF
forge: profile=k8s-workload (L3)

  Project:   $project
  Namespace: $ns (override with FORGE_K8S_NAMESPACE)
  Cluster:   $(kubectl config current-context 2>/dev/null || echo unknown)

No k8s/ manifests found under the project.
Options:
  • Add $project/k8s/ (Deployment + optional Ingress) then re-run
  • Or: forge sandbox enter <project> --profile k8s-workload -- kubectl -n $ns get pods

Public exposure only via Ingress in forge-demo (not forge-agents by default).
EOF
}
