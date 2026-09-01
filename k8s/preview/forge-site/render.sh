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

render_tpl() {
  envsubst '$PREVIEW_PR_NUMBER $PREVIEW_IMAGE $PREVIEW_HOST $PREVIEW_BRANCH' <"$1"
  echo "---"
}

# Namespace must be the first document. `kubectl apply -f -` continues on
# error and bash glob is alphabetical, so Deployment/ExternalSecret/Ingress
# otherwise hit "namespaces ... not found" before the Namespace is created.
render_tpl "${TEMPLATES}/namespace.yaml.in"
for tpl in "${TEMPLATES}"/*.yaml.in; do
  [[ "$(basename "${tpl}")" == "namespace.yaml.in" ]] && continue
  render_tpl "${tpl}"
done
