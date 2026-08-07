#!/usr/bin/env bash
# Claimed-task runner: in_progress → worktree → optional Vault secrets → hook/cell → artifacts → review|failed.
# Does NOT merge to main or kubectl-apply cluster apps (ADR-008).
# Uses an isolated git worktree so the operator's dirty primary tree is never committed.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../../sandbox/lib/common.sh
source "$REPO_ROOT/sandbox/lib/common.sh"
TASK_LIB="$REPO_ROOT/factory/scripts/task_lib.py"
WORKER_ID="${FORGE_WORKER_ID:-worker-$(hostname)-$$}"
ART_ROOT="${FORGE_DATA_ROOT:-/media/diestrin/data/forge}/factory/artifacts"
LOG_DIR="$ART_ROOT/logs"
mkdir -p "$LOG_DIR" "$ART_ROOT"
chmod 700 "${FORGE_DATA_ROOT:-/media/diestrin/data/forge}/factory" 2>/dev/null || true

die() { echo "run-task: $*" >&2; exit 1; }
log() { echo "==> $*"; }

TASK_ID="${1:-}"
[[ -n "$TASK_ID" ]] || die "usage: run-task.sh TASK-NNN"

TASK_FILE=""
for f in "$REPO_ROOT"/factory/tasks/TASK-*.yaml; do
  id="$(python3 -c "import yaml,sys; print(yaml.safe_load(open(sys.argv[1]))['id'])" "$f")"
  if [[ "$id" == "$TASK_ID" ]]; then
    TASK_FILE="$f"
    break
  fi
done
[[ -n "$TASK_FILE" ]] || die "task file not found for $TASK_ID"

eval "$(python3 - <<PY
import yaml, shlex
from pathlib import Path
d = yaml.safe_load(Path("$TASK_FILE").read_text())
def emit(k, v):
    if v is None:
        print(f"export {k}=")
    else:
        print(f"export {k}={shlex.quote(str(v))}")
emit("TASK_STATUS", d.get("status"))
emit("TASK_PROFILE", d.get("sandbox_profile", "agent-cell"))
emit("TASK_REPO_PATH", d.get("repo_path", "."))
emit("TASK_BRANCH", d.get("branch") or f"factory/{d['id'].lower()}")
emit("TASK_HOOK", d.get("worker_hook") or "")
emit("TASK_BUDGET", d.get("budget_minutes") or 30)
emit("TASK_TITLE", d.get("title") or "")
emit("TASK_RISK", d.get("risk_level") or "low")
PY
)"

LOG="$LOG_DIR/${TASK_ID}.log"
exec > >(tee -a "$LOG") 2>&1
log "task=$TASK_ID worker=$WORKER_ID budget=${TASK_BUDGET}m profile=$TASK_PROFILE"

cleanup_cell() {
  local name="${CELL_NAME:-}"
  if [[ -n "$name" ]]; then
    forge_docker rm -f "$name" >/dev/null 2>&1 || true
  fi
}
fail_task() {
  local reason="$1"
  log "FAIL: $reason"
  python3 "$TASK_LIB" --repo "$REPO_ROOT" set-status "$TASK_ID" failed --assignee "$WORKER_ID" || true
  python3 "$TASK_LIB" --repo "$REPO_ROOT" add-artifact "$TASK_ID" log "$LOG" || true
  cleanup_cell
  exit 1
}

trap 'fail_task "interrupted or budget exceeded"' INT TERM

BUDGET_SEC=$((TASK_BUDGET * 60))
(
  sleep "$BUDGET_SEC"
  echo "run-task: budget ${TASK_BUDGET}m exceeded" >&2
  kill -TERM $$ 2>/dev/null || true
) &
WATCHDOG_PID=$!
clear_watchdog() { kill "$WATCHDOG_PID" 2>/dev/null || true; }
trap 'clear_watchdog; cleanup_cell' EXIT

case "$TASK_STATUS" in
  proposed)
    python3 "$TASK_LIB" --repo "$REPO_ROOT" claim --task "$TASK_ID" --worker "$WORKER_ID" >/dev/null
    ;;
  claimed) ;;
  in_progress) log "resuming in_progress task" ;;
  *) die "cannot run task in status=$TASK_STATUS" ;;
esac

python3 "$TASK_LIB" --repo "$REPO_ROOT" set-status "$TASK_ID" in_progress --assignee "$WORKER_ID"

PROJECT="$(forge_resolve_project "$TASK_REPO_PATH")"

