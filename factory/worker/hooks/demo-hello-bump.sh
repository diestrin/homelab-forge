#!/usr/bin/env bash
# Scripted implement step for TASK-001 (portfolio demo). Runs inside agent-cell or host worktree.
set -euo pipefail

REPO_ROOT="${FORGE_TASK_REPO:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)}"
CM="$REPO_ROOT/k8s/apps/forge-demo-hello/deployment.yaml"
[[ -f "$CM" ]] || { echo "missing $CM" >&2; exit 1; }

MARKER="Phase 4 factory demo"
if grep -q "$MARKER" "$CM"; then
  echo "already bumped"
  exit 0
fi

# Replace the Phase 3 demo sentence with a Phase 4 marker (keeps file valid YAML).
python3 - <<'PY'
from pathlib import Path
import re
path = Path("k8s/apps/forge-demo-hello/deployment.yaml")
text = path.read_text(encoding="utf-8")
new = re.sub(
    r"Phase 3 demo on localpower\.diegobarahona\.com \(Argo-synced tested\)",
    "Phase 4 factory demo on localpower.diegobarahona.com (task → worker PR → Argo)",
    text,
    count=1,
)
if new == text:
    raise SystemExit("pattern not found — update hook if hello copy changed")
path.write_text(new, encoding="utf-8")
print("updated hello-html copy")
PY
