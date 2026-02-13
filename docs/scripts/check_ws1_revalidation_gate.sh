#!/usr/bin/env bash
set -euo pipefail

DB_HOST="${DB_HOST:-192.168.64.116}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-etlegacy_user}"
DB_NAME="${DB_NAME:-etlegacy}"
if [[ -z "${PGPASSWORD:-}" ]]; then
  echo "❌ PGPASSWORD is not set."
  echo "Set it explicitly before running, e.g.:"
  echo "  export PGPASSWORD='your_db_password'"
  exit 1
fi

PSQL=(psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F $'\t' -At -v ON_ERROR_STOP=1)

echo "== WS1 Revalidation Gate Snapshot =="
echo "UTC: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo

echo "[1] Latest R1/R2 rounds with Lua linkage"
"${PSQL[@]}" -c "
SELECT
  r.id,
  r.round_date,
  r.round_time,
  r.map_name,
  r.round_number,
  CASE WHEN l.id IS NULL THEN 'NO_LUA' ELSE 'HAS_LUA' END AS lua_status,
  COALESCE(l.captured_at::text, 'NULL') AS lua_captured_at,
  COALESCE(l.end_reason, 'NULL') AS lua_end_reason
FROM rounds r
LEFT JOIN lua_round_teams l ON l.round_id = r.id
WHERE r.round_number IN (1,2)
  AND to_date(r.round_date, 'YYYY-MM-DD') >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY r.id DESC
LIMIT 20;
"
echo

echo "[2] Map-pair readiness (requires R1+R2 both linked to Lua)"
"${PSQL[@]}" -c "
WITH map_pairs AS (
  SELECT
    r.round_date,
    r.match_id,
    r.map_name,
    MIN(r.id) FILTER (WHERE r.round_number = 1) AS r1_id,
    MIN(r.id) FILTER (WHERE r.round_number = 2) AS r2_id,
    COUNT(*) FILTER (WHERE r.round_number IN (1,2)) AS rounds_present,
    COUNT(*) FILTER (WHERE r.round_number = 1 AND l.id IS NOT NULL) AS r1_lua,
    COUNT(*) FILTER (WHERE r.round_number = 2 AND l.id IS NOT NULL) AS r2_lua,
    MAX(r.created_at) AS last_created_at
  FROM rounds r
  LEFT JOIN lua_round_teams l ON l.round_id = r.id
  WHERE r.round_number IN (1,2)
    AND to_date(r.round_date, 'YYYY-MM-DD') >= CURRENT_DATE - INTERVAL '7 days'
  GROUP BY r.round_date, r.match_id, r.map_name
)
SELECT
  round_date,
  match_id,
  map_name,
  r1_id,
  r2_id,
  rounds_present,
  r1_lua,
  r2_lua,
  CASE
    WHEN r1_id IS NOT NULL
      AND r2_id IS NOT NULL
      AND r1_lua = 1
      AND r2_lua = 1
    THEN 'READY'
    ELSE 'NOT_READY'
  END AS ws1_gate_pair_status
FROM map_pairs
ORDER BY last_created_at DESC
LIMIT 15;
"
echo

echo "[3] Most recent READY pair candidate"
"${PSQL[@]}" -c "
WITH map_pairs AS (
  SELECT
    r.round_date,
    r.match_id,
    r.map_name,
    MIN(r.id) FILTER (WHERE r.round_number = 1) AS r1_id,
    MIN(r.id) FILTER (WHERE r.round_number = 2) AS r2_id,
    COUNT(*) FILTER (WHERE r.round_number = 1 AND l.id IS NOT NULL) AS r1_lua,
    COUNT(*) FILTER (WHERE r.round_number = 2 AND l.id IS NOT NULL) AS r2_lua,
    MAX(r.created_at) AS last_created_at
  FROM rounds r
  LEFT JOIN lua_round_teams l ON l.round_id = r.id
  WHERE r.round_number IN (1,2)
    AND to_date(r.round_date, 'YYYY-MM-DD') >= CURRENT_DATE - INTERVAL '7 days'
  GROUP BY r.round_date, r.match_id, r.map_name
)
SELECT round_date, match_id, map_name, r1_id, r2_id
FROM map_pairs
WHERE r1_id IS NOT NULL
  AND r2_id IS NOT NULL
  AND r1_lua = 1
  AND r2_lua = 1
ORDER BY last_created_at DESC
LIMIT 1;
"

echo
echo "Done."
