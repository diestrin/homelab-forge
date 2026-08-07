# L3 — k3s workload profile (Phase 3).
# shellcheck shell=bash

profile_enter() {
  local project="$1"
  shift || true

  cat >&2 <<EOF
forge: profile=k8s-workload is reserved for Phase 3 (k3s + NetworkPolicy + ResourceQuota).

  Project: $project
  Planned namespace patterns: forge-demo / forge-agents (see docs/phases/phase-3-k3s-platform.md)
  Until then use: trusted | devcontainer | agent-cell | incus

EOF
  exit 1
}
