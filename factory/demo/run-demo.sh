#!/usr/bin/env bash
# Scripted portfolio demo path (Phase 4.5).
# ask → task → worker PR → (human merge) → Argo → public HTTPS
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$REPO_ROOT"

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
note() { printf '    %s\n' "$*"; }

step "1. Validate task contract"
./forge factory validate
./forge factory list

step "2. Mirror board (git → Projects)"
./forge factory sync || note "sync failed — check gh project scopes"

step "3. Ensure TASK-001 is proposed (reset if needed)"
STATUS="$(python3 factory/scripts/task_lib.py --repo "$REPO_ROOT" get TASK-001 | python3 -c "import sys,yaml; print(yaml.safe_load(sys.stdin)['status'])")"
note "TASK-001 status=$STATUS"
if [[ "$STATUS" == "done" || "$STATUS" == "failed" || "$STATUS" == "review" ]]; then
  note "Reset TASK-001 to proposed for demo? (y/N)"
  read -r ans || true
  if [[ "${ans:-}" == "y" || "${ans:-}" == "Y" ]]; then
    # allow failed→proposed; for review/done use manual edit
    if [[ "$STATUS" == "failed" ]]; then
      ./forge factory set-status TASK-001 proposed
    else
      python3 - <<'PY'
from pathlib import Path
import sys
sys.path.insert(0, "factory/scripts")
from task_lib import load_yaml, save
p = next(Path("factory/tasks").glob("TASK-001*.yaml"))
d = load_yaml(p)
d["status"] = "proposed"
d["assignee_agent"] = None
d["claimed_at"] = None
d["artifacts"] = []
save(p, d)
print("forced proposed (demo reset)")
PY
    fi
  fi
fi

step "4. Worker claim + implement (agent-cell, scripted hook)"
note "Requires: clean git tree on a branch we can leave, Vault optional, gh auth for push/PR."
note "Run worker once? (y/N)"
read -r ans || true
if [[ "${ans:-}" == "y" || "${ans:-}" == "Y" ]]; then
  ./forge factory worker --once
else
  note "Skipped. Later: ./forge factory worker --once"
fi

step "5. Human review"
note "Open the PR URL from factory artifacts or gh pr list"
note "Checklist: factory/review/CHECKLIST.md"
note "Merge only when satisfied."

step "6. Deploy via Argo (after merge to main)"
note "kubectl -n forge-system get application forge-demo-hello -w"
note "curl -fsS https://localpower.diegobarahona.com | grep -i 'Phase 4'"

step "7. Close the loop"
note "./forge factory set-status TASK-001 done"
note "./forge factory sync"

cat <<'EOF'

Demo narrative
--------------
Orchestrator chat created TASK-001 (git SoT). Worker daemon/cell ran the hook,
opened a PR, and stopped at review. Human merge to main; Argo CD synced
forge-demo-hello; HTTPS shows the Phase 4 copy. No worker used the host Docker
socket; no kubectl apply bypassed GitOps.
EOF
