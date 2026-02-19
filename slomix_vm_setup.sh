#!/bin/bash
# slomix_vm_setup.sh
#
# Bootstraps the Slomix Discord project (ET:Legacy stats bot + FastAPI website +
# PostgreSQL database) on a fresh Debian 12 or Ubuntu 22.04+ host and provides
# tools for phased migration from any existing PostgreSQL host.
#
# ┌─────────────────────────────────────────────────────────────────────────┐
# │  MIGRATION STRATEGY                                                    │
# │                                                                        │
# │  Phase 1 – SETUP   : Run this script.  Installs everything, services  │
# │                       are enabled but NOT started.                     │
# │  Phase 2 – MIGRATE : Run `slomix_vm_setup.sh migrate` to pull a full  │
# │                       pg_dump from the source host (or import a local  │
# │                       dump file) and restore it on this VM.            │
# │  Phase 3 – TUNNEL  : Run `slomix_vm_setup.sh tunnel` to interactively │
# │                       create a Cloudflare Tunnel and wire up DNS.      │
# │  Phase 4 – TEST    : Start website on VM, browse via tunnel, verify.  │
# │  Phase 5 – CUTOVER : Start all services on this VM.                   │
# └─────────────────────────────────────────────────────────────────────────┘
#
# Usage:
#   sudo bash slomix_vm_setup.sh                        # Phase 1 – full setup
#   sudo bash slomix_vm_setup.sh migrate                # Phase 2 – remote pg_dump
#   sudo bash slomix_vm_setup.sh migrate --file dump.sql  # Phase 2 – local file
#   sudo bash slomix_vm_setup.sh tunnel                 # Phase 3 – Cloudflare Tunnel
#   sudo bash slomix_vm_setup.sh cutover                # Phase 5 – start VM services
#   sudo bash slomix_vm_setup.sh status                 # Show current service status
#
# Review the "Configuration" section below and adjust to your environment.

set -euo pipefail

# ===========================================================================
# Configuration – adjust these values to suit your environment
# ===========================================================================

# Directory under which the application will live
APP_DIR="/opt/slomix"

# Git repository to clone
REPO_URL="https://github.com/iamez/slomix.git"
REPO_BRANCH="main"

# System users and group used to run the services.
# A shared group allows both service users to read the code while keeping
# privileges separate per‑service.  Do not log in as these users.
SLX_GROUP="slomix"
BOT_USER="slomix_bot"
WEB_USER="slomix_web"

# PostgreSQL database credentials – MUST match what the bot code expects!
# (see bot/config.py & .env.example in the repo)
DB_NAME="etlegacy"
DB_USER="etlegacy_user"
DB_PASSWORD=""                  # auto‑generated if left empty

# Read‑only PostgreSQL user for the FastAPI website
WEB_DB_USER="website_readonly"
WEB_DB_PASSWORD=""              # auto‑generated if left empty

# Website port (uvicorn binds to 127.0.0.1:<WEBSITE_PORT>)
WEBSITE_PORT=7000

# External domain for the FastAPI website.  Cloudflare Tunnel will route
# requests for this hostname to localhost:$WEBSITE_PORT inside the VM.
DOMAIN_NAME="slomix.fyi"

# Allowed network for SSH access.  Replace with your LAN or VPN range.
# Leave blank to allow SSH from everywhere (not recommended in production).
SSH_ALLOWED_NET="192.168.0.0/16"

# ---------- Migration source (existing production host) ----------
# Used by `slomix_vm_setup.sh migrate` to pull the database.
# Set these to wherever PostgreSQL is currently running, or leave blank
# and pass --file /path/to/dump.sql to import a local dump instead.
SOURCE_DB_HOST=""               # e.g. 192.168.1.50  (source host LAN IP)
SOURCE_DB_PORT="5432"
SOURCE_DB_NAME="etlegacy"
SOURCE_DB_USER="etlegacy_user"
SOURCE_DB_PASSWORD=""           # prompted interactively if empty

# ===========================================================================
# Helpers
# ===========================================================================
error()  { echo "[ERROR] $*" >&2; exit 1; }
info()   { echo "[INFO]  $*"; }
warn()   { echo "[WARN]  $*"; }
success(){ echo "[ OK ]  $*"; }
banner() { echo ""; echo "=========== $* ==========="; echo ""; }

# Ensure we are running as root
if [[ "$(id -u)" -ne 0 ]]; then
  error "This script must be run as root.  Try: sudo $0"
fi

# ---------- OS check ----------
if [[ -f /etc/os-release ]]; then
  . /etc/os-release
  case "$ID" in
    debian|ubuntu) ;;
    *) warn "This script is designed for Debian/Ubuntu. Detected: $ID $VERSION_ID. Proceeding anyway." ;;
  esac
else
  warn "Cannot detect OS (/etc/os-release missing). Proceeding anyway."
fi

# ---------- Setup log ----------
# All output is tee'd to a log file so you can review after a long install.
SETUP_LOG="/var/log/slomix_setup_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$SETUP_LOG") 2>&1
info "Logging to $SETUP_LOG"

# ---------- Auto‑generate passwords if not set ----------
generate_password() {
  if command -v openssl >/dev/null 2>&1; then
    openssl rand -base64 48 | tr -dc 'A-Za-z0-9' | head -c 32
  else
    LC_ALL=C tr -dc 'A-Za-z0-9' < /dev/urandom | head -c 32
  fi
}

# Load existing passwords from .env if it exists (so re‑runs don't overwrite)
BOT_ENV="$APP_DIR/.env"
WEBSITE_ENV="$APP_DIR/website/.env"

load_env_var() {
  local file="$1" key="$2"
  if [[ -f "$file" ]]; then
    grep -m1 "^${key}=" "$file" 2>/dev/null | cut -d'=' -f2- | tr -d "'" | tr -d '"' || true
  fi
}

# Try to recover existing passwords before generating new ones
if [[ -z "$DB_PASSWORD" ]]; then
  DB_PASSWORD="$(load_env_var "$BOT_ENV" POSTGRES_PASSWORD)"
