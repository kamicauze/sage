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

MLX_BASE_URL="${MLX_HOST:-http://127.0.0.1:8080}"
MLX_MODEL="${MLX_MODEL_MID:-${MLX_MODEL_FAST:-mlx-community/Qwen2.5-14B-Instruct-4bit}}"
MLX_FAST_BASE_URL="${MLX_HOST_FAST:-}"
MLX_FAST_MODEL="${MLX_MODEL_FAST:-}"
MLX_HEALTH_PATH="${MLX_HEALTH_ENDPOINT:-/v1/models}"
if [[ "${MLX_HEALTH_PATH:0:1}" != "/" ]]; then
  MLX_HEALTH_PATH="/$MLX_HEALTH_PATH"
fi

declare -a MLX_PIDS=()

parse_bind() {
  local base_url="$1"
  local default_port="$2"
  local bind host port
  bind="${base_url#http://}"
  bind="${bind#https://}"
  bind="${bind%%/*}"
  host="${bind%%:*}"
  port="${bind##*:}"
  if [[ "$host" == "$port" ]]; then
    port="$default_port"
  fi
  echo "$host:$port"
}

is_local_host() {
  local host="$1"
  case "$host" in
    127.0.0.1|localhost|0.0.0.0|::1)
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

start_mlx_server() {
  local label="$1"
  local base_url="$2"
  local model="$3"
  local log_file="$4"
  local default_port="$5"
  local bind host port pid ready

  if [[ -z "$model" ]]; then
    return 0
  fi

  bind="$(parse_bind "$base_url" "$default_port")"
  host="${bind%%:*}"
  port="${bind##*:}"

  echo "[MacMini] ${label} endpoint: ${base_url}${MLX_HEALTH_PATH}"
  echo "[MacMini] ${label} model: ${model}"

  # Remote endpoints are supported for tier offload (e.g., fast tier on MacBook).
  # In that case, we only health-check and never try to launch a local server.
  if ! is_local_host "$host"; then
    if curl -fsS -m 2 "${base_url}${MLX_HEALTH_PATH}" >/dev/null 2>&1; then
      echo "[MacMini] ${label} reachable (remote host: ${host})"
      return 0
    fi
    echo "[MacMini] WARNING: ${label} is configured on remote host ${host} but is not reachable yet."
    echo "[MacMini]          Start it there before using that tier."
    return 0
  fi

  if curl -fsS -m 2 "${base_url}${MLX_HEALTH_PATH}" >/dev/null 2>&1; then
    echo "[MacMini] ${label} already running"
    return 0
  fi

  echo "[MacMini] Starting ${label}..."
  mlx_lm.server \
    --model "$model" \
    --host "$host" \
    --port "$port" \
    > "$log_file" 2>&1 &
  pid="$!"
  MLX_PIDS+=("$pid")

  ready=0
  for _ in {1..180}; do
    if curl -fsS -m 2 "${base_url}${MLX_HEALTH_PATH}" >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 1
  done

  if [[ "$ready" -ne 1 ]]; then
    echo "[MacMini] ERROR: ${label} did not become healthy in time."
    echo "[MacMini] Check logs: ${log_file}"
    exit 1
  fi
  echo "[MacMini] ${label} ready"
}

cleanup() {
  local pid
  for pid in "${MLX_PIDS[@]}"; do
    if kill -0 "$pid" >/dev/null 2>&1; then
      echo "[MacMini] Stopping MLX server (pid=$pid)"
      kill "$pid" >/dev/null 2>&1 || true
      wait "$pid" 2>/dev/null || true
    fi
  done
}
trap cleanup EXIT INT TERM

echo "[MacMini] All-in-one startup"
echo "[MacMini] Env file: $ENV_FILE"

start_mlx_server "MLX main" "$MLX_BASE_URL" "$MLX_MODEL" "/tmp/sage_mlx.log" "8080"

if [[ -n "$MLX_FAST_BASE_URL" ]] && [[ -n "$MLX_FAST_MODEL" ]]; then
  if [[ "$MLX_FAST_BASE_URL" == "$MLX_BASE_URL" ]] && [[ "$MLX_FAST_MODEL" == "$MLX_MODEL" ]]; then
    echo "[MacMini] MLX fast host/model matches main; skipping secondary server"
  else
    start_mlx_server "MLX fast" "$MLX_FAST_BASE_URL" "$MLX_FAST_MODEL" "/tmp/sage_mlx_fast.log" "8081"
  fi
fi

cd "$ROOT_DIR"
python3 -u sage.py pwa --no-stt --no-tts --brain-logs --api-logs "$@"