# Optional Vault secrets (GH token etc.) — never written into git
if [[ "${FORGE_SKIP_VAULT:-0}" != "1" ]]; then
  if [[ -f "${FORGE_APPROLE_ENV:-/media/diestrin/data/secrets/vault/approle-forge-agent.env}" ]]; then
    if VAULT_TOKEN_VAL="$("$REPO_ROOT/factory/scripts/vault-agent-login.sh" --print-token 2>/dev/null)"; then
      export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
      export VAULT_TOKEN="$VAULT_TOKEN_VAL"
      if GH_TOKEN_FETCHED="$(vault kv get -field=token secret/forge/agents/github 2>/dev/null || true)"; then
        if [[ -n "$GH_TOKEN_FETCHED" ]]; then
          export GH_TOKEN="$GH_TOKEN_FETCHED"
          log "fetched GitHub token from Vault (secret/forge/agents/github)"
        fi
      fi
    else
      log "Vault AppRole login skipped/failed — continuing without GH_TOKEN from Vault"
    fi
  else
    log "no AppRole env; continuing without Vault (see docs/runbooks/factory.md)"
  fi
fi

cd "$PROJECT"
git rev-parse --is-inside-work-tree >/dev/null || die "not a git repo: $PROJECT"
DEFAULT_BRANCH="$(git symbolic-ref refs/remotes/origin/main 2>/dev/null | sed 's@^refs/remotes/origin/@@' || echo main)"
git fetch origin "$DEFAULT_BRANCH" >/dev/null 2>&1 || true

WT_ROOT="${FORGE_DATA_ROOT:-/media/diestrin/data/forge}/factory/worktrees"
WT="$WT_ROOT/$TASK_ID"
mkdir -p "$WT_ROOT"
chmod 700 "${FORGE_DATA_ROOT:-/media/diestrin/data/forge}/factory" 2>/dev/null || true

BASE_REF="origin/${DEFAULT_BRANCH}"
git rev-parse --verify "$BASE_REF" >/dev/null 2>&1 || BASE_REF="$DEFAULT_BRANCH"

if [[ -d "$WT" ]]; then
  log "reusing worktree $WT"
else
  log "creating worktree $WT (branch $TASK_BRANCH from $BASE_REF)"
  git -C "$PROJECT" worktree add -B "$TASK_BRANCH" "$WT" "$BASE_REF"
fi

WORK_REPO="$WT"
export FORGE_TASK_REPO="$WORK_REPO"

if [[ -n "$TASK_HOOK" ]]; then
  if [[ ! -f "$WORK_REPO/$TASK_HOOK" && -f "$REPO_ROOT/$TASK_HOOK" ]]; then
    mkdir -p "$(dirname "$WORK_REPO/$TASK_HOOK")"
    cp "$REPO_ROOT/$TASK_HOOK" "$WORK_REPO/$TASK_HOOK"
    chmod +x "$WORK_REPO/$TASK_HOOK"
    log "copied worker_hook into worktree from primary tree"
  fi
fi

run_hook() {
  local hook_rel="$1"
  local hook="$WORK_REPO/$hook_rel"
  local rc=0
  [[ -f "$hook" ]] || die "worker_hook missing: $hook"
  chmod +x "$hook" || true
  if [[ "$TASK_PROFILE" == "agent-cell" ]]; then
    log "running hook inside agent-cell (mount=$WORK_REPO)"
    CELL_NAME="forge-worker-${TASK_ID}-$$"
    export CELL_NAME
    set +e
    FORGE_AGENT_RW=true "$REPO_ROOT/forge" sandbox enter "$WORK_REPO" --profile agent-cell -- \
      bash -lc "cd /workspace && ./$hook_rel"
    rc=$?
    set -e
    CELL_NAME=""
  else
    log "running hook on host profile=$TASK_PROFILE"
    set +e
    (cd "$WORK_REPO" && "$hook")
    rc=$?
    set -e
  fi
  return "$rc"
}

if [[ -n "$TASK_HOOK" ]]; then
  run_hook "$TASK_HOOK" || fail_task "worker_hook failed"
else
  log "no worker_hook — preparing worktree only (attach Cursor/agent to continue)"
  NOTE="$ART_ROOT/${TASK_ID}-awaiting-agent.md"
  cat >"$NOTE" <<EOF
# $TASK_ID awaiting implementer

