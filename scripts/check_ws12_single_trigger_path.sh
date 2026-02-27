#!/usr/bin/env bash
set -euo pipefail

echo "== WS12 Single Trigger Path Gate =="
echo "UTC: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo

mode_raw="${WEBHOOK_TRIGGER_MODE:-stats_ready_only}"
mode="$(printf '%s' "${mode_raw}" | tr '[:upper:]' '[:lower:]')"
ws_raw="${WS_ENABLED:-false}"
ws_enabled="$(printf '%s' "${ws_raw}" | tr '[:upper:]' '[:lower:]')"

fail_count=0

echo "[1] Local trigger-path policy"
echo "  WEBHOOK_TRIGGER_MODE=${mode}"
echo "  WS_ENABLED=${ws_enabled}"

if [[ "${mode}" != "stats_ready_only" ]]; then
  echo "  FAIL: WEBHOOK_TRIGGER_MODE must be stats_ready_only for W12 policy."
  fail_count=$((fail_count + 1))
fi

if [[ "${ws_enabled}" == "true" ]]; then
  echo "  FAIL: WS_ENABLED must be false (websocket path is deprecated/duplicate)."
  fail_count=$((fail_count + 1))
fi
echo

echo "[2] Remote deprecated-producer check (optional)"
if [[ -z "${SSH_HOST:-}" || -z "${SSH_USER:-}" || -z "${SSH_KEY_PATH:-}" ]]; then
  echo "  SKIP: SSH_HOST/SSH_USER/SSH_KEY_PATH not fully configured."
else
  if ! command -v ssh >/dev/null 2>&1; then
    echo "  FAIL: ssh command not available."
    fail_count=$((fail_count + 1))
  else
    ssh_port="${SSH_PORT:-22}"
    remote_output="$(
      ssh -o BatchMode=yes -o ConnectTimeout=10 \
        -p "${ssh_port}" \
        -i "${SSH_KEY_PATH}" \
        "${SSH_USER}@${SSH_HOST}" \
        'enabled=$(systemctl is-enabled et-stats-webhook.service 2>/dev/null || true);
         active=$(systemctl is-active et-stats-webhook.service 2>/dev/null || true);
         legacy_count=$(ps -ef | grep -E "stats_webhook_notify.py" | grep -v grep | wc -l);
         ws_count=$(ps -ef | grep -E "ws_notify_server.py" | grep -v grep | wc -l);
         echo "enabled:${enabled:-unknown}";
         echo "active:${active:-unknown}";
         echo "legacy_notifier_count:${legacy_count}";
         echo "ws_notify_server_count:${ws_count}"'
    )"

    echo "${remote_output}" | sed 's/^/  /'

    enabled_state="$(printf '%s\n' "${remote_output}" | awk -F: '/^enabled:/{print $2}' | tr -d '[:space:]')"
    active_state="$(printf '%s\n' "${remote_output}" | awk -F: '/^active:/{print $2}' | tr -d '[:space:]')"
    legacy_count="$(printf '%s\n' "${remote_output}" | awk -F: '/^legacy_notifier_count:/{print $2}' | tr -d '[:space:]')"
    ws_count="$(printf '%s\n' "${remote_output}" | awk -F: '/^ws_notify_server_count:/{print $2}' | tr -d '[:space:]')"

    if [[ "${enabled_state}" == "enabled" || "${active_state}" == "active" ]]; then
      echo "  FAIL: et-stats-webhook.service must be disabled/inactive."
      fail_count=$((fail_count + 1))
    fi

    if [[ -n "${legacy_count}" && "${legacy_count}" != "0" ]]; then
      echo "  FAIL: stats_webhook_notify.py is still running (${legacy_count})."
      fail_count=$((fail_count + 1))
    fi

    if [[ -n "${ws_count}" && "${ws_count}" != "0" ]]; then
      echo "  FAIL: ws_notify_server.py is still running (${ws_count})."
      fail_count=$((fail_count + 1))
    fi
  fi
fi
echo

if (( fail_count > 0 )); then
  echo "[FAIL] WS12 gate failed (${fail_count} issue(s))."
  exit 2
fi

echo "[PASS] WS12 gate passed."
