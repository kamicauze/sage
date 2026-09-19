#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/apps/brain-runtime/deploy/env/pi5-controller.env}"

if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck source=/dev/null
  source "$ENV_FILE"
  set +a
fi

MQTT_PORT="${MQTT_PORT:-1883}"
SAGE_SKIP_BROKER="${SAGE_SKIP_BROKER:-0}"
SAGE_MQTT_CONFIG="${SAGE_MQTT_CONFIG:-$ROOT_DIR/mosquitto.conf}"
SAGE_SENSOR_CMD="${SAGE_SENSOR_CMD:-}"
SAGE_SWITCH_CONTROLLER="${SAGE_SWITCH_CONTROLLER:-1}"   # voice -> Zigbee2MQTT switch controller

PIDS=()

cleanup() {
  echo "[Pi5] Stopping services..."
  for pid in "${PIDS[@]:-}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}

trap cleanup EXIT INT TERM

if [[ "$SAGE_SKIP_BROKER" != "1" ]]; then
  if pgrep -f "mosquitto" >/dev/null 2>&1; then
    echo "[Pi5] Mosquitto is already running."
  else
    if [[ -f "$SAGE_MQTT_CONFIG" ]]; then
      echo "[Pi5] Starting mosquitto with config: $SAGE_MQTT_CONFIG"
      mosquitto -c "$SAGE_MQTT_CONFIG" &
    else
      echo "[Pi5] Starting mosquitto on port ${MQTT_PORT}"
      mosquitto -p "$MQTT_PORT" &
    fi
    PIDS+=("$!")
  fi
fi

echo "[Pi5] Sensor controller ready"
echo "[Pi5] MQTT port: ${MQTT_PORT}"

if [[ "$SAGE_SWITCH_CONTROLLER" == "1" ]]; then
  if [[ -d "$ROOT_DIR/.venv" ]]; then
    # shellcheck source=/dev/null
    source "$ROOT_DIR/.venv/bin/activate"
  fi
  echo "[Pi5] Starting switch controller (sage/voice/transcript -> zigbee2mqtt/<panel>/set)"
  (
    cd "$ROOT_DIR"
    MQTT_HOST="${MQTT_HOST:-localhost}" MQTT_PORT="$MQTT_PORT" python3 -u -m brain.devices.switch_controller
  ) &
  PIDS+=("$!")
fi

if [[ -n "$SAGE_SENSOR_CMD" ]]; then
  echo "[Pi5] Starting sensor command: $SAGE_SENSOR_CMD"
  bash -lc "$SAGE_SENSOR_CMD" &
  PIDS+=("$!")
fi

if [[ ${#PIDS[@]} -eq 0 ]]; then
  echo "[Pi5] Nothing started by script. Waiting for Ctrl+C."
  while true; do sleep 3600; done
fi

wait -n "${PIDS[@]}"
