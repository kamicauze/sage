#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE_DEFAULT="$ROOT_DIR/apps/brain-runtime/deploy/env/mac-mini-core.env"
ENV_FILE="${SAGE_ENV_FILE:-$ENV_FILE_DEFAULT}"

if [[ $# -gt 0 && "$1" == *.env ]]; then
  ENV_FILE="$1"
  shift
fi

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

if [[ -d "$ROOT_DIR/.venv" ]]; then
  # shellcheck source=/dev/null
  source "$ROOT_DIR/.venv/bin/activate"
fi

echo "[MacMini] Starting always-on core"
echo "[MacMini] Local LLM backend: ${SAGE_LOCAL_LLM_BACKEND:-ollama}"
echo "[MacMini] Broker: ${MQTT_HOST:-localhost}:${MQTT_PORT:-1883}"

cd "$ROOT_DIR"
python3 -u sage.py pwa --no-stt --no-tts --brain-logs "$@"
