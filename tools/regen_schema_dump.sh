#!/usr/bin/env bash
# Regenerate tools/schema_postgresql.sql from the live database.
#
# Drop-in replacement: outputs raw `pg_dump -s` with our header preserved
# and the PG14-only \restrict/\unrestrict lines stripped (so other psql
# versions / SQL clients don't choke).
#
# Usage:
#   ./tools/regen_schema_dump.sh           # uses default localhost creds
#   PGHOST=remote.host PGUSER=etlegacy_user PGPASSWORD=... ./tools/regen_schema_dump.sh

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${ROOT_DIR}/tools/schema_postgresql.sql"
HOST="${PGHOST:-127.0.0.1}"
USER="${PGUSER:-etlegacy_user}"
DB="${PGDATABASE:-etlegacy}"

if [[ -z "${PGPASSWORD:-}" ]]; then
    echo "PGPASSWORD env var must be set (use the etlegacy_user password)" >&2
    exit 2
fi

if ! command -v pg_dump >/dev/null 2>&1; then
    echo "pg_dump not found in PATH" >&2
    exit 2
fi

TODAY="$(date +%Y-%m-%d)"
DUMP_TMP="$(mktemp -t schema_postgresql_dump.XXXXXX.sql)"
OUT_TMP="$(mktemp -t schema_postgresql_out.XXXXXX.sql)"
trap 'rm -f "${DUMP_TMP}" "${OUT_TMP}"' EXIT

pg_dump -s --no-owner --no-privileges -h "${HOST}" -U "${USER}" "${DB}" > "${DUMP_TMP}"

TABLES=$(grep -c "^CREATE TABLE " "${DUMP_TMP}")
# Index count includes both explicit CREATE INDEX statements AND indexes
# created implicitly by PRIMARY KEY / UNIQUE constraints (which pg_dump
# emits as ALTER TABLE ... ADD CONSTRAINT ... PRIMARY KEY|UNIQUE).
EXPLICIT_INDEXES=$(grep -cE "^CREATE( UNIQUE)? INDEX " "${DUMP_TMP}")
CONSTRAINT_INDEXES=$(grep -cE "^    ADD CONSTRAINT .* (PRIMARY KEY|UNIQUE)" "${DUMP_TMP}")
INDEXES=$((EXPLICIT_INDEXES + CONSTRAINT_INDEXES))

# Build the final output in a temp file, then atomic-mv into place so an
# interrupted run never leaves a partial schema_postgresql.sql in the
# working tree.
cat > "${OUT_TMP}" <<HEADER
-- ============================================================================
-- PostgreSQL Schema Reference for ET:Legacy Discord Bot (Slomix)
-- ============================================================================
-- Source: pg_dump -s --no-owner --no-privileges (live \`${DB}\` database)
-- Regenerated: ${TODAY} via tools/regen_schema_dump.sh
-- PostgreSQL: 14 (dev) / 17 (prod)
-- Total tables: ${TABLES} | Total indexes: ${INDEXES}
--   (${EXPLICIT_INDEXES} CREATE INDEX + ${CONSTRAINT_INDEXES} from PK/UNIQUE constraints)
--
-- This file is AUTHORITATIVE — generated from real schema state, not
-- hand-curated. For canonical change history use migrations/*.sql.
--
-- To regenerate after schema migrations:
--   PGPASSWORD=... ./tools/regen_schema_dump.sh
-- ============================================================================

HEADER

# Strip the PG14-only \restrict/\unrestrict lines using extended regex
# alternation so the script is portable across GNU and BSD/macOS grep
# (POSIX grep doesn't support `\|` in BREs).
grep -Ev '^\\(restrict|unrestrict)' "${DUMP_TMP}" >> "${OUT_TMP}"

mv "${OUT_TMP}" "${OUT}"

echo "✓ ${OUT} regenerated (${TABLES} tables, ${INDEXES} indexes)"
