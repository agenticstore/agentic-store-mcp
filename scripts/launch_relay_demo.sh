#!/usr/bin/env bash
set -euo pipefail

# Launch the published AgenticStore package for a Relay screen recording.
# Override these without editing the script, for example:
#   AGENTICSTORE_VERSION=1.0.10 RELAY_PORT=8782 ./scripts/launch_relay_demo.sh

VERSION="${AGENTICSTORE_VERSION:-1.0.10}"
PORT="${RELAY_PORT:-8782}"
ENV_DIR="${RELAY_DEMO_ENV:-/private/tmp/agenticstore-relay-${VERSION}}"
PYTHON="${ENV_DIR}/bin/python"
URL="http://127.0.0.1:${PORT}/#relay"

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install it from https://docs.astral.sh/uv/" >&2
  exit 1
fi

if lsof -tiTCP:"${PORT}" -sTCP:LISTEN >/dev/null 2>&1; then
  echo "A process is already listening on ${PORT}. Open ${URL} or set RELAY_PORT to another port." >&2
  exit 1
fi

if [[ ! -x "${PYTHON}" ]]; then
  uv venv "${ENV_DIR}"
fi
uv pip install --python "${PYTHON}" --refresh "agentic-store-mcp==${VERSION}"

"${PYTHON}" -m uvicorn agentic_store_mcp.webapp.app:app \
  --host 127.0.0.1 \
  --port "${PORT}" \
  --lifespan off \
  >/private/tmp/agenticstore-relay-${PORT}.log 2>&1 &
SERVER_PID=$!
trap 'kill "${SERVER_PID}" 2>/dev/null || true' EXIT INT TERM

for _ in {1..30}; do
  if curl -fsS "http://127.0.0.1:${PORT}/" >/dev/null 2>&1; then
    echo "Relay ${VERSION} is ready: ${URL}"
    if command -v open >/dev/null 2>&1; then
      open "${URL}" >/dev/null 2>&1 || true
    fi
    wait "${SERVER_PID}"
    exit $?
  fi
  sleep 0.2
done

echo "Relay did not start. See /private/tmp/agenticstore-relay-${PORT}.log" >&2
exit 1
