#!/usr/bin/env bash
# deploy_clean.sh — Deploy minimal clean codebase to slomix production VM
#
# Creates a tar of ONLY essential files locally, scp's it to the VM, and extracts.
# No rsync needed (VM doesn't have it). Protects .env, venvs, local_stats, data, logs.
#
# Usage:
#   ./scripts/deploy_clean.sh                   # preview + confirm + deploy
#   ./scripts/deploy_clean.sh --dry-run         # show what would be deployed
#   ./scripts/deploy_clean.sh --yes             # skip confirmation
#   ./scripts/deploy_clean.sh --clean           # remove trash dirs/files first
#   ./scripts/deploy_clean.sh --update-deps     # reinstall pip packages in venvs
#   ./scripts/deploy_clean.sh --schema          # force schema apply
#   ./scripts/deploy_clean.sh --no-logs         # skip log tail
#   ./scripts/deploy_clean.sh --clean --update-deps --yes  # full first-run
#
# Deploy order:
#   1. Build list of essential files
#   2. Preview file list
#   3. Confirm with user
#   4. Stop services on VM
#   5. [--clean] Remove trash dirs/files from VM
#   6. Create tar + scp + extract on VM
#   7. [--update-deps] pip install in both venvs
#   8. Apply DB schema (idempotent)
#   9. Fix ownership and permissions
#  10. Start services
#  11. Verify + tail logs

set -euo pipefail

# ─── Config ───────────────────────────────────────────────────────────────────
VM_HOST="192.168.64.159"
VM_USER="slomix"
VM_KEY="$HOME/.ssh/slomix_vm_ed25519"
VM_PATH="/opt/slomix"
LOCAL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

DRY_RUN=false
AUTO_YES=false
NO_LOGS=false
DO_CLEAN=false
UPDATE_DEPS=false
FORCE_SCHEMA=false
PUSH_GITHUB=false

for arg in "$@"; do
  case "$arg" in
    --dry-run)     DRY_RUN=true ;;
    --yes)         AUTO_YES=true ;;
    --no-logs)     NO_LOGS=true ;;
    --clean)       DO_CLEAN=true ;;
    --update-deps) UPDATE_DEPS=true ;;
    --schema)      FORCE_SCHEMA=true ;;
    --push-github) PUSH_GITHUB=true ;;
    --help|-h)
      echo "Usage: $0 [--dry-run] [--yes] [--clean] [--update-deps] [--schema] [--no-logs] [--push-github]"
      exit 0 ;;
    *) echo "Unknown flag: $arg"; exit 1 ;;
  esac
done

SSH="ssh -i $VM_KEY -o ConnectTimeout=10 $VM_USER@$VM_HOST"
SCP="scp -i $VM_KEY -o ConnectTimeout=10"

# ─── Sudo helper ──────────────────────────────────────────────────────────────
# Usage: SUDO_PASS=xxx bash deploy_clean.sh
sudo_run() {
  if [ -n "${SUDO_PASS:-}" ]; then
    $SSH "echo '$SUDO_PASS' | sudo -S $* 2>/dev/null"
  else
    $SSH "sudo -n $* 2>/dev/null"
  fi
}

