#!/bin/sh
# Initialise a keyless brain on the dedicated pgvector Postgres on first start,
# then serve HTTP MCP. GBRAIN_DATABASE_URL is injected by the Deployment.
set -eu
if [ ! -f "${GBRAIN_HOME}/.gbrain/config.json" ] && [ ! -f "${GBRAIN_HOME}/config.json" ]; then
  gbrain init --non-interactive --no-embedding --url "${GBRAIN_DATABASE_URL}"
fi
gbrain apply-migrations --yes --no-autopilot-install || true
exec gbrain serve --http --port 3131 --bind 0.0.0.0 --public-url "${GBRAIN_PUBLIC_URL}"
