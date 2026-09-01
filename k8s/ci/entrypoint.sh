#!/usr/bin/env bash
# Persist runner registration beside the image's /home/runner (do not mount a
# PVC over that path — it hides config.sh / run.sh).
set -euo pipefail
cd /home/runner

STATE=/runner-state
mkdir -p "${STATE}"

copy_state_in() {
  shopt -s nullglob
  local files=("${STATE}/.runner" "${STATE}/.credentials" "${STATE}/.credentials_rsaparams" "${STATE}/.env" "${STATE}/.path")
  local f
  for f in "${files[@]}"; do
    if [[ -f "${f}" ]]; then
      cp -a "${f}" /home/runner/
    fi
  done
}

copy_state_out() {
  shopt -s nullglob
  local files=(.runner .credentials .credentials_rsaparams .env .path)
  local f
  for f in "${files[@]}"; do
    if [[ -f "/home/runner/${f}" ]]; then
      cp -a "/home/runner/${f}" "${STATE}/"
    fi
  done
}

install_tools() {
  if ! command -v kubectl >/dev/null 2>&1; then
    curl -fsSLo /tmp/kubectl "https://dl.k8s.io/release/v1.32.3/bin/linux/amd64/kubectl"
    sudo install -m 0755 /tmp/kubectl /usr/local/bin/kubectl
  fi
  if ! command -v envsubst >/dev/null 2>&1; then
    sudo apt-get update -qq
    sudo apt-get install -y -qq gettext-base
  fi
}

copy_state_in
install_tools

if [[ ! -f .runner ]]; then
  if [[ -z "${RUNNER_TOKEN:-}" ]]; then
    echo "RUNNER_TOKEN missing — mint a registration token and update secret github-runner-registration" >&2
    exit 1
  fi
  ./config.sh \
    --url "${RUNNER_URL}" \
    --token "${RUNNER_TOKEN}" \
    --name "${RUNNER_NAME}" \
    --labels "${RUNNER_LABELS}" \
    --unattended \
    --replace \
    --work /home/runner/_work
  copy_state_out
fi

exec ./run.sh