# ─── Build essential file list ────────────────────────────────────────────────
build_file_list() {
  cd "$LOCAL_ROOT"

  # Bot package — all .py and .json files
  find bot/ -name '*.py' -not -path '*__pycache__*' 2>/dev/null
  find bot/ -name '*.json' -not -path '*__pycache__*' 2>/dev/null

  # Website backend — all .py files
  find website/backend/ -name '*.py' -not -path '*__pycache__*' 2>/dev/null

  # Website migrations
  find website/migrations/ -name '*.sql' 2>/dev/null

  # Website frontend
  echo "website/index.html"
  find website/js/ -name '*.js' 2>/dev/null
  [ -d website/css/ ] && find website/css/ -type f 2>/dev/null

  # Website assets (images, icons, etc.)
  find website/assets/ -type f 2>/dev/null

  # Website config/startup
  [ -f website/__init__.py ] && echo "website/__init__.py"
  [ -f website/start_website.sh ] && echo "website/start_website.sh"
  [ -f website/etlegacy-website.service ] && echo "website/etlegacy-website.service"
  [ -f website/.env.example ] && echo "website/.env.example"

  # Root essentials
  echo "requirements.txt"
  echo "postgresql_database_manager.py"

  # Greatshot package (website hard dependency)
  find greatshot/ -name '*.py' -not -path '*__pycache__*' -not -path '*tests/*' 2>/dev/null

  # Proximity parser (bot soft dependency, but needed for proximity cog)
  for f in proximity/__init__.py proximity/parser/__init__.py \
           proximity/parser/parser.py proximity/parser/extract_objective_coords.py; do
    [ -f "$f" ] && echo "$f"
  done

  # Tools (unified CLI + schema)
  for f in tools/__init__.py tools/slomix_backfill.py tools/slomix_audit.py \
           tools/slomix_rcon.py tools/slomix_proximity.py tools/slomix_retro.py \
           tools/schema_postgresql.sql; do
    [ -f "$f" ] && echo "$f"
  done

  # VPS scripts
  find vps_scripts/ -type f \( -name '*.py' -o -name '*.lua' \) 2>/dev/null
}

# ─── Header ───────────────────────────────────────────────────────────────────
echo ""
echo "╔════════════════════════════════════════╗"
echo "║   Slomix Clean Deploy                  ║"
echo "╠════════════════════════════════════════╣"
echo "  Target     : $VM_USER@$VM_HOST:$VM_PATH"
echo "  Source     : $LOCAL_ROOT"
echo "  Dry run    : $DRY_RUN"
echo "  Clean      : $DO_CLEAN"
echo "  Update deps: $UPDATE_DEPS"
echo "  Push GitHub: $PUSH_GITHUB"
echo "╚════════════════════════════════════════╝"
echo ""

# ─── Step 1: Build file list ─────────────────────────────────────────────────
echo "[ 1 ] Building file list..."

FILE_LIST=$(build_file_list | sort -u)
FILE_COUNT=$(echo "$FILE_LIST" | wc -l)

# Categorize
BOT_COUNT=$(echo "$FILE_LIST" | grep -c '^bot/' || true)
WEB_BACKEND=$(echo "$FILE_LIST" | grep -c '^website/backend/' || true)
WEB_FRONTEND=$(echo "$FILE_LIST" | grep -c '^website/js/\|^website/index' || true)
WEB_ASSETS=$(echo "$FILE_LIST" | grep -c '^website/assets/' || true)
WEB_MIGRATE=$(echo "$FILE_LIST" | grep -c '^website/migrations/' || true)
TOOL_COUNT=$(echo "$FILE_LIST" | grep -c '^tools/' || true)
VPS_COUNT=$(echo "$FILE_LIST" | grep -c '^vps_scripts/' || true)
ROOT_COUNT=$(echo "$FILE_LIST" | grep -c '^[^/]*$' || true)

echo "  Total: $FILE_COUNT files"
echo "    bot/             : $BOT_COUNT"
echo "    website/backend/ : $WEB_BACKEND"
echo "    website/js+html  : $WEB_FRONTEND"
echo "    website/assets/  : $WEB_ASSETS"
echo "    website/migrations/: $WEB_MIGRATE"
echo "    tools/           : $TOOL_COUNT"
echo "    vps_scripts/     : $VPS_COUNT"
echo "    root files       : $ROOT_COUNT"
echo ""

# ─── Step 2: Preview ─────────────────────────────────────────────────────────
if [ "$DRY_RUN" = true ]; then
  echo "[ 2 ] Full file list:"
  echo "$FILE_LIST" | sed 's/^/    /'
  echo ""
  echo "[DRY RUN] Would deploy $FILE_COUNT files to $VM_PATH"
  [ "$DO_CLEAN" = true ] && echo "[DRY RUN] Would clean trash dirs/files from VM."
  [ "$UPDATE_DEPS" = true ] && echo "[DRY RUN] Would update pip packages in both venvs."
  [ "$FORCE_SCHEMA" = true ] && echo "[DRY RUN] Would apply DB schema."
  echo ""
  exit 0
