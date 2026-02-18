#!/usr/bin/env bash
set -u -o pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT_DIR"

PYTHON_BIN="${PYTHON_BIN:-python}"
ARTIFACT_DIR="${ARTIFACT_DIR:-artifacts/ci}"
mkdir -p "$ARTIFACT_DIR"

STATUS=0
RUFF_BIN="${RUFF_BIN:-$(dirname "$PYTHON_BIN")/ruff}"
if [[ ! -x "$RUFF_BIN" ]]; then
  RUFF_BIN="$(command -v ruff 2>/dev/null || true)"
fi

run_step() {
  local name="$1"
  shift
  local log_file="$ARTIFACT_DIR/${name}.log"

  echo "==> ${name}" | tee "$log_file"
  if "$@" 2>&1 | tee -a "$log_file"; then
    echo "[PASS] ${name}" | tee -a "$log_file"
  else
    echo "[FAIL] ${name}" | tee -a "$log_file"
    STATUS=1
  fi
}

if [[ -n "${RUFF_BIN:-}" ]]; then
  run_step "lint" \
    "$RUFF_BIN" check apps/architect-studio shared tests \
    --select E9,F63,F7,F82
else
  echo "==> lint" | tee "$ARTIFACT_DIR/lint.log"
  echo "[FAIL] lint - ruff executable not found" | tee -a "$ARTIFACT_DIR/lint.log"
  STATUS=1
fi

run_step "py_compile" \
  "$PYTHON_BIN" scripts/ci/py_compile_check.py --output-list "$ARTIFACT_DIR/compiled_files.txt"

run_step "tests_architect" \
  "$PYTHON_BIN" -m unittest discover -s tests -p "test_architect_*.py" -v

if [[ "$STATUS" -eq 0 ]]; then
  echo "status=success" > "$ARTIFACT_DIR/summary.txt"
  echo "All Architect CI checks passed." | tee -a "$ARTIFACT_DIR/summary.txt"
else
  echo "status=failure" > "$ARTIFACT_DIR/summary.txt"
  echo "One or more Architect CI checks failed. See logs in $ARTIFACT_DIR." | tee -a "$ARTIFACT_DIR/summary.txt"
fi

exit "$STATUS"