fi
if [[ -z "$DB_PASSWORD" ]]; then
  DB_PASSWORD="$(generate_password)"
  info "Generated random PostgreSQL password for user $DB_USER"
fi

if [[ -z "$WEB_DB_PASSWORD" ]]; then
  WEB_DB_PASSWORD="$(load_env_var "$WEBSITE_ENV" POSTGRES_PASSWORD)"
fi
if [[ -z "$WEB_DB_PASSWORD" ]]; then
  WEB_DB_PASSWORD="$(generate_password)"
  info "Generated random PostgreSQL password for user $WEB_DB_USER"
fi

# Auto‑generate a SESSION_SECRET for the website (Starlette sessions)
SESSION_SECRET="$(load_env_var "$WEBSITE_ENV" SESSION_SECRET)"
if [[ -z "$SESSION_SECRET" ]]; then
  SESSION_SECRET="$(generate_password)"
fi

# Computed paths used throughout
BOT_VENV="$APP_DIR/venv-bot"
WEB_VENV="$APP_DIR/venv-web"
BOT_SSH_DIR="$APP_DIR/.ssh"

# ===========================================================================
# Sub‑command: migrate  (Phase 2)
# Pull a pg_dump from a remote host, OR import a local .sql dump file.
# ===========================================================================
do_migrate() {
  banner "PHASE 2 — DATABASE MIGRATION"

  command -v psql >/dev/null 2>&1 || error "psql not found. Install postgresql-client."

  # ── Decide mode: local dump file  vs  remote pg_dump ──
  LOCAL_DUMP_FILE=""
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --file|-f) LOCAL_DUMP_FILE="$2"; shift 2 ;;
      *) shift ;;
    esac
  done

  DUMP_DIR="$APP_DIR/migration"
  mkdir -p "$DUMP_DIR"

  if [[ -n "$LOCAL_DUMP_FILE" ]]; then
    # ── Mode A: Import from a local .sql dump file ──
    [[ -f "$LOCAL_DUMP_FILE" ]] || error "Dump file not found: $LOCAL_DUMP_FILE"
    DUMP_SIZE=$(stat --format="%s" "$LOCAL_DUMP_FILE" 2>/dev/null || stat -f "%z" "$LOCAL_DUMP_FILE" 2>/dev/null)
    if [[ "$DUMP_SIZE" -lt 100 ]]; then
      error "Dump file is suspiciously small ($DUMP_SIZE bytes). Aborting."
    fi
    info "Importing local dump: $LOCAL_DUMP_FILE ($(numfmt --to=iec "$DUMP_SIZE" 2>/dev/null || echo "${DUMP_SIZE} bytes"))"
    DUMP_FILE="$LOCAL_DUMP_FILE"
    SOURCE_TABLES="(local file)"
    SOURCE_ROWS="(local file)"
  else
    # ── Mode B: Remote pg_dump over the network ──
    command -v pg_dump >/dev/null 2>&1 || error "pg_dump not found. Install postgresql-client."

    if [[ -z "$SOURCE_DB_HOST" ]]; then
      echo "No --file provided and SOURCE_DB_HOST is empty."
      echo "Options:"
      echo "  1) Enter a remote PostgreSQL host to dump from"
      echo "  2) Abort and use --file to import a local dump:"
      echo "     sudo bash $0 migrate --file /path/to/dump.sql"
      echo ""
      read -rp "Source PostgreSQL host (e.g. 192.168.1.50): " SOURCE_DB_HOST
      [[ -z "$SOURCE_DB_HOST" ]] && error "Source host is required."
    fi
    if [[ -z "$SOURCE_DB_PASSWORD" ]]; then
      read -rsp "Source PostgreSQL password for ${SOURCE_DB_USER}@${SOURCE_DB_HOST}: " SOURCE_DB_PASSWORD
      echo ""
      [[ -z "$SOURCE_DB_PASSWORD" ]] && error "Source password is required."
    fi

    info "Source: ${SOURCE_DB_USER}@${SOURCE_DB_HOST}:${SOURCE_DB_PORT}/${SOURCE_DB_NAME}"
    info "Target: ${DB_USER}@localhost:5432/${DB_NAME}"

    # Test connectivity to source
    info "Testing connection to source database..."
    if ! PGPASSWORD="$SOURCE_DB_PASSWORD" psql -h "$SOURCE_DB_HOST" -p "$SOURCE_DB_PORT" \
         -U "$SOURCE_DB_USER" -d "$SOURCE_DB_NAME" -c "SELECT 1;" >/dev/null 2>&1; then
      error "Cannot connect to source database. Check host/port/credentials and that\n" \
            "  the source host allows connections from this VM's IP.\n" \
            "  You may need to add this VM's IP to pg_hba.conf on the source:\n" \
            "    host  ${SOURCE_DB_NAME}  ${SOURCE_DB_USER}  <VM_IP>/32  scram-sha-256"
    fi
    success "Source database reachable"

    # Dump
    DUMP_FILE="$DUMP_DIR/migration_$(date +%Y%m%d_%H%M%S).sql"

    info "Running pg_dump from source (this may take a few minutes)..."
    PGPASSWORD="$SOURCE_DB_PASSWORD" pg_dump \
      -h "$SOURCE_DB_HOST" \
      -p "$SOURCE_DB_PORT" \
      -U "$SOURCE_DB_USER" \
      -d "$SOURCE_DB_NAME" \
      --no-owner \
      --no-privileges \
      --clean \
      --if-exists \
      -f "$DUMP_FILE"

    DUMP_SIZE=$(stat --format="%s" "$DUMP_FILE" 2>/dev/null || stat -f "%z" "$DUMP_FILE" 2>/dev/null)
    if [[ "$DUMP_SIZE" -lt 100 ]]; then
      error "Dump file is suspiciously small ($DUMP_SIZE bytes). Aborting."
    fi
    success "Dump complete: $DUMP_FILE ($(numfmt --to=iec "$DUMP_SIZE" 2>/dev/null || echo "${DUMP_SIZE} bytes"))"

    # Count tables/rows in source for later verification
    info "Counting source tables for verification..."
    SOURCE_TABLES=$(PGPASSWORD="$SOURCE_DB_PASSWORD" psql -h "$SOURCE_DB_HOST" -p "$SOURCE_DB_PORT" \
      -U "$SOURCE_DB_USER" -d "$SOURCE_DB_NAME" -tAc \
      "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
    SOURCE_ROWS=$(PGPASSWORD="$SOURCE_DB_PASSWORD" psql -h "$SOURCE_DB_HOST" -p "$SOURCE_DB_PORT" \
      -U "$SOURCE_DB_USER" -d "$SOURCE_DB_NAME" -tAc \
      "SELECT sum(n_live_tup) FROM pg_stat_user_tables;")
    info "Source: $SOURCE_TABLES tables, ~$SOURCE_ROWS rows (approximate)"
  fi

  # Restore into local DB
  info "Restoring dump into local database ${DB_NAME}..."
  PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -f "$DUMP_FILE" \
    >/dev/null 2>&1 || warn "Some restore warnings (typically 'does not exist' for --clean drops — non‑fatal)"

  # Re‑grant read‑only privileges (dump's --no-privileges won't include them)
  sudo -u postgres psql -d "$DB_NAME" -c "GRANT USAGE ON SCHEMA public TO ${WEB_DB_USER};" 2>/dev/null || true
  sudo -u postgres psql -d "$DB_NAME" -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO ${WEB_DB_USER};" 2>/dev/null || true

  # Verify
  info "Verifying migration..."
  TARGET_TABLES=$(PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';")
  TARGET_ROWS=$(PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -tAc \
    "SELECT sum(n_live_tup) FROM pg_stat_user_tables;" 2>/dev/null || echo "0")

  echo ""
  echo "  ┌──────────────────────────────────────────────┐"
  echo "  │  Migration Verification                      │"
  echo "  ├────────────┬──────────────┬──────────────────┤"
  echo "  │            │   Source     │   Target (VM)    │"
  echo "  ├────────────┼──────────────┼──────────────────┤"
  printf "  │ Tables     │ %10s   │ %14s   │\n" "$SOURCE_TABLES" "$TARGET_TABLES"
  printf "  │ Rows (≈)   │ %10s   │ %14s   │\n" "$SOURCE_ROWS" "$TARGET_ROWS"
  echo "  └────────────┴──────────────┴──────────────────┘"
  echo ""

  if [[ "$SOURCE_TABLES" == "$TARGET_TABLES" ]]; then
    success "Table count matches! Migration looks good."
  else
    warn "Table count mismatch: source=$SOURCE_TABLES target=$TARGET_TABLES"
    warn "Check schema differences. You may also run the schema file:"
    warn "  PGPASSWORD='...' psql -h 127.0.0.1 -U $DB_USER -d $DB_NAME -f $APP_DIR/tools/schema_postgresql.sql"
  fi

  # Spot‑check key tables
  info "Spot‑checking critical tables..."
  for table in rounds player_comprehensive_stats processed_files player_links; do
    count=$(PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -tAc \
      "SELECT count(*) FROM ${table};" 2>/dev/null || echo "MISSING")
    printf "  %-35s %s rows\n" "$table" "$count"
  done

  echo ""
  success "Database migration complete.  Dump saved at: $DUMP_FILE"
  info ""
  info "Next: test the website against the migrated data:"
  info "  sudo systemctl start slomix-web"
  info "  curl -s http://localhost:${WEBSITE_PORT}/api/health | head"
  info ""
  info "If everything looks good, proceed to Phase 3 (tunnel):"
  info "  sudo bash $0 tunnel"
}

# ===========================================================================
# Sub‑command: tunnel  (Phase 3)
# Interactive Cloudflare Tunnel setup — login, create, configure, DNS, test.
# ===========================================================================
do_tunnel() {
  banner "PHASE 3 — CLOUDFLARE TUNNEL SETUP"

  command -v cloudflared >/dev/null 2>&1 || error "cloudflared is not installed. Run the base setup first."

  echo "This wizard will walk you through creating a Cloudflare Tunnel."
  echo "You need:"
  echo "  • A Cloudflare account (free)"
  echo "  • Your domain ($DOMAIN_NAME) added to Cloudflare with nameservers updated"
  echo ""

  # ---- Step 1: Login ----
  CF_CRED_DIR="/etc/cloudflared"
  if [[ ! -f "$CF_CRED_DIR/cert.pem" ]] && [[ ! -f "/root/.cloudflared/cert.pem" ]]; then
    info "Step 1/6: Authenticating with Cloudflare..."
    info "A browser URL will be printed — open it on any device to authorize."
    cloudflared tunnel login
    # cloudflared stores cert.pem in ~/.cloudflared/ by default
    if [[ -f "/root/.cloudflared/cert.pem" ]] && [[ ! -f "$CF_CRED_DIR/cert.pem" ]]; then
      cp /root/.cloudflared/cert.pem "$CF_CRED_DIR/cert.pem"
    fi
    success "Authenticated with Cloudflare"
  else
    success "Step 1/6: Already authenticated (cert.pem exists)"
  fi

  # ---- Step 2: Create tunnel ----
  TUNNEL_NAME="slomix-website"
  EXISTING_UUID=$(cloudflared tunnel list --output json 2>/dev/null | \
    python3 -c "import sys,json; tunnels=json.load(sys.stdin); print(next((t['id'] for t in tunnels if t['name']=='$TUNNEL_NAME'),''))" 2>/dev/null || true)

  if [[ -n "$EXISTING_UUID" ]]; then
    success "Step 2/6: Tunnel '$TUNNEL_NAME' already exists (UUID: $EXISTING_UUID)"
    TUNNEL_UUID="$EXISTING_UUID"
  else
    info "Step 2/6: Creating tunnel '$TUNNEL_NAME'..."
    TUNNEL_OUTPUT=$(cloudflared tunnel create "$TUNNEL_NAME" 2>&1)
    TUNNEL_UUID=$(echo "$TUNNEL_OUTPUT" | grep -oP '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}' | head -1)
    if [[ -z "$TUNNEL_UUID" ]]; then
      error "Failed to extract tunnel UUID from output:\n$TUNNEL_OUTPUT"
    fi
    success "Tunnel created: $TUNNEL_UUID"
  fi

  # ---- Step 3: Ensure credentials JSON is in /etc/cloudflared ----
  CRED_FILE="$CF_CRED_DIR/${TUNNEL_UUID}.json"
  if [[ ! -f "$CRED_FILE" ]]; then
    # cloudflared puts the creds in the user's home by default
    for search_dir in /root/.cloudflared "$HOME/.cloudflared"; do
      if [[ -f "$search_dir/${TUNNEL_UUID}.json" ]]; then
        cp "$search_dir/${TUNNEL_UUID}.json" "$CRED_FILE"
        break
      fi
    done
  fi
  if [[ ! -f "$CRED_FILE" ]]; then
    error "Credentials file not found at $CRED_FILE. Check ~/.cloudflared/"
  fi
  chown cloudflared:cloudflared "$CRED_FILE"
  chmod 600 "$CRED_FILE"
  success "Step 3/6: Credentials file in place"

  # ---- Step 4: Write config ----
  info "Step 4/6: Writing tunnel configuration..."
  cat > "$CF_CRED_DIR/config.yml" <<EOF
# Cloudflare Tunnel config for Slomix
# Generated by slomix_vm_setup.sh on $(date -Iseconds)
# Docs: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/

tunnel: ${TUNNEL_UUID}
credentials-file: ${CRED_FILE}

# What to expose — ONLY the website.  Everything else = 404.
ingress:
  - hostname: ${DOMAIN_NAME}
    service: http://127.0.0.1:${WEBSITE_PORT}
    originRequest:
      connectTimeout: 10s
      # noTLSVerify: false  (default — origin is plain HTTP, CF terminates TLS)

  # CRITICAL safety net: reject everything not matched above
  - service: http_status:404
EOF
  success "Config written to $CF_CRED_DIR/config.yml"

  # Validate config
  info "Validating ingress rules..."
  cloudflared tunnel ingress validate --config "$CF_CRED_DIR/config.yml"
  success "Ingress rules valid"

  # ---- Step 5: DNS CNAME ----
  info "Step 5/6: Routing DNS..."
  info "  Creating CNAME: $DOMAIN_NAME -> ${TUNNEL_UUID}.cfargotunnel.com"
  cloudflared tunnel route dns "$TUNNEL_NAME" "$DOMAIN_NAME" 2>/dev/null || \
    warn "DNS route may already exist (check Cloudflare dashboard)"
  success "DNS route configured"

  # ---- Step 6: Ensure cloudflared user owns everything ----
  chown -R cloudflared:cloudflared "$CF_CRED_DIR" /var/lib/cloudflared

  echo ""
  info "Step 6/6: Pre‑flight checklist"
  echo ""
  echo "  ✅ cloudflared installed:  $(cloudflared --version 2>&1 | head -1)"
  echo "  ✅ Tunnel UUID:            $TUNNEL_UUID"
  echo "  ✅ Config:                 $CF_CRED_DIR/config.yml"
  echo "  ✅ Credentials:            $CRED_FILE"
  echo "  ✅ DNS CNAME:              $DOMAIN_NAME"
  echo ""
  echo "  ┌───────────────────────────────────────────────────────────────┐"
  echo "  │  IMPORTANT: Set SSL/TLS mode in Cloudflare Dashboard         │"
  echo "  │                                                               │"
  echo "  │  Dashboard -> ${DOMAIN_NAME} -> SSL/TLS -> Overview           │"
  echo "  │  Set mode to: Full  (NOT Flexible, NOT Full Strict)           │"
  echo "  │  Reason: origin is HTTP; CF terminates TLS at the edge.       │"
  echo "  └───────────────────────────────────────────────────────────────┘"
  echo ""

  read -rp "Start slomix-web + cloudflared now for testing? [y/N] " ANSWER
  if [[ "${ANSWER,,}" == "y" ]]; then
    systemctl restart slomix-web
    systemctl restart cloudflared
    sleep 3
    info "Services starting..."
    echo ""
    systemctl --no-pager status slomix-web  | head -5
    echo ""
    systemctl --no-pager status cloudflared | head -5
    echo ""
    info "Test locally:   curl -s http://localhost:${WEBSITE_PORT}/api/health"
    info "Test via tunnel: curl -sI https://${DOMAIN_NAME}"
    echo ""
    info "If the tunnel works, set up Zero Trust Access (email OTP gate):"
    info "  https://one.dash.cloudflare.com → Access → Applications → Add Self‑Hosted"
    info "  Domain: $DOMAIN_NAME  |  Policy: Allow specific emails"
  else
    info "When ready, start services manually:"
    info "  sudo systemctl start slomix-web"
    info "  sudo systemctl start cloudflared"
  fi
}

# ===========================================================================
# Sub‑command: cutover  (Phase 5)
# Start all VM services.  Run this once the old host's services are stopped.
# ===========================================================================
do_cutover() {
  banner "PHASE 5 — CUTOVER TO VM"

  echo "This will start ALL services on this VM:"
  echo "  • slomix-bot   (Discord bot)"
  echo "  • slomix-web   (FastAPI website)"
  echo "  • cloudflared  (Cloudflare Tunnel)"
  echo ""
  echo "Make sure you have:"
  echo "  1. Filled in DISCORD_BOT_TOKEN in $BOT_ENV"
  echo "  2. Stopped the bot on the old host"
  echo "  3. Done a final database migration (or the bot will start fresh)"
  echo ""

  read -rp "Proceed with cutover? [y/N] " ANSWER
  if [[ "${ANSWER,,}" != "y" ]]; then
    info "Aborted."
    exit 0
  fi

  # Final fresh pull of latest code
  if [[ -d "$APP_DIR/.git" ]]; then
    info "Pulling latest code..."
    git -C "$APP_DIR" pull origin "$REPO_BRANCH" || warn "Git pull failed (non‑fatal)"
    chown -R "$BOT_USER:$SLX_GROUP" "$APP_DIR"
    chmod -R g+rX "$APP_DIR"
  fi

  # If .env has empty DISCORD_BOT_TOKEN, abort
  TOKEN=$(load_env_var "$BOT_ENV" DISCORD_BOT_TOKEN)
  if [[ -z "$TOKEN" ]]; then
    error "DISCORD_BOT_TOKEN is empty in $BOT_ENV!  Fill it in first."
  fi

  info "Starting services..."
  systemctl restart postgresql
  systemctl restart redis-server
  systemctl restart slomix-bot
  systemctl restart slomix-web
  systemctl restart cloudflared
  sleep 3

  echo ""
  for svc in postgresql redis-server slomix-bot slomix-web cloudflared; do
    if systemctl is-active --quiet "$svc"; then
      success "$svc is running"
    else
      warn "$svc is NOT running — check: journalctl -u $svc -n 30"
    fi
  done

  echo ""
  success "Cutover complete.  All services running on this VM."
  info "Monitor logs:  journalctl -u slomix-bot -u slomix-web -u cloudflared -f"
}

# ===========================================================================
# Sub‑command: status
# ===========================================================================
do_status() {
  banner "SERVICE STATUS"
  for svc in postgresql redis-server slomix-bot slomix-web cloudflared; do
    STATUS=$(systemctl is-active "$svc" 2>/dev/null || echo "not-found")
    ENABLED=$(systemctl is-enabled "$svc" 2>/dev/null || echo "not-found")
    printf "  %-20s active=%-12s enabled=%s\n" "$svc" "$STATUS" "$ENABLED"
  done
  echo ""

  # Quick DB check
  if systemctl is-active --quiet postgresql; then
    TABLE_COUNT=$(sudo -u postgres psql -d "$DB_NAME" -tAc \
      "SELECT count(*) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE';" 2>/dev/null || echo "?")
    ROUND_COUNT=$(PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -tAc \
      "SELECT count(*) FROM rounds;" 2>/dev/null || echo "?")
    echo "  Database: $DB_NAME  |  Tables: $TABLE_COUNT  |  Rounds: $ROUND_COUNT"
  fi

  # Tunnel check
  if command -v cloudflared >/dev/null 2>&1; then
    TUNNEL_COUNT=$(cloudflared tunnel list 2>/dev/null | grep -c "slomix" || echo "0")
    echo "  Tunnels matching 'slomix': $TUNNEL_COUNT"
  fi
}

# ===========================================================================
# Sub‑command dispatch  —  handle migrate / tunnel / cutover / status
# ===========================================================================
SUBCOMMAND="${1:-setup}"
shift 2>/dev/null || true   # remove subcommand from $@, leaving flags like --file

case "$SUBCOMMAND" in
  migrate)
    do_migrate "$@"
    exit 0
    ;;
  tunnel)
    do_tunnel
    exit 0
    ;;
  cutover)
    do_cutover
    exit 0
    ;;
  status)
    do_status
    exit 0
    ;;
  setup)
    # Fall through to the main setup below
    ;;
  *)
    echo "Usage: $0 [setup|migrate|tunnel|cutover|status]"
    exit 1
    ;;
