#!/usr/bin/env bash
# Long-running factory worker: claim jobs via control plane API → dispatch (ADR-010/ADR-011).
# Claims plan, implement, and watch-checks jobs; runs up to FORGE_WORKER_CONCURRENCY
# jobs in parallel (separate worktrees). Same-task jobs serialize via flock.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
POLL_SECONDS="${FORGE_WORKER_POLL_SECONDS:-30}"
CONCURRENCY="${FORGE_WORKER_CONCURRENCY:-2}"
export WORKER_ID="${FORGE_WORKER_ID:-worker-$(hostname)}"
STATE_DIR="${FORGE_DATA_ROOT:-/media/diestrin/data/forge}/factory/worker"
JOBS_DIR="$STATE_DIR/jobs"
LOCKS_DIR="$STATE_DIR/locks"
mkdir -p "$STATE_DIR" "$JOBS_DIR" "$LOCKS_DIR"
chmod 700 "${FORGE_DATA_ROOT:-/media/diestrin/data/forge}/factory" 2>/dev/null || true
PIDFILE="$STATE_DIR/${WORKER_ID}.pid"
LOG="$STATE_DIR/${WORKER_ID}.log"

# Structured journal line: systemd captures stdout; tee keeps the host log file.
log() { printf '%s forge-worker worker=%s %s\n' "$(date -Is)" "$WORKER_ID" "$*" | tee -a "$LOG"; }

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

log "start poll=${POLL_SECONDS}s concurrency=$CONCURRENCY api=$FORGE_CONTROL_PLANE_URL kinds=plan,implement,watch-checks"

# Claim next job of any kind. Prints: "<kind> <task_id> <job_id> <meta_file>" or nothing.
claim_job() {
  python3 - "$JOBS_DIR" <<PY
import json, os, sys
sys.path.insert(0, "$REPO_ROOT/factory/scripts")
import control_plane_client as cp
jobs_dir = sys.argv[1]
worker = os.environ.get("WORKER_ID") or "worker-anonymous"
try:
    res = cp.claim_job(worker, ["plan", "implement", "watch-checks"])
except Exception as e:
    print(f"claim error: {e}", file=sys.stderr)
    sys.exit(1)
if not res:
    sys.exit(0)
job = res.get("job") or {}
task = res.get("task") or {}
task_id = (job.get("payload") or {}).get("taskId") or task.get("id")
if not task_id:
    sys.exit(0)
kind = job.get("kind") or "implement"
job_id = job.get("id") or "none"
meta = (job.get("payload") or {}).get("meta") or {}
meta_file = os.path.join(jobs_dir, f"{job_id if job_id != 'none' else task_id}.json")
with open(meta_file, "w", encoding="utf-8") as fh:
    json.dump(meta, fh)
print(f"{kind} {task_id} {job_id} {meta_file}")
PY
}

# Run one claimed job to completion; same-task jobs serialize on a lock.
run_job() {
  local kind="$1" task_id="$2" job_id="$3" meta_file="$4"
  local lock="$LOCKS_DIR/${task_id}.lock"
  (
    exec 9>"$lock"
    flock 9
    log "job start kind=$kind task=$task_id job=$job_id"
    local rc=0
    case "$kind" in
      plan)
        FORGE_WORKER_ID="$WORKER_ID" python3 "$REPO_ROOT/factory/orchestrator/run_plan_job.py" \
          --task-id "$task_id" --job-id "$job_id" --meta "$(cat "$meta_file")" || rc=$?
        ;;
      watch-checks)
        FORGE_WORKER_ID="$WORKER_ID" python3 "$REPO_ROOT/factory/worker/watch_checks.py" \
          --task-id "$task_id" --job-id "$job_id" --meta "$(cat "$meta_file")" || rc=$?
        ;;
      implement|*)
        FORGE_WORKER_ID="$WORKER_ID" FORGE_JOB_ID="$job_id" FORGE_JOB_META_FILE="$meta_file" \
          "$REPO_ROOT/factory/worker/run-task.sh" "$task_id" || rc=$?
        "$REPO_ROOT/factory/scripts/sync-projects.sh" >>"$LOG" 2>&1 || true
        ;;
    esac
    log "job done kind=$kind task=$task_id job=$job_id rc=$rc"
    rm -f "$meta_file"
  ) &
}

while true; do
  # Reap finished background jobs (releases concurrency slots).
  ACTIVE="$(jobs -pr | wc -l)"

  CLAIMED=0
  if [[ "$ACTIVE" -lt "$CONCURRENCY" ]]; then
    set +e
    JOB_OUT="$(claim_job 2>&1)"
    claim_rc=$?
    set -e
    if [[ "$claim_rc" -ne 0 ]]; then
      log "claim failed: ${JOB_OUT//$'\n'/ }"
    elif [[ -n "$JOB_OUT" ]]; then
      # Fixed 4-field envelope from claim_job; word splitting is intentional.
      # shellcheck disable=SC2086
      run_job $JOB_OUT
      CLAIMED=1
    fi
  fi

  if [[ "$ONCE" -eq 1 ]]; then
    # Single iteration: wait for whatever we started, then exit.
    wait
    exit 0
  fi

  if [[ "$CLAIMED" -eq 0 ]]; then
    if [[ "$ACTIVE" -eq 0 ]]; then
      log "idle (no queued jobs)"
    fi
    sleep "$POLL_SECONDS"
  fi
done
