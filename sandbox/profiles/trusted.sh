# L0 — trusted workspace on the host (flake + direnv).
# shellcheck shell=bash

profile_enter() {
  local project="$1"
  shift || true

  forge_info "profile=trusted (L0) project=$project"
  cd "$project" || forge_die "cannot cd to $project"

  if [[ $# -gt 0 ]]; then
    exec "$@"
  fi

  # Interactive: prefer login shell so direnv/HM hooks apply (Cursor SSH host session).
  local shell="${SHELL:-/bin/bash}"
  if [[ -x "$shell" ]]; then
    exec "$shell" -l
  fi
  exec /bin/bash -l
}
