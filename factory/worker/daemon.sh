#!/usr/bin/env bash
# Long-running factory worker: claim via control plane API → run-task.sh (ADR-010).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLL_SECONDS="${FORGE_WORKER_POLL_SECONDS:-30}"
WORKER_ID="${FORGE_WORKER_ID:-worker-$(hostname)}"
STATE_DIR="${FORGE_DATA_ROOT:-/media/diestrin/data/forge}/factory/worker"
CLIENT="$REPO_ROOT/factory/scripts/control_plane_client.py"
mkdir -p "$STATE_DIR"
chmod 700 "${FORGE_DATA_ROOT:-/media/diestrin/data/forge}/factory" 2>/dev/null || true
PIDFILE="$STATE_DIR/${WORKER_ID}.pid"
LOG="$STATE_DIR/${WORKER_ID}.log"

log() { printf '%s %s\n' "$(date -Is)" "$*" | tee -a "$LOG"; }

if [[ "${1:-}" == "--once" ]]; then
  ONCE=1
else
  ONCE=0
fi

if [[ -f "$PIDFILE" ]]; then
  old="$(cat "$PIDFILE" || true)"
  if [[ -n "$old" ]] && kill -0 "$old" 2>/dev/null; then
    echo "daemon already running pid=$old ($PIDFILE)" >&2
    exit 1
  fi
fi
echo $$ >"$PIDFILE"
trap 'rm -f "$PIDFILE"' EXIT

if [[ -z "${FORGE_CONTROL_PLANE_URL:-}" || -z "${FORGE_API_TOKEN:-}" ]]; then
  echo "daemon: FORGE_CONTROL_PLANE_URL and FORGE_API_TOKEN required (ADR-010)" >&2
  exit 1
fi

log "start worker_id=$WORKER_ID poll=${POLL_SECONDS}s api=$FORGE_CONTROL_PLANE_URL"

claim_task() {
  python3 - <<PY
import json, os, sys
sys.path.insert(0, "$REPO_ROOT/factory/scripts")
import control_plane_client as cp
task = cp.claim(os.environ["WORKER_ID"], via_queue=True)
if task:
    print(task["id"])
PY
}

while true; do
  TASK_ID="$(claim_task 2>/dev/null || true)"
  if [[ -n "$TASK_ID" ]]; then
    log "claimed $TASK_ID — running"
    if FORGE_WORKER_ID="$WORKER_ID" "$REPO_ROOT/factory/worker/run-task.sh" "$TASK_ID"; then
      log "finished $TASK_ID ok"
    else
      log "finished $TASK_ID with error (see artifacts)"
    fi
    "$REPO_ROOT/factory/scripts/sync-projects.sh" >>"$LOG" 2>&1 || true
  else
    log "idle (no proposed tasks)"
  fi

  if [[ "$ONCE" -eq 1 ]]; then
    exit 0
  fi
  sleep "$POLL_SECONDS"
done