fi

# ─── Step 3: Confirm ─────────────────────────────────────────────────────────
if [ "$AUTO_YES" = false ]; then
  read -rp "  Deploy $FILE_COUNT files to $VM_HOST? [y/N] " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "  Aborted."
    exit 0
  fi
fi

# ─── Step 4: Stop services ───────────────────────────────────────────────────
echo ""
echo "[ 4 ] Stopping services..."
if sudo_run systemctl stop slomix-bot slomix-web; then
  echo "  Services stopped."
else
  echo "  [WARN] Could not stop services (pass SUDO_PASS=<password> to enable)."
  echo "         Files will still be copied. Restart manually after."
fi

# ─── Step 5: Clean trash (optional) ──────────────────────────────────────────
if [ "$DO_CLEAN" = true ]; then
  echo ""
  echo "[ 5 ] Cleaning trash from VM..."

  # Directories to remove (greatshot/ and proximity/ are kept — runtime deps)
  for dir in docs tests .github analytics monitoring scripts; do
    if $SSH "test -d $VM_PATH/$dir" 2>/dev/null; then
      sudo_run rm -rf "$VM_PATH/$dir" && echo "  Removed $dir/" || echo "  [WARN] Failed: $dir/"
    fi
  done

  # Root-level trash files
  TRASH_FILES=(
    "c0rnp0rn.lua" "c0rnp0rn7.lua"
    "freshinstall.sh" "install.sh"
    "start_bot.sh" "update_bot.sh"
    "pytest.ini" "pyproject.toml"
    "requirements-dev.txt"
    ".pre-commit-config.yaml"
    "config.json" "schema.sql"
    "README.md" "CLAUDE.md"
    ".codacy.yaml" ".claudeignore"
    ".gitignore"
  )

  for f in "${TRASH_FILES[@]}"; do
    if $SSH "test -e $VM_PATH/$f" 2>/dev/null; then
      sudo_run rm -f "$VM_PATH/$f" && echo "  Removed $f" || true
    fi
  done

  # Clean old bot subdirs that aren't needed
  for dir in bot/backups bot/bot bot/local_stats bot/logs bot/tools; do
    if $SSH "test -d $VM_PATH/$dir" 2>/dev/null; then
      sudo_run rm -rf "$VM_PATH/$dir" && echo "  Removed $dir/" || true
    fi
  done

  # Clean __pycache__ dirs
  $SSH "find $VM_PATH -name __pycache__ -type d -exec rm -rf {} + 2>/dev/null" || true
  echo "  Cleanup done."
else
  echo "[ 5 ] Skipping cleanup (use --clean for first run)"
fi

# ─── Step 6: Tar + SCP + Extract ─────────────────────────────────────────────
echo ""
echo "[ 6 ] Creating archive and deploying..."

TARBALL=$(mktemp --suffix=.tar.gz)
trap "rm -f $TARBALL" EXIT

cd "$LOCAL_ROOT"
echo "$FILE_LIST" | tar czf "$TARBALL" -T -
TARBALL_SIZE=$(du -h "$TARBALL" | cut -f1)
echo "  Archive: $TARBALL_SIZE"

# Ensure base dirs exist and are writable
sudo_run chmod -R g+w "$VM_PATH/bot/" 2>/dev/null || true
sudo_run chmod -R g+w "$VM_PATH/website/" 2>/dev/null || true
sudo_run chmod -R g+w "$VM_PATH/tools/" 2>/dev/null || true
sudo_run chmod g+w "$VM_PATH/" 2>/dev/null || true

# Upload and extract
VM_TARBALL="/tmp/slomix_deploy_$(date +%s).tar.gz"
$SCP "$TARBALL" "$VM_USER@$VM_HOST:$VM_TARBALL"
$SSH "cd $VM_PATH && tar xzf $VM_TARBALL && rm -f $VM_TARBALL"

echo "  $FILE_COUNT files deployed."

