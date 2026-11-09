#!/bin/sh
# Initialise a keyless PGLite brain on first start, then serve HTTP MCP.
set -eu
if [ ! -f "${GBRAIN_HOME}/.gbrain/config.json" ] && [ ! -f "${GBRAIN_HOME}/config.json" ]; then
  gbrain init --pglite --no-embedding
fi
gbrain apply-migrations --yes --no-autopilot-install || true
exec gbrain serve --http --port 3131 --bind 0.0.0.0 --public-url "${GBRAIN_PUBLIC_URL}"