esac

# ===========================================================================
# PHASE 1 — FULL SETUP  (only runs for `setup` sub‑command)
# ===========================================================================
banner "PHASE 1 — VM SETUP"

# ===========================================================================
# System users & group
# ===========================================================================
if ! getent group "$SLX_GROUP" >/dev/null; then
  info "Creating group $SLX_GROUP"
  groupadd --system "$SLX_GROUP"
fi

create_service_user() {
  local user="$1"
  if ! id "$user" >/dev/null 2>&1; then
    info "Creating service user $user"
    useradd --system --gid "$SLX_GROUP" --home-dir "$APP_DIR" --shell /usr/sbin/nologin "$user"
  fi
}

create_service_user "$BOT_USER"
create_service_user "$WEB_USER"

# ===========================================================================
# System packages
# ===========================================================================
info "Updating package index and installing prerequisites"
export DEBIAN_FRONTEND=noninteractive
apt-get update -qq
apt-get install -y -qq \
  python3 python3-venv python3-pip python3-dev \
  git postgresql postgresql-contrib libpq-dev \
  ufw curl unzip \
  redis-server \
  unattended-upgrades \
  build-essential >/dev/null

# Enable automatic security updates
info "Configuring unattended-upgrades"
systemctl enable unattended-upgrades.service >/dev/null || true

