#!/usr/bin/env bash
set -euo pipefail

DB_HOST=""
DB_PORT=""
DB_USER=""
DB_PASSWORD=""
DB_NAME=""

usage() {
  cat <<'EOF'
Stage 4 live verification helper (non-sandbox host).

Usage:
  docs/reports/stage4_live_verification.sh preflight
  docs/reports/stage4_live_verification.sh latest [limit]
  docs/reports/stage4_live_verification.sh campaign <campaign_id>
  docs/reports/stage4_live_verification.sh help

Commands:
  preflight          Validate psql + DB connectivity + read access checks.
  latest [limit]     Show latest campaign rows (default limit: 10).
  campaign <id>      Show campaign row + jobs + send logs for one campaign.

Environment resolution order:
  1) POSTGRES_HOST / POSTGRES_PORT / POSTGRES_USER / POSTGRES_PASSWORD / POSTGRES_DATABASE
  2) PGHOST / PGPORT / PGUSER / PGPASSWORD / PGDATABASE

Notes:
  - Run this on a live-like/non-sandbox host with DB network access.
  - Queries are read-only evidence checks.

Examples:
  docs/reports/stage4_live_verification.sh preflight
  docs/reports/stage4_live_verification.sh latest
  docs/reports/stage4_live_verification.sh latest 5
  docs/reports/stage4_live_verification.sh campaign 42
EOF
}

die() {
  echo "[error] $*" >&2
  exit 1
}

require_command() {
  local name="$1"
  command -v "$name" >/dev/null 2>&1 || die "required command not found: $name"
}

resolve_db_env() {
  DB_HOST="${POSTGRES_HOST:-${PGHOST:-}}"
  DB_PORT="${POSTGRES_PORT:-${PGPORT:-5432}}"
  DB_USER="${POSTGRES_USER:-${PGUSER:-}}"
  DB_PASSWORD="${POSTGRES_PASSWORD:-${PGPASSWORD:-}}"
  DB_NAME="${POSTGRES_DATABASE:-${PGDATABASE:-}}"
}

validate_db_env() {
  [[ -n "$DB_HOST" ]] || die "missing POSTGRES_HOST/PGHOST"
  [[ -n "$DB_PORT" ]] || die "missing POSTGRES_PORT/PGPORT"
  [[ "$DB_PORT" =~ ^[0-9]+$ ]] || die "POSTGRES_PORT/PGPORT must be numeric"
  [[ -n "$DB_USER" ]] || die "missing POSTGRES_USER/PGUSER"
  [[ -n "$DB_NAME" ]] || die "missing POSTGRES_DATABASE/PGDATABASE"
}

setup_db() {
  require_command psql
  resolve_db_env
  validate_db_env
}

psql_query() {
  local sql="$1"

  if [[ -n "$DB_PASSWORD" ]]; then
    PGPASSWORD="$DB_PASSWORD" psql \
      -X \
      -w \
      -h "$DB_HOST" \
      -p "$DB_PORT" \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      -v ON_ERROR_STOP=1 \
      -F $'\t' \
      -P pager=off \
      -c "$sql"
  else
    psql \
      -X \
      -w \
      -h "$DB_HOST" \
      -p "$DB_PORT" \
      -U "$DB_USER" \
      -d "$DB_NAME" \
      -v ON_ERROR_STOP=1 \
      -F $'\t' \
      -P pager=off \
      -c "$sql"
  fi
}

print_section() {
  echo
  echo "== $* =="
}

preflight_checks() {
  echo "[info] verifying Stage 4 DB evidence prerequisites"
  echo "[info] host=$DB_HOST port=$DB_PORT user=$DB_USER db=$DB_NAME"

  print_section "Database connectivity"
  psql_query "SELECT now() AS db_time;"

  print_section "Promotion evidence table checks"
  psql_query "
SELECT table_name,
       to_regclass(format('public.%I', table_name)) IS NOT NULL AS table_exists,
       has_table_privilege(current_user, format('public.%I', table_name), 'SELECT') AS can_select
FROM (VALUES
  ('availability_promotion_campaigns'),
  ('availability_promotion_jobs'),
  ('availability_promotion_send_logs')
) AS t(table_name);"

  echo
  echo "[ok] preflight checks completed"
}

latest_campaigns() {
  local limit="$1"

  print_section "Latest campaigns (limit=$limit)"
  psql_query "
SELECT id, campaign_date, status, recipient_count, created_at, updated_at
FROM availability_promotion_campaigns
ORDER BY id DESC
LIMIT ${limit};"
}

campaign_details() {
  local campaign_id="$1"

  print_section "Campaign"
  psql_query "
SELECT id, campaign_date, status, recipient_count, created_at, updated_at
FROM availability_promotion_campaigns
WHERE id = ${campaign_id};"

  print_section "Jobs"
  psql_query "
SELECT campaign_id, job_type, status, attempts, max_attempts, run_at, sent_at, last_error
FROM availability_promotion_jobs
WHERE campaign_id = ${campaign_id}
ORDER BY job_type;"

  print_section "Send logs"
  psql_query "
SELECT campaign_id, job_id, user_id, channel_type, status, message_id, error, created_at
FROM availability_promotion_send_logs
WHERE campaign_id = ${campaign_id}
ORDER BY created_at ASC;"
}

main() {
  local command="${1:-help}"

  case "$command" in
    help|-h|--help)
      usage
      ;;
    preflight)
      setup_db
      preflight_checks
      ;;
    latest)
      setup_db
      local limit="${2:-10}"
      if ! [[ "$limit" =~ ^[0-9]+$ ]]; then
        die "limit must be numeric"
      fi
      latest_campaigns "$limit"
      ;;
    campaign)
      setup_db
      if [[ $# -lt 2 ]]; then
        echo "[error] missing campaign_id" >&2
        usage
        exit 1
      fi
      if ! [[ "$2" =~ ^[0-9]+$ ]]; then
        die "campaign_id must be numeric"
      fi
      campaign_details "$2"
      ;;
    *)
      echo "[error] unknown command: $command" >&2
      usage
      exit 1
      ;;
  esac
}

main "$@"
