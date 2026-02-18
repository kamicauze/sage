#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/apps/brain-runtime/deploy/env/orin-voice.env}"

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

MQTT_HOST="${MQTT_HOST:-}"
MQTT_PORT="${MQTT_PORT:-1883}"

if [[ -z "$MQTT_HOST" ]]; then
  echo "[Orin] MQTT_HOST is not set. Provide it in $ENV_FILE or environment."
  exit 1
fi

echo "[Orin] Starting voice node"
echo "[Orin] Broker: ${MQTT_HOST}:${MQTT_PORT}"
echo "[Orin] STT: model=${STT_MODEL_SIZE:-small} device=${STT_DEVICE:-cuda} compute=${STT_COMPUTE_TYPE:-int8_float16}"
echo "[Orin] TTS: engine=${TTS_ENGINE:-kokoro} idle_timeout=${TTS_IDLE_TIMEOUT:-90}s"

PIDS=()

cleanup() {
  echo "[Orin] Stopping services..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

(
  cd "$ROOT_DIR"
  python3 -u -m brain.voice.transcriber
) &
PIDS+=("$!")

(
  cd "$ROOT_DIR"
  python3 -u -m brain.voice.speaker
) &
PIDS+=("$!")

wait -n "${PIDS[@]}"
