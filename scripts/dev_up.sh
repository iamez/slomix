#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_DIR="$ROOT_DIR/logs"
mkdir -p "$LOG_DIR"

# Preserve explicit CLI/session overrides before loading .env files.
BOT_VALIDATE_ONLY_OVERRIDE_SET=0
DISCORD_TOKEN_OVERRIDE_SET=0
if [[ "${BOT_STARTUP_VALIDATE_ONLY+x}" == "x" ]]; then
  BOT_VALIDATE_ONLY_OVERRIDE_SET=1
  BOT_VALIDATE_ONLY_OVERRIDE="$BOT_STARTUP_VALIDATE_ONLY"
fi
if [[ "${DISCORD_BOT_TOKEN+x}" == "x" ]]; then
  DISCORD_TOKEN_OVERRIDE_SET=1
  DISCORD_TOKEN_OVERRIDE="$DISCORD_BOT_TOKEN"
fi

if [[ ! -f "$ROOT_DIR/.env" ]]; then
  cp "$ROOT_DIR/.env.example" "$ROOT_DIR/.env"
  echo "[info] created .env from .env.example"
fi
if [[ ! -f "$ROOT_DIR/website/.env" ]]; then
  cp "$ROOT_DIR/website/.env.example" "$ROOT_DIR/website/.env"
  echo "[info] created website/.env from website/.env.example"
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

# Re-apply explicit CLI/session overrides (higher priority than .env values).
if [[ "$BOT_VALIDATE_ONLY_OVERRIDE_SET" == "1" ]]; then
  export BOT_STARTUP_VALIDATE_ONLY="$BOT_VALIDATE_ONLY_OVERRIDE"
fi
if [[ "$DISCORD_TOKEN_OVERRIDE_SET" == "1" ]]; then
  export DISCORD_BOT_TOKEN="$DISCORD_TOKEN_OVERRIDE"
fi

PYTHON_BIN="${PYTHON_BIN:-$ROOT_DIR/venv/bin/python}"
if [[ ! -x "$PYTHON_BIN" ]]; then
  PYTHON_BIN="$(command -v python3)"
fi

if [[ "${SKIP_INSTALL:-0}" != "1" ]]; then
  "$PYTHON_BIN" -m pip install -r "$ROOT_DIR/requirements.txt" -r "$ROOT_DIR/website/requirements.txt"
fi

# Local/dev defaults are intentionally explicit to avoid accidentally reusing
# production-like values from .env (e.g. remote PostgreSQL endpoints).
export WEBSITE_HOST="${DEV_WEBSITE_HOST:-0.0.0.0}"
export WEBSITE_PORT="${DEV_WEBSITE_PORT:-7000}"
export DATABASE_TYPE="${DEV_DATABASE_TYPE:-sqlite}"
export CACHE_BACKEND="${DEV_CACHE_BACKEND:-memory}"
export SESSION_SECRET="${SESSION_SECRET:-dev-session-secret-change-me}"
export SQLITE_DB_PATH="${DEV_SQLITE_DB_PATH:-bot/etlegacy_production.db}"
export GREATSHOT_STARTUP_ENABLED="${DEV_GREATSHOT_STARTUP_ENABLED:-false}"

if [[ -z "${DISCORD_BOT_TOKEN:-}" ]]; then
  export BOT_STARTUP_VALIDATE_ONLY="true"
  echo "[info] DISCORD_BOT_TOKEN not set; running bot in BOT_STARTUP_VALIDATE_ONLY mode"
fi
BOT_VALIDATE_ONLY="${BOT_STARTUP_VALIDATE_ONLY:-false}"

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

if [[ "$BOT_VALIDATE_ONLY" == "true" || "$BOT_VALIDATE_ONLY" == "1" ]]; then
  if ! "$PYTHON_BIN" bot/ultimate_bot.py >>"$LOG_DIR/bot.log" 2>>"$LOG_DIR/errors.log"; then
    echo "[error] bot startup validation failed; see logs/bot.log and logs/errors.log"
    exit 1
  fi
  echo "[ok] bot startup validation passed"
else
  "$PYTHON_BIN" bot/ultimate_bot.py >>"$LOG_DIR/bot.log" 2>>"$LOG_DIR/errors.log" &
  BOT_PID=$!
fi

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

if [[ -n "$BOT_PID" ]]; then
  echo "[ok] services started: web=${WEB_PID} bot=${BOT_PID}"
else
  echo "[ok] web service started: web=${WEB_PID}"
fi

set +e
if [[ -n "$BOT_PID" ]]; then
  wait -n "$WEB_PID" "$BOT_PID"
  EXIT_CODE=$?
else
  wait "$WEB_PID"
  EXIT_CODE=$?
fi
set -e

echo "[error] a service exited (code=$EXIT_CODE). See logs/web.log, logs/bot.log, logs/errors.log"
exit "$EXIT_CODE"
