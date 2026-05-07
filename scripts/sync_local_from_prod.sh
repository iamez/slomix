#!/usr/bin/env bash
# Sync local samba PostgreSQL from production slomix_vm — non-destructive.
#
# Safety: NEVER drops the existing local database. Instead:
#   1. Dumps current local etlegacy → /tmp/etlegacy_local_pre-sync_<ts>.dump
#      (Postgres custom format, parachute file)
#   2. RENAMES current `etlegacy` → `etlegacy_backup_<ts>` (data preserved as
#      a separate, queryable database — `\c etlegacy_backup_<ts>` to read)
#   3. Creates a fresh empty `etlegacy` owned by the original user
#   4. Streams pg_dump from prod over SSH and pg_restores into the fresh DB
#   5. Verifies row counts (sessions, rounds) and aborts if verification
#      shows the new DB is empty (auto-rollback by renaming back)
#
# Rollback if anything looks wrong:
#   psql -c "ALTER DATABASE etlegacy RENAME TO etlegacy_failed_<ts>"
#   psql -c "ALTER DATABASE etlegacy_backup_<ts> RENAME TO etlegacy"
#   …and you're back where you started, no data lost.
#
# Prerequisites:
#   - SSH alias `slomix-vm` configured (~/.ssh/config)
#   - Local repo .env contains POSTGRES_USER + POSTGRES_PASSWORD (canonical
#     names from .env.example; legacy DB_* names also accepted)
#   - Local user has CREATEDB privilege OR is db owner (etlegacy_user is owner)
#   - No active connections to local etlegacy during rename. Bot/website
#     services must be stopped first — script aborts cleanly if any are open.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_ROOT
readonly LOCAL_ENV="${REPO_ROOT}/.env"
readonly PROD_SSH_ALIAS="${PROD_SSH_ALIAS:-slomix-vm}"
readonly PROD_REPO_PATH="${PROD_REPO_PATH:-/opt/slomix}"

TS="$(date +%Y%m%d-%H%M%S)"
readonly TS
readonly DUMP_DIR="${DUMP_DIR:-/tmp}"
readonly LOCAL_PRE_SYNC_DUMP="${DUMP_DIR}/etlegacy_local_pre-sync_${TS}.dump"
readonly PROD_DUMP="${DUMP_DIR}/etlegacy_prod_${TS}.dump"

# -------------------------------------------------------------------------
# Helpers
# -------------------------------------------------------------------------
log() { printf '\033[1;36m[sync]\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m[warn]\033[0m %s\n' "$*"; }
die() { printf '\033[1;31m[fail]\033[0m %s\n' "$*" >&2; exit 1; }

confirm() {
    local prompt="$1"
    local reply
    read -r -p "$prompt [y/N] " reply
    [[ "$reply" =~ ^[Yy]$ ]] || die "Aborted by user."
}

# -------------------------------------------------------------------------
# Step 0 — Load local env, sanity-check
# Canonical names: POSTGRES_HOST/PORT/DATABASE/USER/PASSWORD (per .env.example).
# Legacy DB_* fall-throughs accepted to keep older devboxes working.
# -------------------------------------------------------------------------
[[ -f "$LOCAL_ENV" ]] || die "Local .env not found at $LOCAL_ENV"

set -a
# shellcheck source=/dev/null
source "$LOCAL_ENV"
set +a

readonly DB_USER_NAME="${POSTGRES_USER:-${DB_USER:-}}"
readonly DB_PASS="${POSTGRES_PASSWORD:-${DB_PASSWORD:-}}"
readonly DB_NAME="${POSTGRES_DATABASE:-${DB_NAME:-etlegacy}}"
readonly DB_HOST="${POSTGRES_HOST:-${DB_HOST:-127.0.0.1}}"
readonly DB_PORT="${POSTGRES_PORT:-${DB_PORT:-5432}}"

[[ -n "$DB_USER_NAME" ]] || die "POSTGRES_USER missing in $LOCAL_ENV"
[[ -n "$DB_PASS"      ]] || die "POSTGRES_PASSWORD missing in $LOCAL_ENV"

readonly BACKUP_DB_NAME="${DB_NAME}_backup_${TS}"