# ===========================================================================
# SSH hardening
# ===========================================================================
info "Hardening SSH configuration"
SSHD_CFG="/etc/ssh/sshd_config"
sed -i 's/^#\?PasswordAuthentication.*/PasswordAuthentication no/' "$SSHD_CFG"
sed -i 's/^#\?PermitRootLogin.*/PermitRootLogin no/' "$SSHD_CFG"
systemctl reload sshd || systemctl restart sshd

# ===========================================================================
# Firewall (UFW)
# ===========================================================================
info "Configuring firewall with ufw"
ufw default deny incoming
ufw default allow outgoing

if [[ -n "$SSH_ALLOWED_NET" ]]; then
  ufw allow from "$SSH_ALLOWED_NET" to any port 22 proto tcp
else
  ufw allow proto tcp to any port 22
fi

# Only enable ufw if not already enabled
if ufw status | grep -q inactive; then
  echo "y" | ufw enable >/dev/null
fi
success "Firewall configured"

# ===========================================================================
# Redis – bind to localhost only
# ===========================================================================
info "Securing Redis (localhost‑only)"
REDIS_CONF="/etc/redis/redis.conf"
if [[ -f "$REDIS_CONF" ]]; then
  sed -i 's/^bind .*/bind 127.0.0.1 ::1/' "$REDIS_CONF"
  sed -i 's/^# *protected-mode yes/protected-mode yes/' "$REDIS_CONF"
  systemctl restart redis-server
