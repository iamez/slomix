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
TMP="$(mktemp -t schema_postgresql.XXXXXX.sql)"
trap 'rm -f "${TMP}"' EXIT

pg_dump -s --no-owner --no-privileges -h "${HOST}" -U "${USER}" "${DB}" > "${TMP}"

TABLES=$(grep -c "^CREATE TABLE " "${TMP}")
INDEXES=$(grep -c "^CREATE.*INDEX " "${TMP}")

# Header preserves the documentation block; subbed values get freshness.
cat > "${OUT}" <<HEADER
-- ============================================================================
-- PostgreSQL Schema Reference for ET:Legacy Discord Bot (Slomix)
-- ============================================================================
-- Source: pg_dump -s --no-owner --no-privileges (live \`${DB}\` database)
-- Regenerated: ${TODAY} via tools/regen_schema_dump.sh
-- PostgreSQL: 14 (dev) / 17 (prod)
-- Total tables: ${TABLES} | Total indexes: ${INDEXES}
--
-- This file is AUTHORITATIVE — generated from real schema state, not
-- hand-curated. For canonical change history use migrations/*.sql.
--
-- To regenerate after schema migrations:
--   PGPASSWORD=... ./tools/regen_schema_dump.sh
-- ============================================================================

HEADER

# Strip the \restrict/\unrestrict lines (psql v14 only).
grep -v '^\\restrict\|^\\unrestrict' "${TMP}" >> "${OUT}"

echo "✓ ${OUT} regenerated (${TABLES} tables, ${INDEXES} indexes)"
