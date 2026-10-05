#!/usr/bin/env bash
# Mac Mini hub: Mosquitto broker (LAN + websocket listeners) + voice switch controller.
# Later the LLM brain (brain/main.py) also runs here.
# Written for macOS's stock bash 3.2: no `wait -n`, no `set -u` with empty arrays.
set -eo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
ENV_FILE="${1:-$ROOT_DIR/apps/brain-runtime/deploy/env/mini-hub.env}"

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

MQTT_PORT="${MQTT_PORT:-1883}"
SAGE_SKIP_BROKER="${SAGE_SKIP_BROKER:-0}"
SAGE_MQTT_CONFIG="${SAGE_MQTT_CONFIG:-$ROOT_DIR/mosquitto.conf}"
SAGE_SWITCH_CONTROLLER="${SAGE_SWITCH_CONTROLLER:-1}"

PIDS=()

cleanup() {
  echo "[Hub] Stopping services..."
  for pid in ${PIDS[@]}; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

lan_ip() {
  ipconfig getifaddr en0 2>/dev/null || ipconfig getifaddr en1 2>/dev/null || \
    (hostname -I 2>/dev/null | awk '{print $1}') || echo "?"
}

find_mosquitto() {
  command -v mosquitto 2>/dev/null && return
  for p in /opt/homebrew/sbin/mosquitto /usr/local/sbin/mosquitto /usr/sbin/mosquitto; do
    if [[ -x "$p" ]]; then echo "$p"; return; fi
  done
}

if [[ "$SAGE_SKIP_BROKER" != "1" ]]; then
  if pgrep -x mosquitto >/dev/null 2>&1; then
    echo "[Hub] Mosquitto is already running; not starting another."
    echo "[Hub] If it came from 'brew services', its default config may listen on localhost only."
    echo "[Hub] Check with: ./sage nodecheck hub   (fix: brew services stop mosquitto, then rerun this script)"
  else
    MOSQ="$(find_mosquitto)"
    if [[ -z "$MOSQ" ]]; then
      echo "[Hub] mosquitto not found. Install it: brew install mosquitto"
      exit 1
    fi
    echo "[Hub] Starting Mosquitto with $SAGE_MQTT_CONFIG"
    "$MOSQ" -c "$SAGE_MQTT_CONFIG" &
    PIDS+=("$!")
    sleep 1
    if ! kill -0 "${PIDS[0]}" >/dev/null 2>&1; then
      echo "[Hub] Mosquitto exited immediately. Debug with: $MOSQ -c $SAGE_MQTT_CONFIG -v"
      exit 1
    fi
  fi
fi

if [[ "$SAGE_SWITCH_CONTROLLER" == "1" ]]; then
  echo "[Hub] Starting switch controller (sage/voice/transcript -> zigbee2mqtt/<panel>/set)"
  (
    cd "$ROOT_DIR"
    MQTT_HOST=localhost MQTT_PORT="$MQTT_PORT" python3 -u -m brain.devices.switch_controller
  ) &
  PIDS+=("$!")
fi

echo "[Hub] Ready. Other nodes use MQTT_HOST=$(lan_ip) MQTT_PORT=$MQTT_PORT"
echo "[Hub] See every node's status: ./sage nodecheck --list"

if [[ ${#PIDS[@]} -eq 0 ]]; then
  echo "[Hub] Nothing started by this script. Waiting for Ctrl+C."
  while true; do sleep 3600; done
fi

# Exit (and clean up the rest) as soon as any service dies.
while true; do
  for pid in ${PIDS[@]}; do
    if ! kill -0 "$pid" >/dev/null 2>&1; then
      echo "[Hub] A service (pid $pid) exited."
      exit 1
    fi
  done
  sleep 2
done