fi
success "Redis configured"

# ===========================================================================
# Clone / update repository
# ===========================================================================
info "Setting up application in $APP_DIR"
mkdir -p "$APP_DIR"

if [[ ! -d "$APP_DIR/.git" ]]; then
  info "Cloning repository from $REPO_URL (branch $REPO_BRANCH)"
  git clone --depth 1 -b "$REPO_BRANCH" "$REPO_URL" "$APP_DIR"
else
  info "Repository already exists – pulling latest changes"
  git -C "$APP_DIR" pull origin "$REPO_BRANCH"
fi

# Set ownership: BOT_USER owns, SLX_GROUP can read (both services share code)
chown -R "$BOT_USER:$SLX_GROUP" "$APP_DIR"
chmod -R g+rX "$APP_DIR"

# Create runtime directories the bot and website expect
for dir in local_stats logs processed_stats website/logs website/data website/data/uploads; do
  mkdir -p "$APP_DIR/$dir"
done
chown -R "$BOT_USER:$SLX_GROUP" "$APP_DIR/local_stats" "$APP_DIR/logs" "$APP_DIR/processed_stats"
chown -R "$WEB_USER:$SLX_GROUP" "$APP_DIR/website/logs" "$APP_DIR/website/data"
chmod -R g+rwX "$APP_DIR/local_stats" "$APP_DIR/logs" "$APP_DIR/processed_stats" \
               "$APP_DIR/website/logs" "$APP_DIR/website/data"