# ─── Step 7: Update deps (optional) ──────────────────────────────────────────
if [ "$UPDATE_DEPS" = true ]; then
  echo ""
  echo "[ 7 ] Updating Python packages..."

  echo "  Bot venv..."
  $SSH "$VM_PATH/venv-bot/bin/pip install --quiet -r $VM_PATH/requirements.txt 2>&1" | tail -5
  echo "  Bot packages updated."

  echo "  Web venv..."
  $SSH "$VM_PATH/venv-web/bin/pip install --quiet -r $VM_PATH/requirements.txt 2>&1" | tail -5
  echo "  Web packages updated."
else
  echo "[ 7 ] Skipping dep update (use --update-deps to reinstall)"
fi

# ─── Step 8: Apply DB schema ─────────────────────────────────────────────────
echo ""
echo "[ 8 ] Applying DB schema (IF NOT EXISTS — idempotent)..."

DB_PASS=$($SSH "grep -E '^POSTGRES_PASSWORD=' $VM_PATH/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\"'" || true)

if [ -z "$DB_PASS" ]; then
  echo "  [WARN] Could not read DB password — skipping schema step."
else
  SCHEMA_OUT=$($SSH "PGPASSWORD='$DB_PASS' psql -h localhost -U etlegacy_user -d etlegacy \
    -f $VM_PATH/tools/schema_postgresql.sql \
    -v ON_ERROR_STOP=0 2>&1 \
    | grep -cE 'CREATE TABLE|CREATE INDEX'" 2>/dev/null || echo "0")
  echo "  Schema applied ($SCHEMA_OUT new objects created)."
fi

# ─── Step 9: Fix ownership and permissions ────────────────────────────────────
echo ""
echo "[ 9 ] Fixing ownership and permissions..."

# Bot files — slomix_bot:slomix
sudo_run chown -R slomix_bot:slomix "$VM_PATH/bot/" 2>/dev/null || true
sudo_run chown slomix_bot:slomix "$VM_PATH/postgresql_database_manager.py" 2>/dev/null || true
sudo_run chown slomix_bot:slomix "$VM_PATH/requirements.txt" 2>/dev/null || true

# Website files — slomix_web:slomix
sudo_run chown -R slomix_web:slomix "$VM_PATH/website/" 2>/dev/null || true

# Tools and vps_scripts — slomix:slomix (deploy user)
sudo_run chown -R slomix:slomix "$VM_PATH/tools/" 2>/dev/null || true
sudo_run chown -R slomix:slomix "$VM_PATH/vps_scripts/" 2>/dev/null || true

# Cross-user read: website needs to read bot.* imports
sudo_run chmod -R g+rX "$VM_PATH/bot/" 2>/dev/null || true
sudo_run chmod -R g+rX "$VM_PATH/website/" 2>/dev/null || true
sudo_run chmod -R g+rX "$VM_PATH/tools/" 2>/dev/null || true

# Ensure logs dir exists
$SSH "mkdir -p $VM_PATH/logs/metrics" 2>/dev/null || true
sudo_run chown -R slomix_bot:slomix "$VM_PATH/logs/" 2>/dev/null || true
sudo_run chmod -R g+w "$VM_PATH/logs/" 2>/dev/null || true

echo "  Permissions fixed."

# ─── Step 10: Start services ─────────────────────────────────────────────────
echo ""
echo "[ 10 ] Starting services..."

NEEDS_MANUAL=false

if sudo_run systemctl start slomix-web; then
  echo "  slomix-web started."
  sleep 2
else
  echo "  [WARN] Could not start slomix-web."
  NEEDS_MANUAL=true
fi

if sudo_run systemctl start slomix-bot; then
  echo "  slomix-bot started."
  sleep 4
else
  echo "  [WARN] Could not start slomix-bot."
  NEEDS_MANUAL=true
fi

# ─── Step 11: Verify ─────────────────────────────────────────────────────────
echo ""
echo "[ 11 ] Verifying..."

