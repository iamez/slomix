#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  echo "[error] .env is required for prod startup"
  exit 1
fi

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

      # Remove inline comments in unquoted values (e.g. PORT=7000  # note).
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

source_env_file "$ROOT_DIR/.env"
source_env_file "$ROOT_DIR/website/.env"

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/website/requirements.txt"
fi

export WEBSITE_HOST="${WEBSITE_HOST:-0.0.0.0}"
export WEBSITE_PORT="${WEBSITE_PORT:-7000}"
export DATABASE_TYPE="${DATABASE_TYPE:-postgresql}"
export CACHE_BACKEND="${CACHE_BACKEND:-redis}"
export SESSION_SECRET="${SESSION_SECRET:-}"
export SQLITE_DB_PATH="${SQLITE_DB_PATH:-bot/etlegacy_production.db}"
export GREATSHOT_STARTUP_ENABLED="${GREATSHOT_STARTUP_ENABLED:-true}"

: "${SESSION_SECRET:?SESSION_SECRET is required}"
: "${DISCORD_BOT_TOKEN:?DISCORD_BOT_TOKEN is required}"
: "${POSTGRES_HOST:?POSTGRES_HOST is required}"
: "${POSTGRES_PORT:?POSTGRES_PORT is required}"
: "${POSTGRES_DATABASE:?POSTGRES_DATABASE is required}"
: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}"

WEB_PID=""
BOT_PID=""

cleanup() {
  if [[ -n "$WEB_PID" ]] && kill -0 "$WEB_PID" 2>/dev/null; then
    kill "$WEB_PID" 2>/dev/null || true
    sleep 0.3
    kill -9 "$WEB_PID" 2>/dev/null || true
  fi
  if [[ -n "$BOT_PID" ]] && kill -0 "$BOT_PID" 2>/dev/null; then
    kill "$BOT_PID" 2>/dev/null || true
    sleep 0.3
    kill -9 "$BOT_PID" 2>/dev/null || true
  fi
  # Best-effort cleanup of background children started by this script.
  pkill -P "$$" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

"$PYTHON_BIN" -m uvicorn website.backend.main:app --host "$WEBSITE_HOST" --port "$WEBSITE_PORT" >>"$LOG_DIR/web.log" 2>>"$LOG_DIR/errors.log" &
WEB_PID=$!

"$PYTHON_BIN" bot/ultimate_bot.py >>"$LOG_DIR/bot.log" 2>>"$LOG_DIR/errors.log" &
BOT_PID=$!

HEALTH_OK=0
if [[ "${SKIP_HEALTHCHECK:-0}" == "1" ]]; then
  HEALTH_OK=1
elif command -v curl >/dev/null 2>&1; then
  for _ in $(seq 1 40); do
    if curl -fsS "http://127.0.0.1:${WEBSITE_PORT}/health" >/dev/null; then
      HEALTH_OK=1
      break
    fi
    sleep 1
  done
else
  HEALTH_OK=1
fi

if [[ "$HEALTH_OK" != "1" ]]; then
  echo "[error] web health check failed at http://127.0.0.1:${WEBSITE_PORT}/health"
  exit 1
fi

echo "[ok] services started: web=${WEB_PID} bot=${BOT_PID}"

set +e
wait -n "$WEB_PID" "$BOT_PID"
EXIT_CODE=$?
set -e

echo "[error] a service exited (code=$EXIT_CODE). See logs/web.log, logs/bot.log, logs/errors.log"
exit "$EXIT_CODE"
