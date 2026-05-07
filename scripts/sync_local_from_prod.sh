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
#   5. Verifies row counts (sessions, rounds) and prints summary
#
# Rollback:
#   psql -c "ALTER DATABASE etlegacy RENAME TO etlegacy_failed_<ts>"
#   psql -c "ALTER DATABASE etlegacy_backup_<ts> RENAME TO etlegacy"
#   …and you're back where you started, no data lost.
#
# Prerequisites:
#   - SSH alias `slomix-vm` configured (~/.ssh/config)
#   - Local /home/samba/share/slomix_discord/.env contains POSTGRES_USER + POSTGRES_PASSWORD
#   - Local user has CREATEDB privilege OR is db owner (etlegacy_user is owner)
#   - No active connections to local etlegacy during rename. If bot/website are
#     running locally, stop them first — script will detect and abort cleanly.

set -euo pipefail

# -------------------------------------------------------------------------
# Config
# -------------------------------------------------------------------------
readonly REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly LOCAL_ENV="${REPO_ROOT}/.env"
readonly PROD_SSH_ALIAS="${PROD_SSH_ALIAS:-slomix-vm}"
readonly PROD_REPO_PATH="${PROD_REPO_PATH:-/opt/slomix}"
readonly TS="$(date +%Y%m%d-%H%M%S)"
readonly DUMP_DIR="${DUMP_DIR:-/tmp}"
readonly LOCAL_PRE_SYNC_DUMP="${DUMP_DIR}/etlegacy_local_pre-sync_${TS}.dump"
readonly PROD_DUMP="${DUMP_DIR}/etlegacy_prod_${TS}.dump"
readonly BACKUP_DB_NAME="etlegacy_backup_${TS}"

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
# -------------------------------------------------------------------------
[[ -f "$LOCAL_ENV" ]] || die "Local .env not found at $LOCAL_ENV"

# shellcheck disable=SC1090
set -a; source "$LOCAL_ENV"; set +a

: "${POSTGRES_USER:?POSTGRES_USER missing in .env}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD missing in .env}"
readonly DB_NAME="${DB_NAME:-etlegacy}"
readonly DB_HOST="${DB_HOST:-127.0.0.1}"
readonly DB_PORT="${DB_PORT:-5432}"

# psql + pg_restore wrappers that pass the password via env (safer than -W)
psql_local() { PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" "$@"; }
restore_local() { PGPASSWORD="$POSTGRES_PASSWORD" pg_restore -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" "$@"; }
dump_local() { PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" "$@"; }

log "Repo root: $REPO_ROOT"
log "Local target: ${POSTGRES_USER}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
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
log "  4. CREATE DATABASE ${DB_NAME} OWNER ${POSTGRES_USER}"
log "  5. pg_restore ${PROD_DUMP} → fresh ${DB_NAME}"
log "  6. Verify row counts"
echo
warn "If something fails at step 5, you can rename ${BACKUP_DB_NAME} back to ${DB_NAME} — no data is destroyed."
confirm "Proceed?"

# -------------------------------------------------------------------------
# Step 3 — Local backup dump (parachute file)
# -------------------------------------------------------------------------
log "(1/6) Dumping local ${DB_NAME} → ${LOCAL_PRE_SYNC_DUMP}"
dump_local -Fc -d "${DB_NAME}" -f "${LOCAL_PRE_SYNC_DUMP}"
LOCAL_DUMP_SIZE=$(du -h "${LOCAL_PRE_SYNC_DUMP}" | cut -f1)
log "   ✓ Local parachute saved (${LOCAL_DUMP_SIZE})"

# -------------------------------------------------------------------------
# Step 4 — Prod dump pulled via SSH (uses prod's own credentials from /opt/slomix/.env)
# -------------------------------------------------------------------------
log "(2/6) Pulling prod dump via ssh ${PROD_SSH_ALIAS}..."
ssh "${PROD_SSH_ALIAS}" "
    set -euo pipefail
    cd ${PROD_REPO_PATH}
    PGPASSWORD=\$(grep ^POSTGRES_PASSWORD .env | cut -d= -f2- | tr -d '\"\\\"')
    PGUSER=\$(grep ^POSTGRES_USER .env | cut -d= -f2- | tr -d '\"\\\"')
    PGPASSWORD=\"\$PGPASSWORD\" pg_dump -h localhost -U \"\$PGUSER\" -Fc -d etlegacy
" > "${PROD_DUMP}"
PROD_DUMP_SIZE=$(du -h "${PROD_DUMP}" | cut -f1)
log "   ✓ Prod dump received (${PROD_DUMP_SIZE})"

# -------------------------------------------------------------------------
# Step 5 — Rename current local DB (NON-DESTRUCTIVE: data accessible under new name)
# -------------------------------------------------------------------------
log "(3/6) Renaming ${DB_NAME} → ${BACKUP_DB_NAME}"
psql_local -d postgres -c "ALTER DATABASE \"${DB_NAME}\" RENAME TO \"${BACKUP_DB_NAME}\""
log "   ✓ Old data preserved as database '${BACKUP_DB_NAME}' (queryable: \\c ${BACKUP_DB_NAME})"

# -------------------------------------------------------------------------
# Step 6 — Create fresh empty DB
# -------------------------------------------------------------------------
log "(4/6) Creating fresh empty ${DB_NAME} owned by ${POSTGRES_USER}"
psql_local -d postgres -c "CREATE DATABASE \"${DB_NAME}\" OWNER \"${POSTGRES_USER}\""
log "   ✓ Empty DB created"

# -------------------------------------------------------------------------
# Step 7 — Restore prod dump into fresh DB
# -------------------------------------------------------------------------
log "(5/6) Restoring prod dump into ${DB_NAME}..."
# --no-owner so objects end up owned by the local connecting user.
# --no-acl drops GRANT/REVOKE statements that reference prod-only roles
#   (eg. website_app password may differ; perms get re-applied via app config).
restore_local --no-owner --no-acl -d "${DB_NAME}" "${PROD_DUMP}" \
    || warn "pg_restore reported errors (often harmless: missing roles, comments). Verify counts below."
log "   ✓ Restore complete"

# -------------------------------------------------------------------------
# Step 8 — Verify
# -------------------------------------------------------------------------
log "(6/6) Verification"
SESSIONS_COUNT=$(psql_local -d "${DB_NAME}" -tAc "
    SELECT COUNT(DISTINCT gaming_session_id) FROM rounds
    WHERE round_number IN (1,2)
      AND (round_status IN ('completed','substitution') OR round_status IS NULL)
      AND gaming_session_id IS NOT NULL
")
ROUNDS_COUNT=$(psql_local -d "${DB_NAME}" -tAc "
    SELECT COUNT(*) FROM rounds
    WHERE round_number IN (1,2)
      AND (round_status IN ('completed','substitution') OR round_status IS NULL)
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
log "Parachute dump file:        ${LOCAL_PRE_SYNC_DUMP}"
log "Prod snapshot dump file:    ${PROD_DUMP}"
log "================================================="
echo
log "Rollback (if needed):"
log "  psql_local -d postgres -c \"ALTER DATABASE ${DB_NAME} RENAME TO etlegacy_failed_${TS}\""
log "  psql_local -d postgres -c \"ALTER DATABASE ${BACKUP_DB_NAME} RENAME TO ${DB_NAME}\""
echo
log "Cleanup (when you're sure new DB is good):"
log "  psql_local -d postgres -c \"DROP DATABASE ${BACKUP_DB_NAME}\""
log "  rm ${LOCAL_PRE_SYNC_DUMP} ${PROD_DUMP}"
