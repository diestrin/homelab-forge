# L2 — Incus system container / VM (higher isolation than L1).
# shellcheck shell=bash

profile_enter() {
  local project="$1"
  shift || true

  if ! command -v incus >/dev/null 2>&1; then
    cat >&2 <<EOF
forge: profile=incus requires the Incus client/daemon.

  LXD snap is present on this host but inactive; Phase 2 standardizes on Incus
  (ADR-002). Install (sudo TTY):

    ./sandbox/scripts/install-incus.sh

  Then re-run:

    ./forge sandbox enter $project --profile incus
EOF
    exit 1
  fi

  forge_ensure_layout
  forge_default_limits

  local name
  name="forge-$(basename "$project" | tr '[:upper:]' '[:lower:]' | tr -c 'a-z0-9-' '-' | sed 's/-*$//')"
  name="${name:0:63}"

  if ! incus info "$name" >/dev/null 2>&1; then
    forge_info "Launching Incus instance $name (images:ubuntu/24.04)"
    incus launch images:ubuntu/24.04 "$name" \
      -c limits.cpu="$FORGE_CPUS" \
      -c limits.memory="$FORGE_MEM" \
      -c limits.processes="$FORGE_PIDS" \
      -c security.nesting=false \
      -c security.syscalls.intercept.mknod=false
    # Device: project directory only (not whole Projects tree, not $HOME).
    incus config device add "$name" workspace disk source="$project" path=/workspace
  else
    forge_info "Starting existing Incus instance $name"
    incus start "$name" 2>/dev/null || true
  fi

  forge_info "profile=incus (L2) instance=$name project=$project -> /workspace"
  forge_info "Inbound: use incus proxy with 127.0.0.1 bind if publishing ports"

  if [[ $# -gt 0 ]]; then
    incus exec "$name" -- "$@"
  else
    incus exec "$name" -- bash -lc 'cd /workspace 2>/dev/null || cd; exec bash -l'
  fi
}
