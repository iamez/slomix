#!/usr/bin/env bash
# Read-only drift check: compare key counters between local samba and prod slomix_vm.
#
# Reports drift on:
#   - rounds.gaming_session_id     COUNT(DISTINCT) + MAX
#   - rounds R1+R2                 COUNT(*)
#   - players (PCS, R1+R2)         COUNT(DISTINCT player_guid)
#   - latest round_date            MAX
#
# Exit status:
#   0 — no drift (local fully matches prod)
#   1 — drift detected (counts differ in one or more metrics)
#   2 — error (env not loaded, ssh failed, etc.)
#
# Reads credentials from each env's own .env at runtime — nothing hardcoded.
# Read-only: SELECT-only queries, no writes, no schema changes.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
readonly REPO_ROOT
readonly LOCAL_ENV="${REPO_ROOT}/.env"
readonly PROD_SSH_ALIAS="${PROD_SSH_ALIAS:-slomix-vm}"
readonly PROD_REPO_PATH="${PROD_REPO_PATH:-/opt/slomix}"

# Colors (auto-disable if not a TTY, e.g. CI / piped output)
if [[ -t 1 ]]; then
    readonly C_OK=$'\033[1;32m'
    readonly C_DRIFT=$'\033[1;33m'
    readonly C_ERR=$'\033[1;31m'
    readonly C_DIM=$'\033[2m'
    readonly C_RESET=$'\033[0m'
else
    readonly C_OK=''; readonly C_DRIFT=''; readonly C_ERR=''; readonly C_DIM=''; readonly C_RESET=''
fi

log() { printf '%s[drift]%s %s\n' "$C_DIM" "$C_RESET" "$*"; }
err() { printf '%s[fail]%s %s\n' "$C_ERR" "$C_RESET" "$*" >&2; }

# Honor the documented exit-code contract (0=match, 1=drift, 2=error) for
# unexpected aborts too. Without this trap, set -e would propagate the
# failing command's exit (often psql=1), colliding with the legitimate
# "drift detected" code.
trap 'err "unexpected abort at line $LINENO (exit code $?)"; exit 2' ERR

# -------------------------------------------------------------------------
# The four metrics to compare. Each is a single-value SELECT.
# Keep these in lock-step with `records_overview.py` so dev+prod home
# pages compare apples to apples.
# -------------------------------------------------------------------------
readonly Q_SESSIONS_DISTINCT="SELECT COUNT(DISTINCT gaming_session_id) FROM rounds WHERE round_number IN (1,2) AND (round_status IN ('completed','substitution') OR round_status IS NULL) AND gaming_session_id IS NOT NULL"
readonly Q_SESSIONS_MAX="SELECT COALESCE(MAX(gaming_session_id), 0) FROM rounds WHERE gaming_session_id IS NOT NULL"
readonly Q_ROUNDS_R1R2="SELECT COUNT(*) FROM rounds WHERE round_number IN (1,2) AND (round_status IN ('completed','substitution') OR round_status IS NULL)"
readonly Q_PLAYERS="SELECT COUNT(DISTINCT player_guid) FROM player_comprehensive_stats WHERE round_number IN (1,2) AND time_played_seconds > 0"
readonly Q_LATEST="SELECT COALESCE(TO_CHAR(MAX(round_date)::date, 'YYYY-MM-DD'), '-')::text FROM rounds WHERE round_number IN (1,2)"

# -------------------------------------------------------------------------
# Load local env (canonical names: POSTGRES_HOST/PORT/DATABASE/USER/PASSWORD,
# matching .env.example). Legacy DB_* variables also accepted as fallback.
# -------------------------------------------------------------------------
if [[ ! -f "$LOCAL_ENV" ]]; then
    err "Local .env not found at $LOCAL_ENV"
    exit 2
fi
set -a
# shellcheck source=/dev/null
source "$LOCAL_ENV"
set +a

readonly DB_USER_NAME="${POSTGRES_USER:-${DB_USER:-}}"
readonly DB_PASS="${POSTGRES_PASSWORD:-${DB_PASSWORD:-}}"
readonly DB_NAME="${POSTGRES_DATABASE:-${DB_NAME:-etlegacy}}"
readonly DB_HOST="${POSTGRES_HOST:-${DB_HOST:-127.0.0.1}}"
readonly DB_PORT="${POSTGRES_PORT:-${DB_PORT:-5432}}"

if [[ -z "$DB_USER_NAME" || -z "$DB_PASS" ]]; then
    err "POSTGRES_USER / POSTGRES_PASSWORD missing in $LOCAL_ENV"
    exit 2
fi

# The remote query_prod call uses prod's PGDATABASE (typically 'etlegacy').
# If local DB_NAME differs, we'd silently compare two unrelated databases,
# which renders the drift report meaningless. Refuse to run rather than
# print misleading match/mismatch rows.
if [[ "$DB_NAME" != "etlegacy" ]]; then
    err "local DB_NAME='${DB_NAME}' but prod side queries 'etlegacy' — comparison would be meaningless."
    err "Set POSTGRES_DATABASE=etlegacy in $LOCAL_ENV, or override prod by exporting PROD_DB_NAME (not yet supported)."
    exit 2
