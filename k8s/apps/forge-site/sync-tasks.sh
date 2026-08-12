#!/usr/bin/env bash
# Sync factory/tasks/*.yaml into this k8s bundle for ConfigMap generation.
# Kustomize cannot reference files outside the kustomization root (see #1009).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
DEST="$(cd "$(dirname "$0")" && pwd)/tasks"
SRC="$ROOT/factory/tasks"

mkdir -p "$DEST"
rm -f "$DEST"/*.yaml
cp "$SRC"/*.yaml "$DEST"/

echo "Synced $(find "$DEST" -maxdepth 1 -name '*.yaml' | wc -l) task file(s) to $DEST"
