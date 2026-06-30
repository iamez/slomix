#!/bin/bash
# =============================================================================
# db_backup.sh — timestamped pg_dump of the etlegacy database.
#
# Run BEFORE any DB-mutating step (migration 011, backfills, schema work) so
# there is always a known-good restore point. Read-only on the DB (dump only).
#
# Usage:
#   ./scripts/db_backup.sh                       # dump to ./backups/
#   BACKUP_DIR=/srv/backups ./scripts/db_backup.sh
#
# Restore (manual, owner-gated):
#   gunzip -c backups/etlegacy_YYYYmmdd-HHMMSS.sql.gz | \
#     PGPASSWORD=... psql -h 127.0.0.1 -U etlegacy_user -d etlegacy
# =============================================================================
set -euo pipefail

# Load .env (POSTGRES_* creds) if present — same vars bot/web use.
if [ -f .env ]; then set -a; . ./.env; set +a; fi

PGHOST="${POSTGRES_HOST:-127.0.0.1}"
PGPORT="${POSTGRES_PORT:-5432}"
PGDB="${POSTGRES_DATABASE:-etlegacy}"
PGUSER="${POSTGRES_USER:-etlegacy_user}"
BACKUP_DIR="${BACKUP_DIR:-backups}"
TS="$(date '+%Y%m%d-%H%M%S')"
OUT="$BACKUP_DIR/${PGDB}_${TS}.sql.gz"

mkdir -p "$BACKUP_DIR"
echo "[db_backup] dumping $PGDB@$PGHOST:$PGPORT -> $OUT"
PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_dump \
  -h "$PGHOST" -p "$PGPORT" -U "$PGUSER" -d "$PGDB" \
  --no-owner --no-privileges \
  | gzip -9 > "$OUT"

SIZE="$(du -h "$OUT" | cut -f1)"
echo "[db_backup] ✅ done: $OUT ($SIZE)"
echo "[db_backup] restore: gunzip -c $OUT | PGPASSWORD=... psql -h $PGHOST -U $PGUSER -d $PGDB"
