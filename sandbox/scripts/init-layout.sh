#!/usr/bin/env bash
# Create forge data-disk layout (idempotent).
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# shellcheck source=../lib/common.sh
source "$REPO_ROOT/sandbox/lib/common.sh"
forge_ensure_layout
echo "OK: $FORGE_DATA_ROOT"
ls -la "$FORGE_DATA_ROOT"
