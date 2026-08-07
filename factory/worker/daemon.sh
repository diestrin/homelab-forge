#!/usr/bin/env bash
# Long-running factory worker: poll proposed tasks → run-task.sh (1B).
# Safe defaults: one task at a time; no host docker.sock into cells; no merge/deploy.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASK_LIB="$REPO_ROOT/factory/scripts/task_lib.py"
POLL_SECONDS="${FORGE_WORKER_POLL_SECONDS:-30}"
WORKER_ID="${FORGE_WORKER_ID:-worker-$(hostname)}"
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

log "start worker_id=$WORKER_ID poll=${POLL_SECONDS}s repo=$REPO_ROOT"

while true; do
  python3 "$TASK_LIB" --repo "$REPO_ROOT" validate >/dev/null || log "validate warnings ignored for poll"

  # Pick oldest proposed task
  mapfile -t CLAIM_OUT < <(python3 "$TASK_LIB" --repo "$REPO_ROOT" claim --worker "$WORKER_ID" 2>/dev/null || true)
  if [[ ${#CLAIM_OUT[@]} -ge 1 && -n "${CLAIM_OUT[0]:-}" ]]; then
    TASK_ID="${CLAIM_OUT[0]}"
    log "claimed $TASK_ID — running"
    if "$REPO_ROOT/factory/worker/run-task.sh" "$TASK_ID"; then
      log "finished $TASK_ID ok"
    else
      log "finished $TASK_ID with error (see artifacts)"
    fi
    # Mirror board after each run
    "$REPO_ROOT/factory/scripts/sync-projects.sh" >>"$LOG" 2>&1 || true
  else
    log "idle (no proposed tasks)"
  fi

  if [[ "$ONCE" -eq 1 ]]; then
    exit 0
  fi
  sleep "$POLL_SECONDS"
done
