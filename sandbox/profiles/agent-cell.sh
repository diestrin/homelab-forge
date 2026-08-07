# L4 — ephemeral agent task cell (L1 base + stricter isolation).
# shellcheck shell=bash

profile_enter() {
  local project="$1"
  shift || true

  forge_require_cmd docker
  forge_ensure_layout
  forge_ensure_image
  forge_docker_limit_args
  forge_publish_args

  local cell_id
  cell_id="$(date +%Y%m%d%H%M%S)-$$"
  local cell_dir="$FORGE_DATA_ROOT/agent-cells/$cell_id"
  local workspace="$cell_dir/workspace"
  mkdir -p "$workspace"
  chmod 700 "$cell_dir"
  printf '%s\n' "$project" >"$cell_dir/project.origin"
  printf '%s\n' "$workspace" >"$cell_dir/agent-workspace.path"

  local name="forge-cell-$cell_id"
  local mount_opts="type=bind,source=${project},target=/workspace"
  if [[ "${FORGE_AGENT_RW:-true}" != "true" ]]; then
    mount_opts+=",readonly"
  fi

  local run_args=(
    --rm
    --name "$name"
    --hostname "$name"
    --security-opt=no-new-privileges
    --mount "$mount_opts"
    -w /workspace
    -e "FORGE_CELL_ID=$cell_id"
    -e "FORGE_AGENT_WORKSPACE=$workspace"
    "${DOCKER_LIMIT_ARGS[@]}"
  )

  if [[ ${#DOCKER_PUBLISH_ARGS[@]} -gt 0 ]]; then
    run_args+=("${DOCKER_PUBLISH_ARGS[@]}")
  fi

  forge_info "profile=agent-cell (L4) cell=$cell_id"
  forge_info "project mount only: $project -> /workspace"
  forge_info "agent workspace marker (host): $workspace"
  forge_info "docker.sock: not mounted; \$HOME / Projects tree: not mounted"

  {
    echo "id=$cell_id"
    echo "project=$project"
    echo "started=$(date -Is)"
    echo "image=$FORGE_IMAGE"
  } >"$cell_dir/meta.env"

  if [[ $# -gt 0 ]]; then
    forge_docker run "${run_args[@]}" "$FORGE_IMAGE" "$@"
  else
    forge_docker run -it "${run_args[@]}" "$FORGE_IMAGE"
  fi
}