# Create SSH key directory for the bot user (for game server polling later)
mkdir -p "$BOT_SSH_DIR"
chown "$BOT_USER:$SLX_GROUP" "$BOT_SSH_DIR"
chmod 700 "$BOT_SSH_DIR"

# ===========================================================================
# PostgreSQL
# ===========================================================================
# Determine PostgreSQL major version
PG_VER=$(pg_lsclusters --no-header | awk '{print $1}' | head -n1)
if [[ -z "$PG_VER" ]]; then
  PG_VER=$(psql --version | awk '{print $3}' | cut -d'.' -f1)
fi

info "Configuring PostgreSQL $PG_VER to use scram-sha-256 and bind to localhost"
PG_CONF="/etc/postgresql/${PG_VER}/main/postgresql.conf"
PG_HBA="/etc/postgresql/${PG_VER}/main/pg_hba.conf"

sed -i "s/^#\?listen_addresses.*/listen_addresses = 'localhost'/" "$PG_CONF"
sed -i "s/^#\?password_encryption.*/password_encryption = scram-sha-256/" "$PG_CONF"

cat > "$PG_HBA" <<EOF
# TYPE  DATABASE        USER            ADDRESS                 METHOD
local   all             postgres                                peer
local   all             all                                     scram-sha-256
host    all             all             127.0.0.1/32            scram-sha-256
host    all             all             ::1/128                 scram-sha-256
EOF

systemctl restart postgresql

# ---------- Create roles & database ----------
info "Creating PostgreSQL roles and database"

# Main bot user (read‑write)
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}';" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASSWORD}';"

# Website read‑only user
sudo -u postgres psql -tc "SELECT 1 FROM pg_roles WHERE rolname = '${WEB_DB_USER}';" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE USER ${WEB_DB_USER} WITH PASSWORD '${WEB_DB_PASSWORD}';"

# Database
sudo -u postgres psql -tc "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}';" | grep -q 1 || \
  sudo -u postgres psql -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER};"

# Privileges
sudo -u postgres psql -c "GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};"
sudo -u postgres psql -c "GRANT CONNECT ON DATABASE ${DB_NAME} TO ${WEB_DB_USER};"

# ---------- Apply schema ----------
SCHEMA_FILE="$APP_DIR/tools/schema_postgresql.sql"
if [[ -f "$SCHEMA_FILE" ]]; then
  info "Applying database schema from tools/schema_postgresql.sql"
  PGPASSWORD="$DB_PASSWORD" psql -h 127.0.0.1 -U "$DB_USER" -d "$DB_NAME" -f "$SCHEMA_FILE" >/dev/null 2>&1 || \
    info "Schema may already exist (non‑fatal)"
fi

# Grant read‑only for website user on all existing tables
sudo -u postgres psql -d "$DB_NAME" -c "GRANT USAGE ON SCHEMA public TO ${WEB_DB_USER};"
sudo -u postgres psql -d "$DB_NAME" -c "GRANT SELECT ON ALL TABLES IN SCHEMA public TO ${WEB_DB_USER};"
sudo -u postgres psql -d "$DB_NAME" -c "ALTER DEFAULT PRIVILEGES FOR USER ${DB_USER} IN SCHEMA public GRANT SELECT ON TABLES TO ${WEB_DB_USER};"

success "PostgreSQL configured (DB=$DB_NAME, main user=$DB_USER, readonly=$WEB_DB_USER)"

# ===========================================================================
# Python virtual environments
# ===========================================================================
info "Creating Python virtual environments and installing dependencies"

python3 -m venv "$BOT_VENV"
python3 -m venv "$WEB_VENV"

# Upgrade pip
"$BOT_VENV/bin/pip" install --upgrade pip >/dev/null
"$WEB_VENV/bin/pip" install --upgrade pip >/dev/null

# Bot uses the root requirements.txt
if [[ -f "$APP_DIR/requirements.txt" ]]; then
  info "Installing bot dependencies from requirements.txt"
  "$BOT_VENV/bin/pip" install -r "$APP_DIR/requirements.txt" >/dev/null
fi

# Website uses its OWN requirements.txt
if [[ -f "$APP_DIR/website/requirements.txt" ]]; then
  info "Installing website dependencies from website/requirements.txt"
  "$WEB_VENV/bin/pip" install -r "$APP_DIR/website/requirements.txt" >/dev/null
fi

