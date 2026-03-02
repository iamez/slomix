#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${PGPASSWORD:-}" ]]; then
  echo "PGPASSWORD is not set. Export it before running this script."
  echo "Example: export PGPASSWORD='your_db_password'"
  exit 1
fi

if ! command -v psql >/dev/null 2>&1; then
  echo "psql is required but was not found in PATH."
  exit 1
fi

DB_HOST="${DB_HOST:-192.168.64.116}"
DB_PORT="${DB_PORT:-5432}"
DB_USER="${DB_USER:-etlegacy_user}"
DB_NAME="${DB_NAME:-etlegacy}"
TOP_N="${TOP_N:-10}"

echo "== WS11 Objective Coordinates Gate =="
echo "UTC: $(date -u '+%Y-%m-%d %H:%M:%S UTC')"
echo "DB: ${DB_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
echo "Top N: ${TOP_N}"
echo

top_maps_raw="$(
  psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" -d "$DB_NAME" -Atc "
SELECT lower(trim(map_name))
FROM rounds
WHERE coalesce(map_name, '') <> ''
GROUP BY 1
ORDER BY COUNT(*) DESC, 1 ASC
LIMIT ${TOP_N};
"
)"

if [[ -z "${top_maps_raw}" ]]; then
  echo "[FAIL] Query returned no top maps."
  exit 2
fi

top_maps_csv="$(printf '%s\n' "${top_maps_raw}" | paste -sd, -)"
echo "Top maps: ${top_maps_csv}"
echo

python3 scripts/proximity_objective_coords_gate.py \
  --config proximity/objective_coords_gate_config.json \
  --template proximity/objective_coords_template.json \
  --top-maps "${top_maps_csv}"
