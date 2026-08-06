#!/usr/bin/env bash
# Install in-tree host-watch from homelab-forge.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
exec "$REPO_ROOT/security/host-watch/scripts/install.sh"