# Fix ownership of venvs
chown -R "$BOT_USER:$SLX_GROUP" "$BOT_VENV"
chown -R "$WEB_USER:$SLX_GROUP" "$WEB_VENV"

success "Python environments ready"

# ===========================================================================
# .env files
# ===========================================================================

if [[ ! -f "$BOT_ENV" ]]; then
  info "Creating bot .env file at $BOT_ENV"
  cat > "$BOT_ENV" <<EOF
# ==============================================
# Slomix Discord Bot – .env
# Generated by slomix_vm_setup.sh on $(date -Iseconds)
# See .env.example for full reference
# ==============================================

# ---- Database (PostgreSQL) ----
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=${DB_NAME}
POSTGRES_USER=${DB_USER}
POSTGRES_PASSWORD=${DB_PASSWORD}
POSTGRES_MIN_POOL=10
POSTGRES_MAX_POOL=30

# ---- Discord (REQUIRED – fill these in!) ----
DISCORD_BOT_TOKEN=
DISCORD_GUILD_ID=
STATS_CHANNEL_ID=
ADMIN_CHANNEL_ID=
OWNER_USER_ID=

# Voice channels to monitor for session detection (comma‑separated IDs)
GAMING_VOICE_CHANNELS=
# Text channels where bot commands work (comma‑separated IDs)
BOT_COMMAND_CHANNELS=

# ---- Session Detection ----
SESSION_GAP_MINUTES=60
ROUND_MATCH_WINDOW_MINUTES=45
MONITORING_GRACE_PERIOD_MINUTES=45
SESSION_START_THRESHOLD=6
SESSION_END_THRESHOLD=2
SESSION_END_DELAY=300

# ---- File Paths ----
LOCAL_STATS_PATH=./local_stats
STATS_DIRECTORY=local_stats

# ---- SSH Monitoring (fill in to auto‑download stats from game server) ----
SSH_ENABLED=false
SSH_HOST=
SSH_PORT=22
SSH_USER=
SSH_KEY_PATH=${BOT_SSH_DIR}/etlegacy_bot
REMOTE_STATS_PATH=
SSH_CHECK_INTERVAL=60
SSH_STARTUP_LOOKBACK_HOURS=24
SSH_VOICE_CONDITIONAL=true
SSH_GRACE_PERIOD_MINUTES=10
SSH_STRICT_HOST_KEY=true

# ---- Automation ----
AUTOMATION_ENABLED=false
STARTUP_LOOKBACK_HOURS=168

# ---- Misc ----
LOG_LEVEL=INFO
EOF
  chmod 640 "$BOT_ENV"
  chown "$BOT_USER:$SLX_GROUP" "$BOT_ENV"
fi

if [[ ! -f "$WEBSITE_ENV" ]]; then
  info "Creating website .env file at $WEBSITE_ENV"
  cat > "$WEBSITE_ENV" <<EOF
# ==============================================
# Slomix FastAPI Website – .env
# Generated by slomix_vm_setup.sh on $(date -Iseconds)
# See website/.env.example for full reference
# ==============================================

# ---- Database (read‑only) ----
DATABASE_TYPE=postgresql
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
POSTGRES_DATABASE=${DB_NAME}
POSTGRES_USER=${WEB_DB_USER}
POSTGRES_PASSWORD=${WEB_DB_PASSWORD}
POSTGRES_MIN_POOL=2
POSTGRES_MAX_POOL=10

# ---- Web Server ----
WEBSITE_HOST=127.0.0.1
WEBSITE_PORT=${WEBSITE_PORT}
WEBSITE_RELOAD=false

# ---- Session & Security ----
SESSION_SECRET=${SESSION_SECRET}

# ---- CORS ----
CORS_ORIGINS=http://localhost:${WEBSITE_PORT},http://127.0.0.1:${WEBSITE_PORT},https://${DOMAIN_NAME}

# ---- Discord OAuth2 (optional – fill in for user login) ----
DISCORD_CLIENT_ID=
DISCORD_CLIENT_SECRET=
DISCORD_REDIRECT_URI=https://${DOMAIN_NAME}/auth/callback
DISCORD_REDIRECT_URI_ALLOWLIST=https://${DOMAIN_NAME}/auth/callback

# ---- Cache (Redis) ----
CACHE_BACKEND=redis
REDIS_URL=redis://localhost:6379/0

# ---- Rate Limiting ----
RATE_LIMIT_ENABLED=true

# ---- Misc ----
LOG_LEVEL=INFO
EOF
  chmod 640 "$WEBSITE_ENV"
  chown "$WEB_USER:$SLX_GROUP" "$WEBSITE_ENV"
fi

success ".env files created"

# ===========================================================================
# systemd services
# ===========================================================================

# ---- Discord bot ----
BOT_SERVICE_FILE="/etc/systemd/system/slomix-bot.service"
info "Writing systemd unit for Discord bot"
cat > "$BOT_SERVICE_FILE" <<EOF
[Unit]
Description=Slomix Discord Bot (ET:Legacy Stats)
After=network.target postgresql.service redis-server.service
Requires=postgresql.service

