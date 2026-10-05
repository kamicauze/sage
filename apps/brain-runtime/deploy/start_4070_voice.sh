#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/apps/brain-runtime/deploy/env/rtx4070-voice.env}"

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
  echo "[4070] MQTT_HOST is not set. Provide it in $ENV_FILE or environment."
  exit 1
fi

echo "[4070] Starting voice node"
echo "[4070] Broker: ${MQTT_HOST}:${MQTT_PORT}"
echo "[4070] STT: model=${STT_MODEL_SIZE:-medium.en} device=${STT_DEVICE:-cuda} compute=${STT_COMPUTE_TYPE:-float16}"
echo "[4070] TTS: engine=${TTS_ENGINE:-kokoro} idle_timeout=${TTS_IDLE_TIMEOUT:-300}s prewarm=${TTS_PREWARM:-false}"

PIDS=()

cleanup() {
  echo "[4070] Stopping services..."
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
