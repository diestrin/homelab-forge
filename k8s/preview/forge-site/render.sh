#!/usr/bin/env bash
# Render forge-site preview manifests for a PR. Used by CI and local dry-runs.
set -euo pipefail

: "${PREVIEW_PR_NUMBER:?PREVIEW_PR_NUMBER required}"
: "${PREVIEW_IMAGE:?PREVIEW_IMAGE required}"
: "${PREVIEW_HOST:?PREVIEW_HOST required}"
: "${PREVIEW_BRANCH:?PREVIEW_BRANCH required}"

if [[ ! "${PREVIEW_PR_NUMBER}" =~ ^[0-9]+$ ]]; then
  echo "PREVIEW_PR_NUMBER must be digits, got: ${PREVIEW_PR_NUMBER}" >&2
  exit 1
fi
if [[ ! "${PREVIEW_IMAGE}" =~ ^[a-zA-Z0-9._:/-]+$ ]]; then
  echo "PREVIEW_IMAGE contains invalid characters" >&2
  exit 1
fi
if [[ "${PREVIEW_HOST}" == *$'\n'* || "${PREVIEW_BRANCH}" == *$'\n'* ]]; then
  echo "PREVIEW_HOST and PREVIEW_BRANCH must be single-line" >&2
  exit 1
fi
if [[ "${PREVIEW_HOST}" == *$'"'* || "${PREVIEW_BRANCH}" == *$'"'* ]]; then
  echo "PREVIEW_HOST and PREVIEW_BRANCH must not contain double quotes" >&2
  exit 1
fi

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TEMPLATES="${ROOT}/templates"

for tpl in "${TEMPLATES}"/*.yaml.in; do
  envsubst '$PREVIEW_PR_NUMBER $PREVIEW_IMAGE $PREVIEW_HOST $PREVIEW_BRANCH' <"${tpl}"
  echo "---"
done
