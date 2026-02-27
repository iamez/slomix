#!/usr/bin/env bash
# deploy_to_vm.sh — Deploy local code changes to slomix production VM
#
# Auto-detects changed files from git status. No hardcoded file lists.
#
# Usage:
#   ./scripts/deploy_to_vm.sh            # auto-detect + confirm + deploy
#   ./scripts/deploy_to_vm.sh --dry-run  # show what would happen, no changes
#   ./scripts/deploy_to_vm.sh --yes      # skip confirmation prompt
#   ./scripts/deploy_to_vm.sh --no-logs  # skip the live log tail at the end
#
# Deploy order:
#   1. Stop slomix-bot and slomix-web (no partial file loads mid-copy)
#   2. Fix group-write permissions (slomix_bot/slomix_web owned dirs)
#   3. scp each changed file individually (no rsync, no delete risk)
#   4. Apply tools/schema_postgresql.sql via psql (all IF NOT EXISTS — idempotent)
#   5. Start slomix-web, then slomix-bot
#   6. Tail bot + web logs to check for startup errors
#
# Auto-excludes: docs/, tests/, *.md, deployed_lua/, proximity/lua/, scripts/,
#   migrations/, monitoring/, .vscode/, config JSONs, .env, __pycache__, *.pyc
#
# NOTE: Services also run locally on samba — this script only touches the VM.

set -euo pipefail

# ─── Config ───────────────────────────────────────────────────────────────────
VM_HOST="192.168.64.159"
VM_USER="slomix"
VM_KEY="$HOME/.ssh/slomix_vm_ed25519"
VM_PATH="/opt/slomix"
LOCAL_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

DRY_RUN=false
NO_LOGS=false
AUTO_YES=false
for arg in "$@"; do
  case "$arg" in
    --dry-run) DRY_RUN=true ;;
    --no-logs) NO_LOGS=true ;;
    --yes)     AUTO_YES=true ;;
  esac
done

SCP="scp -i $VM_KEY -q"
SSH="ssh -i $VM_KEY $VM_USER@$VM_HOST"

# ─── Sudo helper ──────────────────────────────────────────────────────────────
# Usage: SUDO_PASS=123 bash deploy_to_vm.sh
sudo_run() {
  if [ -n "${SUDO_PASS:-}" ]; then
    $SSH "echo '$SUDO_PASS' | sudo -S $* 2>/dev/null"
  else
    $SSH "sudo -n $* 2>/dev/null"
  fi
}

# ─── Copy one file ────────────────────────────────────────────────────────────
copy_file() {
  local rel_path="$1"
  local vm_dir="$VM_PATH/$(dirname "$rel_path")"

  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY] $rel_path  →  $VM_PATH/$rel_path"
    return
  fi

  echo "  → $rel_path"
  $SSH "mkdir -p $vm_dir" 2>/dev/null
  $SCP "$LOCAL_ROOT/$rel_path" "$VM_USER@$VM_HOST:$VM_PATH/$rel_path"
}