# psql + pg_dump + pg_restore wrappers (password via env, never on argv)
psql_local() { PGPASSWORD="$DB_PASS" psql -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER_NAME" "$@"; }
restore_local() { PGPASSWORD="$DB_PASS" pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER_NAME" "$@"; }
dump_local() { PGPASSWORD="$DB_PASS" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER_NAME" "$@"; }

log "Repo root: $REPO_ROOT"
log "Local target: ${DB_USER_NAME}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
log "Prod source: ssh ${PROD_SSH_ALIAS} → ${PROD_REPO_PATH}/.env"
log "Backup DB will be named: ${BACKUP_DB_NAME}"
log "Dump files (parachutes):"
log "  - local pre-sync: ${LOCAL_PRE_SYNC_DUMP}"
log "  - prod snapshot:  ${PROD_DUMP}"

# -------------------------------------------------------------------------
# Step 1 — Detect active connections (rename will fail if any)
# -------------------------------------------------------------------------
log "Checking for active local connections to ${DB_NAME}..."
ACTIVE_CONNS=$(psql_local -d postgres -tAc \
    "SELECT COUNT(*) FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid()")
if [[ "${ACTIVE_CONNS}" -gt 0 ]]; then
    warn "${ACTIVE_CONNS} active connection(s) on ${DB_NAME}. List:"
    psql_local -d postgres -c \
        "SELECT pid, usename, application_name, client_addr, state FROM pg_stat_activity WHERE datname='${DB_NAME}' AND pid <> pg_backend_pid()"
    die "Stop bot/website services that hold connections, then re-run. (No data has been touched.)"
fi
log "No active connections — safe to proceed."

# -------------------------------------------------------------------------
# Step 2 — Confirmation
# -------------------------------------------------------------------------
echo
log "Plan:"
log "  1. Dump local ${DB_NAME} → ${LOCAL_PRE_SYNC_DUMP}"
log "  2. Pull prod dump via SSH → ${PROD_DUMP}"
log "  3. ALTER DATABASE ${DB_NAME} RENAME TO ${BACKUP_DB_NAME}  (preserves all current data)"
log "  4. CREATE DATABASE ${DB_NAME} OWNER ${DB_USER_NAME}"
log "  5. pg_restore ${PROD_DUMP} → fresh ${DB_NAME}"
log "  6. Verify row counts; auto-rollback rename if verify fails"
echo
warn "If something fails at step 5, the script will rename ${BACKUP_DB_NAME} back to ${DB_NAME}. No data is destroyed."
confirm "Proceed?"

# -------------------------------------------------------------------------
# Step 3 — Local backup dump (parachute file)
# -------------------------------------------------------------------------
log "(1/6) Dumping local ${DB_NAME} → ${LOCAL_PRE_SYNC_DUMP}"
dump_local -Fc -d "${DB_NAME}" -f "${LOCAL_PRE_SYNC_DUMP}"
LOCAL_DUMP_SIZE=$(du -h "${LOCAL_PRE_SYNC_DUMP}" | cut -f1)
log "   ✓ Local parachute saved (${LOCAL_DUMP_SIZE})"

# -------------------------------------------------------------------------
# Step 4 — Prod dump pulled via SSH (uses prod's own credentials from
# /opt/slomix/.env). Uses heredoc + positional $1 to avoid client-side
# expansion of the path and any quoting issues.
# -------------------------------------------------------------------------
log "(2/6) Pulling prod dump via ssh ${PROD_SSH_ALIAS}..."
ssh "${PROD_SSH_ALIAS}" bash -s "${PROD_REPO_PATH}" <<'REMOTE_DUMP_END' > "${PROD_DUMP}"
set -euo pipefail
cd "$1"
PGPASSWORD=$(grep -E '^POSTGRES_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '"')
PGUSER=$(grep -E '^POSTGRES_USER=' .env | head -1 | cut -d= -f2- | tr -d '"')
PGDATABASE=$(grep -E '^POSTGRES_DATABASE=' .env | head -1 | cut -d= -f2- | tr -d '"')
PGPASSWORD="$PGPASSWORD" pg_dump -h localhost -U "$PGUSER" -Fc -d "${PGDATABASE:-etlegacy}"
REMOTE_DUMP_END

# Sanity-check the dump file before we touch the local DB
if [[ ! -s "${PROD_DUMP}" ]]; then
    die "Prod dump is empty (${PROD_DUMP}) — refusing to proceed. Local DB is untouched."
fi
PROD_DUMP_SIZE=$(du -h "${PROD_DUMP}" | cut -f1)
log "   ✓ Prod dump received (${PROD_DUMP_SIZE})"

# -------------------------------------------------------------------------
# Step 5 — Rename current local DB (NON-DESTRUCTIVE: data accessible under new name)
# -------------------------------------------------------------------------
log "(3/6) Renaming ${DB_NAME} → ${BACKUP_DB_NAME}"
psql_local -d postgres -c "ALTER DATABASE \"${DB_NAME}\" RENAME TO \"${BACKUP_DB_NAME}\""
log "   ✓ Old data preserved as database '${BACKUP_DB_NAME}' (queryable: \\c ${BACKUP_DB_NAME})"

# -------------------------------------------------------------------------
# Auto-rollback helper. If anything between here and the final verification
# fails, swap names back so the user is not stuck without a working DB.
# -------------------------------------------------------------------------
rollback_rename() {
    local reason="$1"
    warn "Auto-rollback: ${reason}"
    if psql_local -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
        psql_local -d postgres -c "ALTER DATABASE \"${DB_NAME}\" RENAME TO \"${DB_NAME}_failed_${TS}\"" || true
    fi
    psql_local -d postgres -c "ALTER DATABASE \"${BACKUP_DB_NAME}\" RENAME TO \"${DB_NAME}\""
    warn "Rolled back. ${DB_NAME} is your original data; failed restore is ${DB_NAME}_failed_${TS}."
    warn "Parachute dump still at ${LOCAL_PRE_SYNC_DUMP}; prod dump at ${PROD_DUMP}."
}

# -------------------------------------------------------------------------
# Step 6 — Create fresh empty DB
# -------------------------------------------------------------------------
log "(4/6) Creating fresh empty ${DB_NAME} owned by ${DB_USER_NAME}"
if ! psql_local -d postgres -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${DB_USER_NAME}\""; then
    rollback_rename "CREATE DATABASE failed"
    die "Aborted at step 4."
fi
log "   ✓ Empty DB created"

# -------------------------------------------------------------------------
# Step 7 — Restore prod dump into fresh DB
# Capture pg_restore exit code separately. Non-zero is common (e.g. missing
# website_app / website_readonly roles → harmless GRANT errors). We don't
# treat exit code alone as fatal — verification (next step) decides.
# -------------------------------------------------------------------------
log "(5/6) Restoring prod dump into ${DB_NAME}..."
RESTORE_RC=0
restore_local --no-owner --no-acl -d "${DB_NAME}" "${PROD_DUMP}" || RESTORE_RC=$?
if [[ "${RESTORE_RC}" -ne 0 ]]; then
    warn "pg_restore exit ${RESTORE_RC} (often harmless: missing roles, comments). Verification will decide."
else
    log "   ✓ pg_restore exit 0"
fi

# -------------------------------------------------------------------------
# Step 8 — Verify. If the new DB has zero rounds, treat the restore as
# failed and roll back. This catches catastrophic restore errors that exit 0.
# -------------------------------------------------------------------------
log "(6/6) Verification"
ROUNDS_COUNT=0
if ! ROUNDS_COUNT=$(psql_local -d "${DB_NAME}" -tAc "
    SELECT COUNT(*) FROM rounds
    WHERE round_number IN (1,2)
      AND (round_status IN ('completed','substitution') OR round_status IS NULL)
" 2>/dev/null); then
    rollback_rename "verification query failed (table missing or DB unusable)"
    die "Aborted at step 6 — restored DB is not usable."
fi

if [[ "${ROUNDS_COUNT}" -lt 1 ]]; then
    rollback_rename "verification: 0 rounds in restored DB"
    die "Aborted at step 6 — restored DB has no rounds."
fi

SESSIONS_COUNT=$(psql_local -d "${DB_NAME}" -tAc "
    SELECT COUNT(DISTINCT gaming_session_id) FROM rounds
    WHERE round_number IN (1,2)
      AND (round_status IN ('completed','substitution') OR round_status IS NULL)
      AND gaming_session_id IS NOT NULL
")
BACKUP_SESSIONS=$(psql_local -d "${BACKUP_DB_NAME}" -tAc "
    SELECT COUNT(DISTINCT gaming_session_id) FROM rounds
    WHERE round_number IN (1,2)
      AND (round_status IN ('completed','substitution') OR round_status IS NULL)
      AND gaming_session_id IS NOT NULL
")

echo
log "==================== SUMMARY ===================="
log "Old data preserved as DB:   ${BACKUP_DB_NAME}  (sessions: ${BACKUP_SESSIONS})"
log "New ${DB_NAME} from prod:    sessions: ${SESSIONS_COUNT}, R1+R2 rounds: ${ROUNDS_COUNT}"
log "pg_restore exit code:       ${RESTORE_RC} (warnings tolerated when verification passes)"
log "Parachute dump file:        ${LOCAL_PRE_SYNC_DUMP}"
log "Prod snapshot dump file:    ${PROD_DUMP}"
log "================================================="
echo
# Print rollback / cleanup hints with a real copy-pasteable psql command.
# Earlier versions referenced `psql_local`, the in-script bash function defined
# above — that name does not exist in the user's shell after the script exits,
# which is exactly when these hints are needed.
RECOVERY_PSQL="PGPASSWORD=\$POSTGRES_PASSWORD psql -h ${DB_HOST} -p ${DB_PORT} -U ${DB_USER_NAME} -d postgres -c"
log "Rollback (if needed):"
log "  ${RECOVERY_PSQL} \"ALTER DATABASE ${DB_NAME} RENAME TO etlegacy_failed_${TS}\""
log "  ${RECOVERY_PSQL} \"ALTER DATABASE ${BACKUP_DB_NAME} RENAME TO ${DB_NAME}\""
echo
log "Cleanup (when you're sure new DB is good):"
log "  ${RECOVERY_PSQL} \"DROP DATABASE ${BACKUP_DB_NAME}\""
log "  rm ${LOCAL_PRE_SYNC_DUMP} ${PROD_DUMP}"
