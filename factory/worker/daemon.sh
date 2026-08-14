#!/usr/bin/env bash
# Long-running factory worker: claim via control plane API → run-task.sh (ADR-010).
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLL_SECONDS="${FORGE_WORKER_POLL_SECONDS:-30}"
export WORKER_ID="${FORGE_WORKER_ID:-worker-$(hostname)}"
STATE_DIR="${FORGE_DATA_ROOT:-/media/diestrin/data/forge}/factory/worker"
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
import os, sys
sys.path.insert(0, "$REPO_ROOT/factory/scripts")
import control_plane_client as cp
worker = os.environ.get("WORKER_ID") or os.environ.get("FORGE_WORKER_ID") or "worker-anonymous"
try:
    task = cp.claim(worker, via_queue=True)
    if not task:
        # pg-boss job may already be gone; proposed status is still claimable.
        task = cp.claim(worker, via_queue=False)
except Exception as e:
    print(f"claim error: {e}", file=sys.stderr)
    sys.exit(1)
if task:
    print(task["id"])
PY
}

while true; do
  set +e
  TASK_OUT="$(claim_task 2>&1)"
  claim_rc=$?
  set -e
  if [[ "$claim_rc" -ne 0 ]]; then
    log "claim failed: ${TASK_OUT//$'\n'/ }"
    TASK_ID=""
  else
    TASK_ID="$TASK_OUT"
  fi
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