# ─── Auto-detect changed files ────────────────────────────────────────────────
detect_files() {
  cd "$LOCAL_ROOT"

  # Get all modified (M) and untracked (??) files from git status
  # For untracked directories, expand to individual files
  git status --short | while read -r status filepath; do
    # Strip quotes from paths with spaces
    filepath="${filepath%\"}"
    filepath="${filepath#\"}"

    # If git status reports a directory (trailing /), expand to individual files
    if [[ "$filepath" == */ ]]; then
      find "$LOCAL_ROOT/$filepath" -type f | while read -r full_path; do
        echo "__ ${full_path#$LOCAL_ROOT/}"
      done
      continue
    fi

    echo "$status $filepath"
  done | while read -r status filepath; do
    # Strip quotes again (for expanded files)
    filepath="${filepath%\"}"
    filepath="${filepath#\"}"

    # ── Exclude rules ──
    # Docs and markdown
    case "$filepath" in
      docs/*|*.md|*.MD) continue ;;
    esac
    # Tests
    case "$filepath" in
      tests/*) continue ;;
    esac
    # Lua game server files (deploy to puran.hehe.si separately)
    case "$filepath" in
      deployed_lua/*|proximity/lua/*) continue ;;
    esac
    # Migrations (review + apply manually)
    case "$filepath" in
      migrations/*|tools/migrations/*|website/migrations/*) continue ;;
    esac
    # IDE, configs, build artifacts
    case "$filepath" in
      .vscode/*|.github/*|monitoring/*|scripts/*) continue ;;
    esac
    # Sensitive/local config files
    case "$filepath" in
      .env|.env.*|config.json|bot_config.json|fiveeyes_config.json) continue ;;
    esac
    # Binary, compiled, non-deployable (but allow website/assets images)
    case "$filepath" in
      website/assets/*) ;; # allow through — handled by include rules below
      *.pyc|*.log|*.db|*.sqlite|*.docx|*.zip|*.png|*.jpg) continue ;;
    esac
    # Cache dirs
    case "$filepath" in
      *__pycache__*) continue ;;
    esac
    # Proximity non-code assets that don't go to bot VM
    case "$filepath" in
      proximity/docs/*|proximity/schema/*|proximity/*.code-workspace) continue ;;
    esac
    # Root-level non-deployable files
    case "$filepath" in
      pyproject.toml|pytest.ini|*.sh|*.ps1|Makefile|LICENSE|*.yaml|*.yml) continue ;;
    esac
    # Schema file for sqlite (not used on prod)
    case "$filepath" in
      tools/schema_sqlite.sql) continue ;;
    esac

    # ── Include rules ──
    # If it passed all excludes, check it's a deployable file type/path
    case "$filepath" in
      bot/*.py|bot/**/*.py)           echo "$filepath" ;;
      analytics/*.py)                 echo "$filepath" ;;
      proximity/parser/*.py)          echo "$filepath" ;;
      proximity/*.json)               echo "$filepath" ;;
      website/backend/*.py)           echo "$filepath" ;;
      website/backend/**/*.py)        echo "$filepath" ;;
      website/index.html)             echo "$filepath" ;;
      website/js/*.js)                echo "$filepath" ;;
      website/assets/*)               echo "$filepath" ;;
      tools/schema_postgresql.sql)    echo "$filepath" ;;
      requirements*.txt)              echo "$filepath" ;;
      postgresql_database_manager.py) echo "$filepath" ;;
      bot/schema.json)                echo "$filepath" ;;
      *)
        # Catch other .py files at root level
        case "$filepath" in
          *.py) echo "$filepath" ;;
        esac
        ;;
    esac
  done | sort -u
}

# ─── Header ───────────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════╗"
echo "║    Slomix VM Deploy              ║"
echo "╠══════════════════════════════════╣"
echo "  Target  : $VM_USER@$VM_HOST:$VM_PATH"
echo "  Dry run : $DRY_RUN"
echo "╚══════════════════════════════════╝"
echo ""

# ─── Detect files ─────────────────────────────────────────────────────────────
echo "Scanning for changed files..."
DEPLOY_FILES=$(detect_files)
FILE_COUNT=$(echo "$DEPLOY_FILES" | grep -c . || true)

if [ "$FILE_COUNT" -eq 0 ]; then
  echo "  No deployable changes detected."
  exit 0
fi

echo "  Found $FILE_COUNT file(s) to deploy:"
echo ""
echo "$DEPLOY_FILES" | sed 's/^/    /'
echo ""

# ─── Confirm ──────────────────────────────────────────────────────────────────
if [ "$DRY_RUN" = false ] && [ "$AUTO_YES" = false ]; then
  read -rp "  Deploy these files? [y/N] " confirm
  if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
    echo "  Aborted."
    exit 0
  fi
fi

# ─── Step 1: Stop services ────────────────────────────────────────────────────
echo ""
echo "[ 1/5 ] Stopping services on VM..."
if [ "$DRY_RUN" = true ]; then
  echo "  [DRY] sudo systemctl stop slomix-bot slomix-web"
else
  if sudo_run systemctl stop slomix-bot slomix-web; then
    echo "  Services stopped."
  else
    echo "  [WARN] Could not stop services. Pass SUDO_PASS=<password> to enable."
    echo "         Files will still be copied safely. Restart services manually after."
  fi

  # Fix group-write permissions on directories owned by slomix_bot / slomix_web
  echo "  Fixing group-write permissions..."
  if sudo_run chmod -R g+w /opt/slomix/bot/ && \
     sudo_run chmod -R g+w /opt/slomix/website/backend/ && \
     sudo_run chmod -R g+w /opt/slomix/proximity/ && \
     sudo_run chmod -R g+w /opt/slomix/tools/ && \
     sudo_run chmod -R g+w /opt/slomix/logs/ && \
     sudo_run chmod -R g+w /opt/slomix/analytics/; then
    echo "  Permissions fixed."
  else
    echo "  [WARN] Could not fix permissions — scp may fail on some files."
  fi

  # Ensure logs/metrics dir exists for MetricsLogger
  $SSH "mkdir -p /opt/slomix/logs/metrics 2>/dev/null" || true
fi
echo ""

# ─── Step 2: Copy files ───────────────────────────────────────────────────────
echo "[ 2/5 ] Copying $FILE_COUNT file(s)..."
echo "$DEPLOY_FILES" | while read -r f; do
  copy_file "$f"
done
echo ""

# ─── Step 3: Apply DB schema ──────────────────────────────────────────────────
# Only run if schema_postgresql.sql was in the deploy list
if echo "$DEPLOY_FILES" | grep -q 'tools/schema_postgresql.sql'; then
  echo "[ 3/5 ] Applying DB schema (IF NOT EXISTS — safe/idempotent)..."

  if [ "$DRY_RUN" = true ]; then
    echo "  [DRY] psql -U etlegacy_user -d etlegacy -f $VM_PATH/tools/schema_postgresql.sql"
  else
    DB_PASS=$($SSH "grep -E '^DB_PASSWORD=|^POSTGRES_PASSWORD=' $VM_PATH/.env 2>/dev/null | head -1 | cut -d= -f2- | tr -d '\"'" || true)

    if [ -z "$DB_PASS" ]; then
      echo "  [WARN] Could not read DB password from VM .env — skipping schema step"
    else
      $SSH "PGPASSWORD='$DB_PASS' psql -h localhost -U etlegacy_user -d etlegacy \
        -f $VM_PATH/tools/schema_postgresql.sql \
        -v ON_ERROR_STOP=0 2>&1 \
        | grep -E 'CREATE TABLE|CREATE INDEX|ERROR|already exists' | head -40"
      echo "  Schema applied."
    fi
  fi
else
  echo "[ 3/5 ] Schema unchanged — skipping."
fi
echo ""

# ─── Step 4: Start services ───────────────────────────────────────────────────
echo "[ 4/5 ] Starting services on VM (web first, then bot)..."
if [ "$DRY_RUN" = true ]; then
  echo "  [DRY] sudo systemctl start slomix-web"
  echo "  [DRY] sudo systemctl start slomix-bot"
else
  NEEDS_MANUAL_RESTART=false

  if sudo_run systemctl start slomix-web; then
    echo "  slomix-web started."
    sleep 2
  else
    echo "  [WARN] Could not start slomix-web."
    NEEDS_MANUAL_RESTART=true
  fi

  if sudo_run systemctl start slomix-bot; then
    echo "  slomix-bot started."
    sleep 4
  else
    echo "  [WARN] Could not start slomix-bot."
    NEEDS_MANUAL_RESTART=true
  fi

  if [ "$NEEDS_MANUAL_RESTART" = true ]; then
    echo ""
    echo "  ┌─────────────────────────────────────────────────────────┐"
    echo "  │  Manual restart needed — run on the VM:                 │"
    echo "  │    sudo systemctl start slomix-web slomix-bot           │"
    echo "  │    sudo journalctl -u slomix-bot -f                     │"
    echo "  └─────────────────────────────────────────────────────────┘"
  else
    echo ""
    echo "  Service status:"
    WEB_STATUS=$($SSH "systemctl is-active slomix-web" || echo "failed")
    BOT_STATUS=$($SSH "systemctl is-active slomix-bot" || echo "failed")
    echo "    slomix-web : $WEB_STATUS"
    echo "    slomix-bot : $BOT_STATUS"

    if [ "$WEB_STATUS" != "active" ] || [ "$BOT_STATUS" != "active" ]; then
      echo "  [WARN] One or more services did not start cleanly — check logs below"
    fi
  fi
fi
echo ""

# ─── Step 5: Tail logs ────────────────────────────────────────────────────────
if [ "$NO_LOGS" = true ] || [ "$DRY_RUN" = true ]; then
  if [ "$DRY_RUN" = true ]; then
    echo "[ 5/5 ] [DRY] Would tail: journalctl -u slomix-bot -n 40 --no-pager"
  else
    echo "[ 5/5 ] Skipping log tail (--no-logs)"
  fi
else
  echo "[ 5/5 ] Bot startup logs (last 40 lines):"
  echo "        ─────────────────────────────────────"
  { sudo_run journalctl -u slomix-bot -n 40 --no-pager --output=short-iso 2>/dev/null || echo '  (no log access)'; } \
    | grep -v '^-- ' \
    | sed 's/^/        /'
  echo ""
  echo "        Website logs (last 20 lines):"
  echo "        ─────────────────────────────────────"
  { sudo_run journalctl -u slomix-web -n 20 --no-pager --output=short-iso 2>/dev/null || echo '  (no log access)'; } \
    | grep -v '^-- ' \
    | sed 's/^/        /'
fi

echo ""
echo "╔══════════════════════════════════╗"
echo "║    Deploy complete               ║"
echo "╚══════════════════════════════════╝"
echo ""
echo "  Live log stream (Ctrl+C to exit):"
echo "    ssh slomix-vm 'sudo journalctl -u slomix-bot -f'"
echo ""
