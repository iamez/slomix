#!/usr/bin/env bash
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs/validation_runs"
mkdir -p "$LOG_DIR"

RUN_ID="$(date -u '+%Y%m%d_%H%M%S')"
LOG_FILE="$LOG_DIR/validation_bundle_${RUN_ID}.log"

exec > >(tee -a "$LOG_FILE") 2>&1

source_env_file() {
  local file_path="$1"
  if [[ -f "$file_path" ]]; then
    while IFS= read -r raw_line || [[ -n "$raw_line" ]]; do
      local line="${raw_line%$'\r'}"
      [[ -z "$line" ]] && continue
      [[ "$line" =~ ^[[:space:]]*# ]] && continue
      [[ "$line" =~ ^[[:space:]]*[A-Za-z_][A-Za-z0-9_]*= ]] || continue

      local key="${line%%=*}"
      local value="${line#*=}"
      key="${key#"${key%%[![:space:]]*}"}"
      key="${key%"${key##*[![:space:]]}"}"
      value="${value#"${value%%[![:space:]]*}"}"

      if [[ ! "$value" =~ ^\".*\"$ && ! "$value" =~ ^\'.*\'$ ]]; then
        value="${value%%[[:space:]]#*}"
        value="${value%"${value##*[![:space:]]}"}"
      fi

      if [[ "$value" =~ ^\".*\"$ ]]; then
        value="${value:1:${#value}-2}"
      elif [[ "$value" =~ ^\'.*\'$ ]]; then
        value="${value:1:${#value}-2}"
      fi
      export "$key=$value"
    done < "$file_path"
  fi
}

cd "$ROOT_DIR"
source_env_file "$ROOT_DIR/.env"
source_env_file "$ROOT_DIR/website/.env"

if [[ -z "${PGPASSWORD:-}" && -n "${POSTGRES_PASSWORD:-}" ]]; then
  export PGPASSWORD="$POSTGRES_PASSWORD"
fi

export DB_HOST="${DB_HOST:-${POSTGRES_HOST:-localhost}}"
export DB_PORT="${DB_PORT:-${POSTGRES_PORT:-5432}}"
export DB_USER="${DB_USER:-${POSTGRES_USER:-etlegacy_user}}"
export DB_NAME="${DB_NAME:-${POSTGRES_DATABASE:-etlegacy}}"

if [[ -n "${SSH_KEY_PATH:-}" && "${SSH_KEY_PATH}" == "~/"* ]]; then
  export SSH_KEY_PATH="${HOME}/${SSH_KEY_PATH#~/}"
fi

export MPLCONFIGDIR="${MPLCONFIGDIR:-/tmp/matplotlib}"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

pass_count=0
fail_count=0

run_step() {
  local label="$1"
  shift

  echo
  echo "== STEP: ${label} =="
  if "$@"; then
    echo "[PASS] ${label}"
    pass_count=$((pass_count + 1))
  else
    local exit_code=$?
    echo "[FAIL] ${label} (exit=${exit_code})"
    fail_count=$((fail_count + 1))
  fi
}

echo "Validation bundle start (UTC): $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Run id: ${RUN_ID}"
echo "Log file: ${LOG_FILE}"
echo "DB target: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "SSH target: ${SSH_USER:-unset}@${SSH_HOST:-unset}:${SSH_PORT:-unset}"

run_step "Python lint (ruff)" "$PYTHON_BIN" -m ruff check bot/ website/backend/
run_step "JavaScript lint" npm run lint:js

run_step "Targeted W04-W15 regression pytest" \
  "$PYTHON_BIN" -m pytest -q \
  tests/unit/test_round_contract.py \
  tests/unit/test_timing_end_reason_contracts.py \
  tests/unit/test_backfill_gametimes_contract.py \
  tests/unit/test_gametime_synthetic_round.py \
  tests/unit/test_webhook_round_metadata_service.py \
  tests/unit/test_lua_webhook_diagnostics.py \
  tests/unit/test_round_publisher_timing_dual.py \
  tests/unit/test_session_embed_builder_timing_dual.py \
  tests/unit/test_session_graph_generator_timing_dual.py \
  tests/unit/test_session_timing_shadow_service.py \
  tests/unit/test_timing_comparison_service_side_markers.py \
  tests/unit/test_timing_debug_service_session_join.py \
  tests/unit/test_round_correlation_service_guardrails.py \
  tests/unit/test_round_linkage_anomaly_service.py \
  tests/unit/test_round_linkage_diagnostics_api.py \
  tests/unit/test_proximity_objective_coords_gate.py \
  tests/unit/test_proximity_round_number_normalization.py \
  tests/unit/test_proximity_parser_objective_conflict.py \
  tests/unit/test_proximity_reaction_metrics_parser.py \
  tests/unit/test_proximity_lua_live_gating_guard.py \
  tests/unit/test_proximity_lua_mod_constants_guard.py \
  tests/unit/proximity_stats_guard_test.py \
  tests/unit/proximity_sprint_pipeline_test.py \
  tests/e2e/test_config_loading.py

run_step "Pipeline smoke" "$PYTHON_BIN" scripts/smoke_pipeline.py
run_step "WS12 single trigger path gate" bash scripts/check_ws12_single_trigger_path.sh
run_step "Round linkage anomaly gate" "$PYTHON_BIN" scripts/check_round_linkage_anomalies.py --fail-on-breach
run_step "Pipeline health report" "$PYTHON_BIN" scripts/pipeline_health_report.py -n "${PIPELINE_HEALTH_LIMIT:-30}"
run_step "WS11 objective coords gate" bash scripts/check_ws11_objective_coords_gate.sh
run_step "WS1/WS1C gate snapshot" bash scripts/check_ws1_ws1c_gates.sh
run_step "Proximity schema verification" "$PYTHON_BIN" scripts/verify_proximity_schema.py
run_step "Backfill gametimes dry-run audit" "$PYTHON_BIN" scripts/backfill_gametimes.py --dry-run --limit "${BACKFILL_DRYRUN_LIMIT:-50}"

echo
echo "Validation bundle finished (UTC): $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "Summary: pass=${pass_count} fail=${fail_count}"
echo "Log file: ${LOG_FILE}"

if (( fail_count > 0 )); then
  exit 2
fi

exit 0
