#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE_DEFAULT="$ROOT_DIR/apps/brain-runtime/deploy/env/local-4070-test.env"
ENV_FILE="${SAGE_ENV_FILE:-$ENV_FILE_DEFAULT}"

MODULE="${1:-}"  # brain|stt|tts|voice|vision|core|pwa
if [[ -z "$MODULE" ]]; then
  echo "Usage: bash apps/brain-runtime/deploy/start_4070_lab.sh <brain|stt|tts|voice|vision|core|pwa>"
  exit 1
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

MQTT_HOST="${MQTT_HOST:-localhost}"
MQTT_PORT="${MQTT_PORT:-1883}"
SAGE_SKIP_BROKER="${SAGE_SKIP_BROKER:-0}"
SAGE_MQTT_CONFIG="${SAGE_MQTT_CONFIG:-$ROOT_DIR/mosquitto.conf}"

PIDS=()

cleanup() {
  echo "[LAB] Stopping services..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

ensure_local_broker() {
  if [[ "$SAGE_SKIP_BROKER" == "1" ]]; then
    return
  fi

  if [[ "$MQTT_HOST" != "localhost" && "$MQTT_HOST" != "127.0.0.1" ]]; then
    # Remote broker profile.
    return
  fi

  if pgrep -f "mosquitto" >/dev/null 2>&1; then
    echo "[LAB] Mosquitto already running"
    return
  fi

  if [[ -f "$SAGE_MQTT_CONFIG" ]]; then
    echo "[LAB] Starting mosquitto with $SAGE_MQTT_CONFIG"
    mosquitto -c "$SAGE_MQTT_CONFIG" &
  else
    echo "[LAB] Starting mosquitto on ${MQTT_PORT}"
    mosquitto -p "$MQTT_PORT" &
  fi
  PIDS+=("$!")
  sleep 1
}

start_bg() {
  local label="$1"
  shift
  echo "[LAB] Starting ${label}: $*"
  (cd "$ROOT_DIR" && "$@") &
  PIDS+=("$!")
}

run_fg() {
  local label="$1"
  shift
  echo "[LAB] Running ${label}: $*"
  cd "$ROOT_DIR"
  "$@"
}

vision_python() {
  if [[ -n "${VISION_PYTHON:-}" ]]; then
    echo "$VISION_PYTHON"
    return
  fi

  if [[ -x "$ROOT_DIR/.venv-vision/bin/python3" ]]; then
    echo "$ROOT_DIR/.venv-vision/bin/python3"
    return
  fi

  echo "python3"
}

run_vision_service() {
  local vpy
  vpy="$(vision_python)"

  local location camera vlm_model vlm_interval yolo_model yolo_interval
  location="${VISION_LOCATION:-office}"
  camera="${VISION_CAMERA:-0}"
  vlm_model="${VISION_VLM_MODEL:-moondream}"
  vlm_interval="${VISION_VLM_INTERVAL:-75}"
  yolo_model="${VISION_YOLO_MODEL:-yolov8n}"
  yolo_interval="${VISION_YOLO_INTERVAL:-3}"

  local cmd=("$vpy" -u -m brain.vision.vision_service
    --location "$location"
    --camera "$camera"
    --mqtt-host "$MQTT_HOST"
    --mqtt-port "$MQTT_PORT"
    --vlm-model "$vlm_model"
    --vlm-interval "$vlm_interval"
    --yolo-model "$yolo_model"
    --yolo-interval "$yolo_interval")

  if [[ "${VISION_NO_VLM:-0}" == "1" ]]; then
    cmd+=(--no-vlm)
  fi
  if [[ "${VISION_NO_YOLO:-0}" == "1" ]]; then
    cmd+=(--no-yolo)
  fi
  if [[ "${VISION_UI:-0}" == "1" ]]; then
    cmd+=(--ui)
  fi

  run_fg "vision" "${cmd[@]}"
}

echo "[LAB] Module: $MODULE"
echo "[LAB] MQTT: ${MQTT_HOST}:${MQTT_PORT}"

case "$MODULE" in
  brain)
    ensure_local_broker
    run_fg "brain" python3 -u brain/main.py
    ;;
  stt)
    ensure_local_broker
    run_fg "stt" python3 -u -m brain.voice.transcriber
    ;;
  tts)
    ensure_local_broker
    run_fg "tts" python3 -u -m brain.voice.speaker
    ;;
  voice)
    ensure_local_broker
    start_bg "stt" python3 -u -m brain.voice.transcriber
    start_bg "tts" python3 -u -m brain.voice.speaker
    wait -n "${PIDS[@]}"
    ;;
  vision)
    ensure_local_broker
    run_vision_service
    ;;
  core)
    ensure_local_broker
    start_bg "brain" python3 -u brain/main.py
    start_bg "vision" "$(vision_python)" -u -m brain.vision.vision_service \
      --location "${VISION_LOCATION:-office}" \
      --camera "${VISION_CAMERA:-0}" \
      --mqtt-host "$MQTT_HOST" \
      --mqtt-port "$MQTT_PORT" \
      --vlm-model "${VISION_VLM_MODEL:-moondream}" \
      --vlm-interval "${VISION_VLM_INTERVAL:-75}" \
      --yolo-model "${VISION_YOLO_MODEL:-yolov8n}" \
      --yolo-interval "${VISION_YOLO_INTERVAL:-3}"
    wait -n "${PIDS[@]}"
    ;;
  pwa)
    # Use existing orchestrator; it already binds UI on 0.0.0.0 for phone access.
    run_fg "pwa" python3 -u sage.py pwa --brain-logs
    ;;
  *)
    echo "Unknown module: $MODULE"
    echo "Usage: bash apps/brain-runtime/deploy/start_4070_lab.sh <brain|stt|tts|voice|vision|core|pwa>"
    exit 1
    ;;
esac
