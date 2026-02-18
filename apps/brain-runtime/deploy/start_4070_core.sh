#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/apps/brain-runtime/deploy/env/rtx4070-core.env}"

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
START_VISION="${START_VISION:-1}"

if [[ -z "$MQTT_HOST" ]]; then
  echo "[RTX] MQTT_HOST is not set. Provide it in $ENV_FILE or environment."
  exit 1
fi

echo "[RTX] Starting brain node"
echo "[RTX] Broker: ${MQTT_HOST}:${MQTT_PORT}"
echo "[RTX] Vision: ${START_VISION}"

PIDS=()

cleanup() {
  echo "[RTX] Stopping services..."
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
  python3 -u brain/main.py
) &
PIDS+=("$!")

if [[ "$START_VISION" == "1" ]]; then
  VISION_LOCATION="${VISION_LOCATION:-office}"
  VISION_CAMERA="${VISION_CAMERA:-0}"
  VISION_VLM_MODEL="${VISION_VLM_MODEL:-moondream}"
  VISION_VLM_INTERVAL="${VISION_VLM_INTERVAL:-75}"
  VISION_YOLO_MODEL="${VISION_YOLO_MODEL:-yolov8n}"
  VISION_YOLO_INTERVAL="${VISION_YOLO_INTERVAL:-3}"

  VISION_CMD=(python3 -u -m brain.vision.vision_service
    --location "$VISION_LOCATION"
    --camera "$VISION_CAMERA"
    --mqtt-host "$MQTT_HOST"
    --mqtt-port "$MQTT_PORT"
    --vlm-model "$VISION_VLM_MODEL"
    --vlm-interval "$VISION_VLM_INTERVAL"
    --yolo-model "$VISION_YOLO_MODEL"
    --yolo-interval "$VISION_YOLO_INTERVAL")

  if [[ "${VISION_NO_VLM:-0}" == "1" ]]; then
    VISION_CMD+=(--no-vlm)
  fi
  if [[ "${VISION_NO_YOLO:-0}" == "1" ]]; then
    VISION_CMD+=(--no-yolo)
  fi
  if [[ "${VISION_UI:-0}" == "1" ]]; then
    VISION_CMD+=(--ui)
  fi

  (
    cd "$ROOT_DIR"
    "${VISION_CMD[@]}"
  ) &
  PIDS+=("$!")
fi

wait -n "${PIDS[@]}"
