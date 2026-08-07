#!/usr/bin/env bash
# Phase 2 smoke tests — escape attempts fail closed; trusted + devcontainer demo.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../lib/common.sh
source "$REPO_ROOT/sandbox/lib/common.sh"

DEMO="${FORGE_SMOKE_PROJECT:-$REPO_ROOT/sandbox/examples/hello-flake}"
OTHER_PROJECT="$FORGE_PROJECTS_ROOT/host-watch"
PASS=0
FAIL=0

pass() { echo "PASS: $*"; PASS=$((PASS + 1)); }
fail() { echo "FAIL: $*" >&2; FAIL=$((FAIL + 1)); }

forge_info "Smoke project: $DEMO"
forge_ensure_layout

# --- L0 trusted: hello from flake/direnv or nix develop ---
forge_info "1) trusted profile runs demo"
if (
  cd "$DEMO"
  if command -v nix >/dev/null 2>&1; then
    nix develop --command hello
  else
    hello
  fi
) >/tmp/forge-smoke-trusted.out 2>&1; then
  if grep -q 'Hello, world!' /tmp/forge-smoke-trusted.out; then
    pass "trusted: hello"
  else
    # hello prints to stdout; nix develop may wrap
    if grep -qi 'hello' /tmp/forge-smoke-trusted.out; then
      pass "trusted: hello (output present)"
    else
      cat /tmp/forge-smoke-trusted.out >&2
      fail "trusted: unexpected output"
    fi
  fi
else
  cat /tmp/forge-smoke-trusted.out >&2
  fail "trusted: nix develop / hello failed"
fi

# --- L1 image build + hello inside container ---
forge_info "2) devcontainer profile runs demo (build if needed)"
forge_ensure_image
if forge_docker run --rm \
  --security-opt=no-new-privileges \
  --memory=2g --cpus=1 --pids-limit=1024 \
  --mount "type=bind,source=${DEMO},target=/workspace" \
  -w /workspace \
  "$FORGE_IMAGE" \
  bash -lc 'hello' >/tmp/forge-smoke-dc.out 2>&1; then
  if grep -q 'Hello, world!' /tmp/forge-smoke-dc.out; then
    pass "devcontainer: hello"
  else
    cat /tmp/forge-smoke-dc.out >&2
    fail "devcontainer: hello output missing"
  fi
else
  cat /tmp/forge-smoke-dc.out >&2
  fail "devcontainer: container run failed"
fi

# --- Agent-cell: no docker.sock, no unrelated projects ---
forge_info "3) agent-cell cannot see docker.sock or unrelated projects"
CELL_OUT=/tmp/forge-smoke-cell.out
if forge_docker run --rm \
  --security-opt=no-new-privileges \
  --memory=1g --cpus=1 --pids-limit=512 \
  --mount "type=bind,source=${DEMO},target=/workspace" \
  -w /workspace \
  "$FORGE_IMAGE" \
  bash -lc '
    set -e
    echo "=== mounts ==="
    # docker.sock must not exist
    if [[ -S /var/run/docker.sock || -S /run/docker.sock || -e /run/user/1000/docker.sock ]]; then
      echo "ESCAPE: docker.sock visible"; exit 10
    fi
    echo "docker.sock: absent (good)"
    # Unrelated project path on host must not be visible
    if [[ -d /media/diestrin/data/Projects/host-watch ]]; then
      echo "ESCAPE: unrelated Projects tree visible"; exit 11
    fi
    echo "unrelated project path: absent (good)"
    # Writing outside /workspace should fail (path does not exist / not mounted)
    if mkdir -p /media/diestrin/data/Projects/forge-escape-test 2>/dev/null; then
      echo "ESCAPE: wrote outside workspace"; exit 12
    fi
    echo "write outside mount: failed closed (good)"
    # Workspace itself is visible
    test -f /workspace/flake.nix
    hello
  ' >"$CELL_OUT" 2>&1; then
  pass "agent-cell: isolation checks"
else
  cat "$CELL_OUT" >&2
  fail "agent-cell: isolation checks failed"
fi

# --- Publish bind is localhost-only when set ---
forge_info "4) publish policy defaults to no host bind; FORGE_PUBLISH_PORT uses 127.0.0.1"
# shellcheck disable=SC2034
FORGE_PROFILE=devcontainer
forge_publish_args
if [[ ${#DOCKER_PUBLISH_ARGS[@]} -eq 0 ]]; then
  pass "no publish by default"
else
  fail "unexpected default publish args"
fi
FORGE_PUBLISH_PORT=18080 forge_publish_args
if [[ "${DOCKER_PUBLISH_ARGS[*]}" == *"127.0.0.1:18080:18080"* ]]; then
  pass "FORGE_PUBLISH_PORT binds 127.0.0.1"
else
  fail "publish args: ${DOCKER_PUBLISH_ARGS[*]:-empty}"
fi

# --- Layout permissions ---
forge_info "5) forge data root mode"
mode="$(stat -c '%a' "$FORGE_DATA_ROOT")"
if [[ "$mode" == "700" ]]; then
  pass "FORGE_DATA_ROOT mode 700"
else
  fail "FORGE_DATA_ROOT mode is $mode (want 700)"
fi

if [[ -d "$FORGE_SECRETS_ROOT" ]]; then
  smode="$(stat -c '%a' "$FORGE_SECRETS_ROOT")"
  if [[ "$smode" == "700" ]]; then
    pass "secrets root mode 700"
  else
    fail "secrets root mode is $smode (want 700)"
  fi
else
  pass "secrets root absent (document-only; not a smoke fail)"
fi

# Reference OTHER_PROJECT existence on host (contrast with cell)
if [[ -d "$OTHER_PROJECT" ]]; then
  pass "host still has unrelated project (isolation contrast)"
else
  pass "unrelated project path not present on host (skipped contrast)"
fi

echo
echo "Smoke summary: $PASS passed, $FAIL failed"
[[ "$FAIL" -eq 0 ]]