[Service]
Type=simple
User=${BOT_USER}
Group=${SLX_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${BOT_ENV}
# Module invocation (-m) ensures correct import resolution
ExecStart=${BOT_VENV}/bin/python3 -m bot.ultimate_bot
Restart=always
RestartSec=5
# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=yes
ReadWritePaths=${APP_DIR}

[Install]
WantedBy=multi-user.target
EOF

# ---- FastAPI website ----
WEB_SERVICE_FILE="/etc/systemd/system/slomix-web.service"
info "Writing systemd unit for FastAPI website"
cat > "$WEB_SERVICE_FILE" <<EOF
[Unit]
Description=Slomix FastAPI Website (ET:Legacy Stats)
After=network.target postgresql.service redis-server.service
Wants=postgresql.service redis-server.service

[Service]
Type=simple
User=${WEB_USER}
Group=${SLX_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${WEBSITE_ENV}
ExecStart=${WEB_VENV}/bin/python3 -m uvicorn website.backend.main:app --host 127.0.0.1 --port ${WEBSITE_PORT}
Restart=always
RestartSec=5
# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=full
ProtectHome=yes
ReadWritePaths=${APP_DIR}

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable slomix-bot.service slomix-web.service

# Do NOT auto‑start: user must fill in DISCORD_BOT_TOKEN first
info "Services enabled but NOT started – fill in .env files first, then:"
info "  sudo systemctl start slomix-bot slomix-web"

# ===========================================================================
# Logrotate — prevent logs from filling the disk
# ===========================================================================
info "Configuring logrotate for application logs"
cat > /etc/logrotate.d/slomix <<EOF
${APP_DIR}/logs/*.log ${APP_DIR}/website/logs/*.log {
    daily
    missingok
    rotate 14
    compress
    delaycompress
    notifempty
    create 0640 ${BOT_USER} ${SLX_GROUP}
    sharedscripts
}
EOF

# ===========================================================================
# Cloudflare Tunnel — install binary + create system user (config in Phase 3)
# ===========================================================================
if ! command -v cloudflared >/dev/null 2>&1; then
  info "Installing cloudflared"
  TEMP_DEB=$(mktemp)
  arch=$(dpkg --print-architecture)
  curl -fsSL -o "$TEMP_DEB" "https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-${arch}.deb"
  dpkg -i "$TEMP_DEB" >/dev/null || apt-get install -f -y >/dev/null
  rm -f "$TEMP_DEB"
fi

mkdir -p /etc/cloudflared

# Create cloudflared systemd service skeleton
CF_SERVICE_FILE="/etc/systemd/system/cloudflared.service"
if [[ ! -f "$CF_SERVICE_FILE" ]]; then
  info "Creating cloudflared systemd service"
  cat > "$CF_SERVICE_FILE" <<'EOF'
[Unit]
Description=Cloudflare Tunnel agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=cloudflared
ExecStart=/usr/bin/cloudflared --config /etc/cloudflared/config.yml tunnel run
Restart=always
RestartSec=5s
NoNewPrivileges=yes

[Install]
WantedBy=multi-user.target
EOF
fi

if ! id cloudflared >/dev/null 2>&1; then
  useradd --system --home-dir /var/lib/cloudflared --shell /usr/sbin/nologin cloudflared
fi
mkdir -p /var/lib/cloudflared
chown cloudflared:cloudflared /var/lib/cloudflared /etc/cloudflared

systemctl daemon-reload
systemctl enable cloudflared.service
# NOT started — Phase 3 (tunnel wizard) handles that

success "cloudflared installed (tunnel not configured yet — run: sudo $0 tunnel)"

# ===========================================================================
# Phase 1 complete — Summary & Next Steps
# ===========================================================================
cat <<SUMMARY

========================================================================
  PHASE 1 COMPLETE — VM is ready for migration
========================================================================

Services installed (all STOPPED — nothing running yet):
  • slomix-bot.service   (Discord bot)
  • slomix-web.service   (FastAPI website on port ${WEBSITE_PORT})
  • cloudflared.service  (Cloudflare Tunnel — needs Phase 3 setup)
  • redis-server.service (cache, localhost only — running)
  • postgresql.service   (database — running, empty schema applied)

PostgreSQL:
  • Database:       ${DB_NAME}
  • Bot user:       ${DB_USER}  (password in ${BOT_ENV})
  • Web user:       ${WEB_DB_USER}  (read‑only, password in ${WEBSITE_ENV})
  • Schema:         Applied from tools/schema_postgresql.sql

File locations:
  • Application:    ${APP_DIR}
  • Bot .env:       ${BOT_ENV}
  • Website .env:   ${WEBSITE_ENV}
  • Bot venv:       ${BOT_VENV}
  • Website venv:   ${WEB_VENV}
  • Bot SSH keys:   ${BOT_SSH_DIR}/

Firewall:
  • SSH allowed from: ${SSH_ALLOWED_NET:-everywhere}
  • All other inbound: denied

========================================================================
  MIGRATION ROADMAP
========================================================================

  Phase 2 — MIGRATE DATABASE:
  ───────────────────────────
    Option A — Remote dump (pull over LAN):
      On the source host, allow connections from this VM:
        # Add to pg_hba.conf on source host:
        host  ${DB_NAME}  ${DB_USER}  <THIS_VM_IP>/32  scram-sha-256
        # Then: sudo systemctl reload postgresql
      Then run:  sudo bash $0 migrate

    Option B — Local dump file (you dump + copy manually):
      On the source host:
        pg_dump -U ${DB_USER} -d ${DB_NAME} --no-owner --no-privileges -f dump.sql
        scp dump.sql user@<THIS_VM_IP>:/opt/slomix/migration/
      Then run:  sudo bash $0 migrate --file /opt/slomix/migration/dump.sql

    Both options verify table/row counts after import.

  Phase 3 — CLOUDFLARE TUNNEL (expose website to internet):
  ─────────────────────────────────────────────────────────
    Prerequisites:
      • Cloudflare account (free) at https://dash.cloudflare.com
      • Domain ${DOMAIN_NAME} added to Cloudflare with NS updated

    Run on this VM:
      sudo bash $0 tunnel

    This walks you through login → create → config → DNS → test.

  Phase 4 — TEST:
  ────────────────
    • Start website on VM:  sudo systemctl start slomix-web
    • Browse: https://${DOMAIN_NAME}  (through Cloudflare Tunnel)
    • Check API: curl http://localhost:${WEBSITE_PORT}/api/health
    • Compare data — everything should match the source

  Phase 5 — CUTOVER (when ready):
  ────────────────────────────────
    1. Fill in ${BOT_ENV} with DISCORD_BOT_TOKEN and channel IDs
    2. Stop bot + website on the old host
    3. Run final migration:  sudo bash $0 migrate
    4. Cut over:             sudo bash $0 cutover
    5. Verify:               sudo bash $0 status

  At any time, check status:
      sudo bash $0 status

========================================================================
SUMMARY

