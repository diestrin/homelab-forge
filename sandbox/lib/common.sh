# Shared helpers for forge sandbox profiles.
# shellcheck shell=bash

FORGE_DATA_ROOT="${FORGE_DATA_ROOT:-/media/diestrin/data/forge}"
FORGE_PROJECTS_ROOT="${FORGE_PROJECTS_ROOT:-/media/diestrin/data/Projects}"
FORGE_SECRETS_ROOT="${FORGE_SECRETS_ROOT:-/media/diestrin/data/secrets}"
FORGE_IMAGE="${FORGE_IMAGE:-forge-devcontainer:phase2}"

# Repo root: sandbox/lib -> sandbox -> repo
FORGE_REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

forge_die() {
  echo "forge: $*" >&2
  exit 1
}

forge_info() {
  echo "==> $*"
}

forge_require_cmd() {
  command -v "$1" >/dev/null 2>&1 || forge_die "missing required command: $1"
}

# Resolve a project argument to an absolute directory under Projects (or absolute path).
# Accepts: absolute path, relative path, or bare name under FORGE_PROJECTS_ROOT.
forge_resolve_project() {
  local arg="${1:-}"
  local candidate

  [[ -n "$arg" ]] || forge_die "project path or name required"

  if [[ "$arg" == /* ]]; then
    candidate="$arg"
  elif [[ -d "$arg" ]]; then
    candidate="$(cd "$arg" && pwd)"
  elif [[ -d "$FORGE_PROJECTS_ROOT/$arg" ]]; then
    candidate="$FORGE_PROJECTS_ROOT/$arg"
  elif [[ -d "$FORGE_REPO_ROOT/$arg" ]]; then
    candidate="$(cd "$FORGE_REPO_ROOT/$arg" && pwd)"
  else
    forge_die "project not found: $arg (looked under $FORGE_PROJECTS_ROOT and cwd)"
  fi

  [[ -d "$candidate" ]] || forge_die "not a directory: $candidate"
  # Prefer realpath when available for canonical form.
  if command -v realpath >/dev/null 2>&1; then
    realpath "$candidate"
  else
    cd "$candidate" && pwd
  fi
}

forge_ensure_layout() {
  mkdir -p \
    "$FORGE_DATA_ROOT/state" \
    "$FORGE_DATA_ROOT/volumes" \
    "$FORGE_DATA_ROOT/agent-cells" \
    "$FORGE_DATA_ROOT/images" \
    "$FORGE_DATA_ROOT/workspaces"
  chmod 700 "$FORGE_DATA_ROOT" "$FORGE_DATA_ROOT/agent-cells" "$FORGE_DATA_ROOT/state"
  chmod 755 "$FORGE_DATA_ROOT/volumes" "$FORGE_DATA_ROOT/images" "$FORGE_DATA_ROOT/workspaces"

  if [[ -d "$FORGE_SECRETS_ROOT" ]]; then
    chmod 700 "$FORGE_SECRETS_ROOT" 2>/dev/null || true
  else
    forge_info "secrets root missing at $FORGE_SECRETS_ROOT (create outside git; see docs/runbooks/bootstrap-secrets.md)"
  fi
}

forge_docker() {
  # Prefer rootless context when present (ADR-002 L1).
  if docker context ls --format '{{.Name}} {{.Current}}' 2>/dev/null | grep -q '^rootless true$'; then
    docker "$@"
  elif [[ -S /run/user/"$(id -u)"/docker.sock ]]; then
    DOCKER_HOST="unix:///run/user/$(id -u)/docker.sock" docker "$@"
  else
    docker "$@"
  fi
}

forge_default_limits() {
  # Exports FORGE_MEM / FORGE_CPUS / FORGE_PIDS for the active profile.
  case "${FORGE_PROFILE:-trusted}" in
    trusted)
      FORGE_MEM=""; FORGE_CPUS=""; FORGE_PIDS=""
      ;;
    devcontainer)
      FORGE_MEM="${FORGE_MEM:-4g}"
      FORGE_CPUS="${FORGE_CPUS:-2}"
      FORGE_PIDS="${FORGE_PIDS:-2048}"
      ;;
    agent-cell)
      FORGE_MEM="${FORGE_MEM:-2g}"
      FORGE_CPUS="${FORGE_CPUS:-1}"
      FORGE_PIDS="${FORGE_PIDS:-1024}"
      ;;
    incus)
      FORGE_MEM="${FORGE_MEM:-4GiB}"
      FORGE_CPUS="${FORGE_CPUS:-2}"
      FORGE_PIDS="${FORGE_PIDS:-2048}"
      ;;
    k8s-workload)
      FORGE_MEM="${FORGE_MEM:-512Mi}"
      FORGE_CPUS="${FORGE_CPUS:-500m}"
      FORGE_PIDS=""
      ;;
    *)
      forge_die "unknown profile for limits: $FORGE_PROFILE"
      ;;
  esac
  export FORGE_MEM FORGE_CPUS FORGE_PIDS
}

forge_docker_limit_args() {
  forge_default_limits
  local args=()
  [[ -n "${FORGE_MEM:-}" ]] && args+=(--memory="$FORGE_MEM")
  [[ -n "${FORGE_CPUS:-}" ]] && args+=(--cpus="$FORGE_CPUS")
  [[ -n "${FORGE_PIDS:-}" ]] && args+=(--pids-limit="$FORGE_PIDS")
  # shellcheck disable=SC2206
  DOCKER_LIMIT_ARGS=("${args[@]}")
}

forge_publish_args() {
  # Inbound localhost-only. Opt-in via FORGE_PUBLISH_PORT=hostPort[:containerPort]
  DOCKER_PUBLISH_ARGS=()
  if [[ -n "${FORGE_PUBLISH_PORT:-}" ]]; then
    local host_port container_port
    if [[ "$FORGE_PUBLISH_PORT" == *:* ]]; then
      host_port="${FORGE_PUBLISH_PORT%%:*}"
      container_port="${FORGE_PUBLISH_PORT##*:}"
    else
      host_port="$FORGE_PUBLISH_PORT"
      container_port="$FORGE_PUBLISH_PORT"
    fi
    DOCKER_PUBLISH_ARGS=(-p "127.0.0.1:${host_port}:${container_port}")
  fi
}

forge_ensure_image() {
  forge_require_cmd docker
  if ! forge_docker image inspect "$FORGE_IMAGE" >/dev/null 2>&1; then
    forge_info "Building $FORGE_IMAGE (first run; Nix inside image may take a few minutes)"
    forge_docker build -t "$FORGE_IMAGE" -f "$FORGE_REPO_ROOT/sandbox/images/Dockerfile" \
      "$FORGE_REPO_ROOT/sandbox/images"
  fi
}
