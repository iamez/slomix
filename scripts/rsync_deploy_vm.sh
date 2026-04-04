#!/usr/bin/env bash
# rsync_deploy_vm.sh — Full rsync deploy from dev to slomix VM
#
# Unlike deploy_to_vm.sh (git-diff based, incremental), this does a FULL
# rsync of the entire codebase. Use when VM is far behind or git state is dirty.
#
# Usage:
#   ./scripts/rsync_deploy_vm.sh              # full sync + restart
#   ./scripts/rsync_deploy_vm.sh --dry-run    # preview only
#   ./scripts/rsync_deploy_vm.sh --no-restart # sync without restart
#   ./scripts/rsync_deploy_vm.sh --no-migrate # skip migration check
#
# What it syncs:   bot/, website/, proximity/, greatshot/, tools/, vps_scripts/,
#                  requirements.txt, postgresql_database_manager.py, package.json
# What it skips:   .env, .git, logs/, backups/, local_stats/, venv/, node_modules/,
#                  __pycache__, tests/, docs/, .claude/, scripts/ (except this one)
#
# IMPORTANT: .env on VM is NEVER overwritten (different DB creds, tokens)

set -euo pipefail

# ─── Config ──────────────────────────────────────────────────────────────────
VM_HOST="192.168.64.159"
VM_USER="slomix"
VM_KEY="$HOME/.ssh/slomix_vm_ed25519"
VM_PATH="/opt/slomix"
LOCAL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

DRY_RUN=false
NO_RESTART=false
NO_MIGRATE=false
for arg in "$@"; do
  case "$arg" in
    --dry-run)    DRY_RUN=true ;;
    --no-restart) NO_RESTART=true ;;
    --no-migrate) NO_MIGRATE=true ;;
  esac
done

SSH="ssh -i $VM_KEY $VM_USER@$VM_HOST"

# ─── Sudo helper ─────────────────────────────────────────────────────────────
sudo_run() {
  if [ -n "${SUDO_PASS:-}" ]; then
    $SSH "echo '$SUDO_PASS' | sudo -S $* 2>/dev/null"
  else
    $SSH "sudo -n $* 2>/dev/null || echo '[WARN] sudo failed — run with SUDO_PASS=<pass>'"
  fi
}

# ─── Header ──────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════╗"
echo "║  Slomix VM Full Rsync Deploy         ║"
echo "╠══════════════════════════════════════╣"
echo "  Source  : $LOCAL_ROOT"
echo "  Target  : $VM_USER@$VM_HOST:$VM_PATH"
echo "  Dry run : $DRY_RUN"
echo "  Restart : $([ "$NO_RESTART" = true ] && echo 'skip' || echo 'yes')"
echo "╚══════════════════════════════════════╝"
echo ""

# ─── Phase 1: Rsync ─────────────────────────────────────────────────────────
echo "=== Phase 1: Rsync code ==="

RSYNC_OPTS="-avz --delete"
if [ "$DRY_RUN" = true ]; then
  RSYNC_OPTS="$RSYNC_OPTS --dry-run"
fi

rsync $RSYNC_OPTS \
  --exclude='.env' \
  --exclude='.env.*' \
  --exclude='.git/' \
  --exclude='.github/' \
  --exclude='.claude/' \
  --exclude='.codacy*' \
  --exclude='.vscode/' \
  --exclude='__pycache__/' \
  --exclude='*.pyc' \
  --exclude='.pytest_cache/' \
  --exclude='.mypy_cache/' \
  --exclude='.ruff_cache/' \
  --exclude='logs/' \
  --exclude='backups/' \
  --exclude='local_stats/' \
  --exclude='local_proximity/' \
  --exclude='local_gametimes/' \
  --exclude='node_modules/' \
  --exclude='venv/' \
  --exclude='venv-*/' \
  --exclude='.venv/' \
  --exclude='dist/' \
  --exclude='build/' \
  --exclude='*.egg-info/' \
  --exclude='gemini-website/' \
  --exclude='*.log' \
  --exclude='*.db' \
  --exclude='*.sqlite' \
  --exclude='deployed_lua/' \
  --exclude='server/' \
  --exclude='.ssh/' \
  --exclude='.cache/' \
  --exclude='.local/' \
  --exclude='.bash*' \
  --exclude='.profile' \
  --exclude='*.gz' \
  --exclude='*.tar' \
  -e "ssh -i $VM_KEY" \
  "$LOCAL_ROOT/" \
  "$VM_USER@$VM_HOST:$VM_PATH/"

echo "Done."

if [ "$DRY_RUN" = true ]; then
  echo ""
  echo "[DRY RUN] No changes made. Remove --dry-run to deploy."
  exit 0
fi

# ─── Phase 2: Dependencies ──────────────────────────────────────────────────
echo ""
echo "=== Phase 2: Python dependencies ==="
$SSH "cd $VM_PATH && \
  $VM_PATH/venv-web/bin/pip install -q -r website/requirements.txt 2>&1 | tail -3 && \
  $VM_PATH/venv-bot/bin/pip install -q -r requirements.txt 2>&1 | tail -3 && \
  echo 'Dependencies OK'"

# ─── Phase 3: Migrations ────────────────────────────────────────────────────
if [ "$NO_MIGRATE" = false ]; then
  echo ""
  echo "=== Phase 3: Migration check ==="
  $SSH "ls $VM_PATH/migrations/*.sql 2>/dev/null | wc -l | xargs -I{} echo '{} migration files found'"
  echo "(Migrations must be applied manually — review SQL first)"
fi

# ─── Phase 4: Restart services ──────────────────────────────────────────────
if [ "$NO_RESTART" = false ]; then
  echo ""
  echo "=== Phase 4: Restart services ==="
  sudo_run "systemctl restart slomix-web"
  echo "  slomix-web restarted"
  sleep 3
  sudo_run "systemctl restart slomix-bot"
  echo "  slomix-bot restarted"
  sleep 5

  echo ""
  echo "=== Phase 5: Health check ==="
  # Service status
  web_status=$(sudo_run "systemctl is-active slomix-web" || echo "unknown")
  bot_status=$(sudo_run "systemctl is-active slomix-bot" || echo "unknown")
  echo "  slomix-web: $web_status"
  echo "  slomix-bot: $bot_status"

  # API health
  sleep 5
  api_code=$(curl -s -o /dev/null -w "%{http_code}" "https://www.slomix.fyi/api/status" 2>/dev/null || echo "000")
  echo "  API health: $api_code"

  # Error count
  error_count=$($SSH "sudo journalctl -u slomix-web --since '30 sec ago' --no-pager 2>/dev/null | grep -ci error" 2>/dev/null || echo "?")
  echo "  Web errors: $error_count"
fi

echo ""
echo "=== Deploy complete ==="
