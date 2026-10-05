#!/usr/bin/env bash
# Jetson Orin: camera + vision pipeline (YOLO, faces, moondream VLM), publishing to the hub's broker.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/apps/brain-runtime/deploy/env/orin-vision.env}"

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
  echo "[Orin] MQTT_HOST is not set. Put the Mac Mini's IP in $ENV_FILE."
  exit 1
fi

VPY="${VISION_PYTHON:-python3}"
CMD=("$VPY" -u -m brain.vision.vision_service
  --location "${VISION_LOCATION:-office}"
  --camera "${VISION_CAMERA:-0}"
  --mqtt-host "$MQTT_HOST"
  --mqtt-port "$MQTT_PORT"
  --ollama-host "${VISION_OLLAMA_HOST:-http://localhost:11434}"
  --vlm-model "${VISION_VLM_MODEL:-moondream}"
  --vlm-interval "${VISION_VLM_INTERVAL:-75}"
  --yolo-model "${VISION_YOLO_MODEL:-yolov8n}"
  --yolo-interval "${VISION_YOLO_INTERVAL:-3}")
[[ "${VISION_NO_VLM:-0}" == "1" ]] && CMD+=(--no-vlm)
[[ "${VISION_NO_YOLO:-0}" == "1" ]] && CMD+=(--no-yolo)
[[ "${VISION_UI:-0}" == "1" ]] && CMD+=(--ui)

echo "[Orin] Starting vision node"
echo "[Orin] Broker: ${MQTT_HOST}:${MQTT_PORT}   camera: ${VISION_CAMERA:-0}   VLM: ${VISION_VLM_MODEL:-moondream} via ${VISION_OLLAMA_HOST:-http://localhost:11434}"
echo "[Orin] Preflight: ./sage nodecheck vision"
cd "$ROOT_DIR"
exec "${CMD[@]}"