WEB_STATUS=$($SSH "systemctl is-active slomix-web 2>/dev/null" || echo "failed")
BOT_STATUS=$($SSH "systemctl is-active slomix-bot 2>/dev/null" || echo "failed")

echo "  slomix-web : $WEB_STATUS"
echo "  slomix-bot : $BOT_STATUS"

if [ "$NEEDS_MANUAL" = true ] || [ "$WEB_STATUS" != "active" ] || [ "$BOT_STATUS" != "active" ]; then
  echo ""
  echo "  ┌──────────────────────────────────────────────────────┐"
  echo "  │  Manual restart needed — run on the VM:              │"
  echo "  │    sudo systemctl start slomix-web slomix-bot        │"
  echo "  │    sudo journalctl -u slomix-bot -f                  │"
  echo "  └──────────────────────────────────────────────────────┘"
fi

# VM file listing
echo ""
echo "  VM /opt/slomix contents:"
$SSH "ls $VM_PATH/" 2>/dev/null | sed 's/^/    /'

# ─── Tail logs ────────────────────────────────────────────────────────────────
if [ "$NO_LOGS" = false ]; then
  echo ""
  echo "  Bot logs (last 30 lines):"
  echo "  ──────────────────────────"
  { sudo_run journalctl -u slomix-bot -n 30 --no-pager --output=short-iso 2>/dev/null || echo '  (no log access)'; } \
    | grep -v '^-- ' | sed 's/^/    /'

  echo ""
  echo "  Web logs (last 15 lines):"
  echo "  ──────────────────────────"
  { sudo_run journalctl -u slomix-web -n 15 --no-pager --output=short-iso 2>/dev/null || echo '  (no log access)'; } \
    | grep -v '^-- ' | sed 's/^/    /'
fi

# ─── Step 12: Push clean snapshot to GitHub prod branch ─────────────────────
push_github_prod() {
  local SNAP_DIR
  SNAP_DIR=$(mktemp -d)

  cd "$SNAP_DIR"
  git init -q
  git remote add origin "$(git -C "$LOCAL_ROOT" remote get-url origin)"

  # Carry over git identity from main repo (or fall back to defaults)
  GIT_USER=$(git -C "$LOCAL_ROOT" config user.name 2>/dev/null || echo "Slomix Deploy")
  GIT_EMAIL=$(git -C "$LOCAL_ROOT" config user.email 2>/dev/null || echo "deploy@slomix.fyi")
  git config user.name "$GIT_USER"
  git config user.email "$GIT_EMAIL"

  # Base on existing prod history if it exists, else start orphan
  if git fetch origin prod --depth=1 -q 2>/dev/null; then
    git checkout -b prod FETCH_HEAD -q
    git rm -rf . -q 2>/dev/null || true
  else
    git checkout --orphan prod -q
  fi

  # Copy essential files from LOCAL_ROOT
  cd "$LOCAL_ROOT"
  echo "$FILE_LIST" | tar cf - -T - | tar xf - -C "$SNAP_DIR"

  cd "$SNAP_DIR"
  git add -A

  if git diff --cached --quiet; then
    echo "  No changes — prod branch already up to date."
  else
    NFILES=$(git diff --cached --name-only | wc -l | tr -d ' ')
    git commit -q -m "chore(deploy): clean prod snapshot $(date +%Y-%m-%d)"
    git push origin prod -q
    echo "  ✅ Pushed $NFILES files to origin/prod"
    echo "  GitHub: https://github.com/iamez/slomix/tree/prod"
  fi

  rm -rf "$SNAP_DIR"
}

if [ "$PUSH_GITHUB" = true ] && [ "$DRY_RUN" = false ]; then
  echo ""
  echo "[ 12 ] Pushing clean snapshot to GitHub (origin/prod)..."
  push_github_prod
fi

echo ""
echo "╔════════════════════════════════════════╗"
echo "║   Deploy complete                      ║"
echo "╚════════════════════════════════════════╝"
echo ""
echo "  Live logs:  ssh slomix-vm 'sudo journalctl -u slomix-bot -f'"
echo "  Website:    http://$VM_HOST:7000"
echo ""