fi

query_local() {
    PGPASSWORD="$DB_PASS" psql \
        -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER_NAME" -d "$DB_NAME" \
        -tAc "$1" 2>/dev/null | tr -d '[:space:]'
}

# Run a single SELECT on prod via SSH. SQL is passed as positional $2 inside a
# quoted heredoc — no client-side expansion, no quoting issues with embedded
# single quotes (e.g. `round_status IN ('completed', ...)`). Path is $1.
query_prod() {
    local sql="$1"
    ssh -o BatchMode=yes "${PROD_SSH_ALIAS}" bash -s "${PROD_REPO_PATH}" "$sql" <<'REMOTE_END' 2>/dev/null | tr -d '[:space:]'
set -euo pipefail
cd "$1"
PGPASSWORD=$(grep -E '^POSTGRES_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '"')
PGUSER=$(grep -E '^POSTGRES_USER=' .env | head -1 | cut -d= -f2- | tr -d '"')
PGDATABASE=$(grep -E '^POSTGRES_DATABASE=' .env | head -1 | cut -d= -f2- | tr -d '"')
PGPASSWORD="$PGPASSWORD" psql -h localhost -U "$PGUSER" -d "${PGDATABASE:-etlegacy}" -tAc "$2"
REMOTE_END
}

# -------------------------------------------------------------------------
# Run all metrics on both sides
# -------------------------------------------------------------------------
log "Querying local: ${DB_USER_NAME}@${DB_HOST}:${DB_PORT}/${DB_NAME}"
LOCAL_SESSIONS_DISTINCT=$(query_local "$Q_SESSIONS_DISTINCT") || { err "local query failed"; exit 2; }
LOCAL_SESSIONS_MAX=$(query_local "$Q_SESSIONS_MAX")
LOCAL_ROUNDS=$(query_local "$Q_ROUNDS_R1R2")
LOCAL_PLAYERS=$(query_local "$Q_PLAYERS")
LOCAL_LATEST=$(query_local "$Q_LATEST")

log "Querying prod via ssh ${PROD_SSH_ALIAS}..."
PROD_SESSIONS_DISTINCT=$(query_prod "$Q_SESSIONS_DISTINCT") || { err "prod ssh/query failed"; exit 2; }
PROD_SESSIONS_MAX=$(query_prod "$Q_SESSIONS_MAX")
PROD_ROUNDS=$(query_prod "$Q_ROUNDS_R1R2")
PROD_PLAYERS=$(query_prod "$Q_PLAYERS")
PROD_LATEST=$(query_prod "$Q_LATEST")

# -------------------------------------------------------------------------
# Compare and report
# -------------------------------------------------------------------------
DRIFT=0
print_row() {
    local name="$1" loc="$2" prod="$3"
    if [[ "$loc" == "$prod" ]]; then
        printf '  %s✓%s %-28s local=%-12s prod=%-12s match\n' "$C_OK" "$C_RESET" "$name" "$loc" "$prod"
    else
        DRIFT=1
        local arrow="≠"
        if [[ "$loc" =~ ^[0-9]+$ && "$prod" =~ ^[0-9]+$ ]]; then
            local d=$((prod - loc))
            if (( d > 0 )); then
                arrow="(+${d} on prod)"
            else
                arrow="(${d#-} more on local)"
            fi
        fi
        printf '  %s✗%s %-28s local=%-12s prod=%-12s %s%s%s\n' \
            "$C_DRIFT" "$C_RESET" "$name" "$loc" "$prod" "$C_DRIFT" "$arrow" "$C_RESET"
    fi
}

echo
log "==================== DB DRIFT ===================="
print_row "sessions COUNT(DISTINCT)"  "$LOCAL_SESSIONS_DISTINCT"  "$PROD_SESSIONS_DISTINCT"
print_row "sessions MAX(id)"           "$LOCAL_SESSIONS_MAX"       "$PROD_SESSIONS_MAX"
print_row "rounds R1+R2 COUNT"         "$LOCAL_ROUNDS"             "$PROD_ROUNDS"
print_row "players (PCS) COUNT"        "$LOCAL_PLAYERS"            "$PROD_PLAYERS"
print_row "latest round_date"          "$LOCAL_LATEST"             "$PROD_LATEST"
log "=================================================="
echo

if [[ "$DRIFT" -eq 0 ]]; then
    printf '%sLocal and prod match across all checked metrics.%s\n' "$C_OK" "$C_RESET"
    exit 0
fi

# Surface the well-known partial-dump symptom
if [[ "$LOCAL_SESSIONS_MAX" == "$PROD_SESSIONS_MAX" \
   && "$LOCAL_SESSIONS_DISTINCT" != "$PROD_SESSIONS_DISTINCT" ]]; then
    echo
    printf '%sNote:%s MAX(gaming_session_id) matches but DISTINCT does not — \n' "$C_DRIFT" "$C_RESET"
    printf '      classic partial-dump symptom (some session_ids inside 1..MAX are absent locally).\n'
    printf '      Run %sscripts/sync_local_from_prod.sh%s for non-destructive resync.\n' "$C_DIM" "$C_RESET"
fi

exit 1
