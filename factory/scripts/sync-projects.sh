#!/usr/bin/env bash
# Mirror factory/tasks/* status → GitHub Projects v2 board.
# Git wins: this script only pushes git status to the board; never writes tasks from Projects.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
TASK_LIB="$REPO_ROOT/factory/scripts/task_lib.py"
OWNER="${FORGE_PROJECT_OWNER:-diestrin}"
PROJECT_NUMBER="${FORGE_PROJECT_NUMBER:-1}"
STATUS_FIELD_ID="${FORGE_PROJECT_STATUS_FIELD_ID:-PVTSSF_lAHOAA3gD84Bfo-BzhZ6dSI}"
PROJECT_ID="${FORGE_PROJECT_ID:-PVT_kwHOAA3gD84Bfo-B}"

# Option ids must match factory/PROJECTS.md (refreshed when Planning was added).
declare -A COLUMN_IDS=(
  [Planning]=9d0b2c46
  [Proposed]=a5a9735c
  [Claimed]=654955ca
  [In Progress]=acd648e9
  [Review]=2ec5fd72
  [Done]=f4ef9446
  [Failed]=8ccee8f2
)

log() { echo "==> $*"; }
die() { echo "sync-projects: $*" >&2; exit 1; }

command -v gh >/dev/null || die "gh required"
command -v jq >/dev/null || die "jq required"
command -v python3 >/dev/null || die "python3 required"

# Prefer GitHub App installation token from Vault when AppRole material is present
if [[ -z "${GH_TOKEN:-}" && "${FORGE_SKIP_VAULT:-0}" != "1" ]]; then
  if [[ -f "${FORGE_APPROLE_ENV:-/media/diestrin/data/secrets/vault/approle-forge-agent.env}" ]]; then
    if VAULT_TOKEN_VAL="$("$REPO_ROOT/factory/scripts/vault-agent-login.sh" --print-token 2>/dev/null)"; then
      export VAULT_ADDR="${VAULT_ADDR:-http://127.0.0.1:8200}"
      export VAULT_TOKEN="$VAULT_TOKEN_VAL"
      if TOK="$("$REPO_ROOT/factory/scripts/github-app-token.sh" 2>/dev/null)"; then
        export GH_TOKEN="$TOK"
        export GH_PROMPT_DISABLED=1
        log "using GitHub App installation token for Projects sync"
      fi
    fi
  fi
fi

python3 "$TASK_LIB" --repo "$REPO_ROOT" validate >/dev/null
gh project link "$PROJECT_NUMBER" --owner "$OWNER" --repo diestrin/homelab-forge >/dev/null 2>&1 || true

draft_content_id() {
  local item_id="$1"
  gh api graphql -f query="
    query {
      node(id: \"$item_id\") {
        ... on ProjectV2Item {
          content {
            ... on DraftIssue { id }
            ... on Issue { id }
            ... on PullRequest { id }
          }
        }
      }
    }" --jq '.data.node.content.id'
}

sync_one() {
  local file="$1"
  local data id title status column item_id body content_id opt_id tmp
  data="$(python3 -c "import sys,json,yaml; print(json.dumps(yaml.safe_load(open(sys.argv[1]))))" "$file")"
  id="$(jq -r .id <<<"$data")"
  title="$(jq -r .title <<<"$data")"
  status="$(jq -r .status <<<"$data")"
  item_id="$(jq -r '.github_project_item_id // empty' <<<"$data")"
  column="$(python3 "$TASK_LIB" --repo "$REPO_ROOT" column "$status")"
  opt_id="${COLUMN_IDS[$column]:-}"
  [[ -n "$opt_id" ]] || die "no column id for $column"

  body="$(printf 'Task `%s` (git SoT)\n\n%s\n\nStatus: `%s` → column **%s**\n' \
    "$id" "$(jq -r .goal <<<"$data")" "$status" "$column")"

  if [[ -z "$item_id" || "$item_id" == "null" ]]; then
    log "create draft item for $id ($column)"
    tmp="$(gh project item-create "$PROJECT_NUMBER" --owner "$OWNER" \
      --title "[$id] $title" --body "$body" --format json)"
    item_id="$(jq -r .id <<<"$tmp")"
    python3 - <<PY
from pathlib import Path
import sys
sys.path.insert(0, "$REPO_ROOT/factory/scripts")
from task_lib import load_yaml, save
p = Path("$file")
d = load_yaml(p)
d["github_project_item_id"] = "$item_id"
save(p, d)
PY
  else
    content_id="$(draft_content_id "$item_id")"
    if [[ -n "$content_id" && "$content_id" != "null" ]]; then
      log "update draft content for $id"
      gh project item-edit --id "$content_id" --title "[$id] $title" --body "$body" >/dev/null
    else
      log "skip title/body update for $id (no draft content id)"
    fi
  fi

  log "set Status=$column for $id"
  gh project item-edit --id "$item_id" --project-id "$PROJECT_ID" \
    --field-id "$STATUS_FIELD_ID" --single-select-option-id "$opt_id" >/dev/null
}

DRY="${1:-}"
if [[ "$DRY" == "--dry-run" ]]; then
  python3 "$TASK_LIB" --repo "$REPO_ROOT" list
  exit 0
fi

shopt -s nullglob
for f in "$REPO_ROOT"/factory/tasks/TASK-*.yaml; do
  sync_one "$f"
done
log "sync complete → https://github.com/users/${OWNER}/projects/${PROJECT_NUMBER}"
