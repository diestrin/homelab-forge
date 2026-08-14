#!/usr/bin/env bash
# Render forge-site preview manifests for a PR. Used by CI and local dry-runs.
set -euo pipefail

: "${PREVIEW_PR_NUMBER:?PREVIEW_PR_NUMBER required}"
: "${PREVIEW_IMAGE:?PREVIEW_IMAGE required}"
: "${PREVIEW_HOST:?PREVIEW_HOST required}"
: "${PREVIEW_BRANCH:?PREVIEW_BRANCH required}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES="${ROOT}/templates"

for tpl in "${TEMPLATES}"/*.yaml.in; do
  envsubst '$PREVIEW_PR_NUMBER $PREVIEW_IMAGE $PREVIEW_HOST $PREVIEW_BRANCH' <"${tpl}"
  echo "---"
done
