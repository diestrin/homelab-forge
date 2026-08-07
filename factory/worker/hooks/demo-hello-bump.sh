#!/usr/bin/env bash
# Scripted implement step for TASK-001 (portfolio demo). Runs inside agent-cell or host worktree.
# Pure bash/sed — sandbox image may not include python3.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CM="$ROOT/k8s/apps/forge-demo-hello/deployment.yaml"
[[ -f "$CM" ]] || { echo "missing $CM" >&2; exit 1; }

MARKER="Phase 4 factory demo"
if grep -q "$MARKER" "$CM"; then
  echo "already bumped"
  exit 0
fi

OLD='Phase 3 demo on localpower.diegobarahona.com (Argo-synced tested)'
NEW='Phase 4 factory demo on localpower.diegobarahona.com (task → worker PR → Argo)'

if ! grep -Fq "$OLD" "$CM"; then
  echo "pattern not found — update hook if hello copy changed" >&2
  exit 1
fi

# portable in-place replace without perl/python
tmp="$(mktemp)"
sed "s#${OLD}#${NEW}#" "$CM" >"$tmp"
mv "$tmp" "$CM"
echo "updated hello-html copy"
