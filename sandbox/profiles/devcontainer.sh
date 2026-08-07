# L1 — rootless Docker / Devcontainer-style (project bind mount only).
# shellcheck shell=bash

profile_enter() {
  local project="$1"
  shift || true

  forge_require_cmd docker
  forge_ensure_layout
  forge_ensure_image
  forge_docker_limit_args
  forge_publish_args

  local name
  name="forge-dc-$(basename "$project")-$$"

  # Hard rules (ADR-002): no docker.sock, no $HOME bind, localhost publish only.
  local run_args=(
    --rm
    --name "$name"
    --hostname "$name"
    --security-opt=no-new-privileges
    --mount "type=bind,source=${project},target=/workspace"
    -w /workspace
    "${DOCKER_LIMIT_ARGS[@]}"
  )

  if [[ ${#DOCKER_PUBLISH_ARGS[@]} -gt 0 ]]; then
    run_args+=("${DOCKER_PUBLISH_ARGS[@]}")
  fi

  forge_info "profile=devcontainer (L1) image=$FORGE_IMAGE limits mem=${FORGE_MEM} cpus=${FORGE_CPUS} pids=${FORGE_PIDS}"
  forge_info "mount: $project -> /workspace (no docker.sock, no \$HOME)"

  if [[ $# -gt 0 ]]; then
    forge_docker run "${run_args[@]}" "$FORGE_IMAGE" "$@"
  else
    forge_docker run -it "${run_args[@]}" "$FORGE_IMAGE"
  fi
}
