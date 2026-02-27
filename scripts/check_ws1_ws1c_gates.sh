#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${PGPASSWORD:-}" ]]; then
  echo "PGPASSWORD is not set. Export it before running this script."
  echo "Example: export PGPASSWORD='your_db_password'"
  exit 1
fi

DB_HOST="${DB_HOST:-192.168.64.116}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-etlegacy_user}"
DB_NAME="${DB_NAME:-etlegacy}"

echo "== WS1/WS1C Gate Snapshot =="
echo "UTC: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo

echo "[1] Lua table baseline (WS1)"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F $'\t' -Atc "
SELECT
  COUNT(*) AS lua_total,
  COUNT(*) FILTER (WHERE round_id IS NULL) AS lua_unlinked,
  COALESCE(MAX(captured_at)::text,'NULL') AS latest_captured_at
FROM lua_round_teams;
"
echo

echo "[2] Round coverage vs Lua linkage (last 3 days)"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F $'\t' -Atc "
SELECT
  r.round_date,
  COUNT(*) AS rounds_total,
  COUNT(*) FILTER (WHERE l.id IS NULL) AS rounds_without_lua
FROM rounds r
LEFT JOIN lua_round_teams l ON l.round_id = r.id
WHERE r.round_number IN (1,2)
  AND r.round_date >= to_char(CURRENT_DATE - INTERVAL '3 days', 'YYYY-MM-DD')
GROUP BY r.round_date
ORDER BY r.round_date DESC;
"
echo

echo "[3] Webhook store signals (last 20 lines)"
if [[ -f logs/webhook.log ]]; then
  rg -n "Stored Lua round data|Could not store Lua team data: the server expects 24 arguments" logs/webhook.log | tail -n 20 || true
else
  echo "logs/webhook.log not found"
fi
echo

echo "[4] Sprint distribution (WS1C-004)"
psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -F $'\t' -Atc "
SELECT
  session_date,
  COUNT(*) AS tracks,
  COUNT(*) FILTER (WHERE sprint_percentage > 0) AS nonzero_sprint_pct,
  ROUND(MIN(sprint_percentage)::numeric,2) AS min_pct,
  ROUND(MAX(sprint_percentage)::numeric,2) AS max_pct,
  ROUND(AVG(sprint_percentage)::numeric,2) AS avg_pct,
  COUNT(*) FILTER (
    WHERE EXISTS (
      SELECT 1
      FROM jsonb_array_elements(path) e
      WHERE (e->>'sprint')::int = 1
    )
  ) AS tracks_with_sprint1
FROM player_track
WHERE session_date >= DATE '2026-02-11'
GROUP BY session_date
ORDER BY session_date DESC;
"
echo

echo "Done."