Branch: \`$TASK_BRANCH\`
Worktree: \`$WORK_REPO\`
Profile: \`$TASK_PROFILE\`
Worker: \`$WORKER_ID\` prepared worktree then stopped (no worker_hook).

Attach with:
  ./forge sandbox enter $WORK_REPO --profile agent-cell
EOF
  python3 "$TASK_LIB" --repo "$REPO_ROOT" add-artifact "$TASK_ID" note "$NOTE"
  python3 "$TASK_LIB" --repo "$REPO_ROOT" set-status "$TASK_ID" review --assignee "$WORKER_ID"
  python3 "$TASK_LIB" --repo "$REPO_ROOT" add-artifact "$TASK_ID" log "$LOG"
  clear_watchdog
  trap - EXIT INT TERM
  cleanup_cell
  log "moved to review (manual implement expected)"
  exit 0
fi

cd "$WORK_REPO"
# Drop bootstrap-copied hook from the implement PR (factory code lands via normal commits)
if [[ -n "$TASK_HOOK" ]]; then
  git checkout -- "$TASK_HOOK" 2>/dev/null || true
  if [[ -f "$WORK_REPO/$TASK_HOOK" ]] && ! git cat-file -e "HEAD:$TASK_HOOK" 2>/dev/null; then
    rm -f "$WORK_REPO/$TASK_HOOK"
    # remove empty dirs left behind
    rmdir -p "$(dirname "$WORK_REPO/$TASK_HOOK")" 2>/dev/null || true
  fi
fi

if [[ -n "$(git status --porcelain)" ]]; then
  git add -A
  git -c user.email="${GIT_AUTHOR_EMAIL:-forge-worker@localhost}" \
      -c user.name="${GIT_AUTHOR_NAME:-forge-worker}" \
      commit -m "$(cat <<EOF
factory($TASK_ID): ${TASK_TITLE}

Worker $WORKER_ID via forge factory. Review required before merge.
EOF
)"
else
  log "no file changes from hook"
fi

PR_URL=""
if git remote get-url origin >/dev/null 2>&1; then
  if [[ -n "$(git log "$BASE_REF"..HEAD --oneline 2>/dev/null || true)" ]]; then
    if git push -u origin "$TASK_BRANCH" 2>&1; then
      if command -v gh >/dev/null; then
        PR_URL="$(gh pr create --repo diestrin/homelab-forge --base "$DEFAULT_BRANCH" --head "$TASK_BRANCH" \
          --title "factory($TASK_ID): $TASK_TITLE" \
          --body "$(cat <<EOF
## Factory task

- Task: \`$TASK_ID\`
- Risk: \`$TASK_RISK\`
- Worker: \`$WORKER_ID\`
- Profile: \`$TASK_PROFILE\`

## Deploy

Do **not** kubectl-apply. After human review + merge to \`main\`, Argo CD syncs (ADR-008).

## Checklist

See \`factory/review/CHECKLIST.md\`.
EOF
)" 2>/dev/null || true)"
        if [[ -z "$PR_URL" ]]; then
          PR_URL="$(gh pr view "$TASK_BRANCH" --repo diestrin/homelab-forge --json url -q .url 2>/dev/null || true)"
        fi
      fi
    else
      log "push failed (auth?) — artifacts only"
    fi
  else
    log "no commits ahead of $BASE_REF — skip push/PR"
  fi
fi

DIFF_ART="$ART_ROOT/${TASK_ID}-git.diff"
git diff "$BASE_REF...HEAD" >"$DIFF_ART" 2>/dev/null || true
python3 "$TASK_LIB" --repo "$REPO_ROOT" add-artifact "$TASK_ID" log "$LOG"
python3 "$TASK_LIB" --repo "$REPO_ROOT" add-artifact "$TASK_ID" other "$DIFF_ART"
if [[ -n "$PR_URL" ]]; then
  python3 "$TASK_LIB" --repo "$REPO_ROOT" add-artifact "$TASK_ID" pr "artifacts/${TASK_ID}-pr.txt" --url "$PR_URL"
  printf '%s\n' "$PR_URL" >"$ART_ROOT/${TASK_ID}-pr.txt"
fi

if git diff --name-only "$BASE_REF...HEAD" 2>/dev/null | grep -q '^k8s/'; then
  if command -v kubectl >/dev/null && [[ -f "${KUBECONFIG:-$HOME/.kube/config}" ]]; then
    KDIFF="$ART_ROOT/${TASK_ID}-kubectl.diff"
    kubectl -n forge-demo diff -k "$WORK_REPO/k8s/apps/forge-demo-hello" >"$KDIFF" 2>&1 || true
    python3 "$TASK_LIB" --repo "$REPO_ROOT" add-artifact "$TASK_ID" kubectl_diff "$KDIFF"
  fi
fi

python3 "$TASK_LIB" --repo "$REPO_ROOT" set-status "$TASK_ID" review --assignee "$WORKER_ID"
clear_watchdog
trap - EXIT INT TERM
cleanup_cell
log "done → review${PR_URL:+ pr=$PR_URL}"
"$REPO_ROOT/factory/scripts/sync-projects.sh" >/dev/null 2>&1 || true
