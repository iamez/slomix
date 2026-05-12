#!/usr/bin/env bash
# deploy_release_v1.14.2.sh — Tag-based release deploy to slomix_vm
#
# Ships the v1.14.2 audit bundle to the production VM:
#   - PR #245 (4 N+1 fixes + 7 SLF001 renames)
#   - PR #247 (noise-rule ruff ignores)
#   - PR #251 (A8 weapon_stats_mv + A5 KIS shadow, both feature-flagged)
#
# Strictly follows docs/DEPLOYMENT_RUNBOOK.md: git checkout tag, apply
# migrations, update .env flags, restart in correct order, verify.
#
# Usage:
#   SUDO_PASS=<pass> ./scripts/deploy_release_v1.14.2.sh             # full deploy
#   ./scripts/deploy_release_v1.14.2.sh --dry-run                    # show actions, no changes
#   ./scripts/deploy_release_v1.14.2.sh --skip-migrations            # skip migration apply (already done)
#   ./scripts/deploy_release_v1.14.2.sh --skip-flags                 # skip .env edit
#
# Migrations applied (manual psql per CLAUDE.md):
#   - migrations/052_composite_indexes_proximity.sql  (VM is on cdb7f51, pre-v1.14.0)
#   - migrations/053_add_weapon_stats_mv.sql
#   - migrations/054_add_storytelling_kis_shadow_audit.sql
#
# Flags added to /opt/slomix/.env (idempotent — won't duplicate):
#   USE_WEAPON_STATS_MV=true
#   WEAPON_STATS_MV_REFRESH_SECONDS=300
#   (KIS_SHADOW_MODE_ENABLED intentionally NOT enabled on prod yet)

set -euo pipefail

# ─── Config ───────────────────────────────────────────────────────────────────
VM_HOST="192.168.64.159"
VM_USER="slomix"
VM_KEY="$HOME/.ssh/slomix_vm_ed25519"
VM_PATH="/opt/slomix"
TAG="v1.14.2"
PUBLIC_URL="https://www.slomix.fyi"

DRY_RUN=false
SKIP_MIGRATIONS=false
SKIP_FLAGS=false
for arg in "$@"; do
  case "$arg" in
    --dry-run)         DRY_RUN=true ;;
    --skip-migrations) SKIP_MIGRATIONS=true ;;
    --skip-flags)      SKIP_FLAGS=true ;;
  esac
done

SSH="ssh -i $VM_KEY $VM_USER@$VM_HOST"

# ─── Helpers ──────────────────────────────────────────────────────────────────
log()   { echo -e "\033[36m[deploy]\033[0m $*"; }
warn()  { echo -e "\033[33m[warn]\033[0m  $*" >&2; }
fail()  { echo -e "\033[31m[fail]\033[0m  $*" >&2; exit 1; }

run_remote() {
  if $DRY_RUN; then
    log "[dry-run] would run: $*"
  else
    $SSH "$@"
  fi
}

sudo_run() {
  if $DRY_RUN; then
    log "[dry-run] would sudo: $*"
    return
  fi
  if [ -n "${SUDO_PASS:-}" ]; then
    $SSH "echo '$SUDO_PASS' | sudo -S $*"
  else
    $SSH "sudo -n $*" || fail "sudo failed — re-run with SUDO_PASS=<pass>"
  fi
}

# ─── Header ───────────────────────────────────────────────────────────────────
echo
echo "╔══════════════════════════════════════════════╗"
echo "║  slomix_vm release deploy — $TAG          ║"
echo "╠══════════════════════════════════════════════╣"
printf "  Target     : %s@%s:%s\n" "$VM_USER" "$VM_HOST" "$VM_PATH"
printf "  Public URL : %s\n" "$PUBLIC_URL"
printf "  Dry run    : %s\n" "$DRY_RUN"
printf "  Migrations : %s\n" "$([ "$SKIP_MIGRATIONS" = true ] && echo 'SKIP' || echo 'apply 052+053+054')"
printf "  Env flags  : %s\n" "$([ "$SKIP_FLAGS" = true ] && echo 'SKIP' || echo 'enable USE_WEAPON_STATS_MV')"
echo "╚══════════════════════════════════════════════╝"
echo

# ─── 1. Verify SSH + current state ────────────────────────────────────────────
log "1/8  Verify SSH + current VM state"
$SSH "cd $VM_PATH && git log --oneline -1 && systemctl is-active slomix-bot slomix-web" \
  || fail "SSH check failed"

CURRENT_COMMIT=$($SSH "cd $VM_PATH && git rev-parse HEAD")
log "Current commit: $CURRENT_COMMIT (rollback target)"

# ─── 2. DB backup pre-migration ───────────────────────────────────────────────
# Password is read *inside* the remote shell so it never enters our local
# transcript. Both DB_PASSWORD and POSTGRES_PASSWORD prefixes are supported,
# matching scripts/deploy_to_vm.sh. The `\$(` escape prevents local expansion;
# the remote shell evaluates the command substitution.
if ! $SKIP_MIGRATIONS; then
  log "2/8  Backup DB before migrations"
  BACKUP_NAME="pre-${TAG}-$(date +%Y%m%d-%H%M%S).sql.gz"
  run_remote "cd $VM_PATH && mkdir -p backups && \
    PGPASSWORD=\$(grep -E '^(DB|POSTGRES)_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '\"') \
    pg_dump -h localhost -U etlegacy_user -d etlegacy \
      | gzip > backups/$BACKUP_NAME && \
    ls -lh backups/$BACKUP_NAME"
fi

# ─── 3. Fetch + checkout tag ──────────────────────────────────────────────────
log "3/8  Fetch tags + verify clean tree + checkout $TAG"
# Refuse to clobber uncommitted changes — abort and let user reconcile manually.
run_remote "cd $VM_PATH && \
  if [ -n \"\$(git status --porcelain)\" ]; then \
    echo 'ERROR: VM working tree not clean. Aborting before checkout.' >&2; \
    git status --short; \
    exit 1; \
  fi"
run_remote "cd $VM_PATH && git fetch origin --tags && git checkout $TAG && git log --oneline -1"

# ─── 3b. Auto-bump JS cache-buster to current git SHA (CF edge cache purge) ───
# Why: index.html / app.js / session-detail.js reference static JS files with a
# fixed `?v=...` query. Cloudflare's edge cache keys include the query string,
# so unless the buster changes between releases, CF keeps serving the previous
# version of any updated JS file (24h max-age). We saw this exact failure on
# 2026-05-13 — session-detail.js was Apr-19 cached, user saw old UI.
#
# Rewriting these three files in place (post-checkout, pre-restart) gives every
# release a unique buster derived from the commit SHA. The files are otherwise
# byte-identical to the tagged content; we never commit the rewrite.
log "3b/8 Auto-bump cache-buster to current git SHA"
run_remote "cd $VM_PATH && \
  SHA=\$(git rev-parse --short HEAD) && \
  for f in website/index.html website/js/app.js website/js/session-detail.js; do \
    sed -i \"s|?v=[A-Za-z0-9._-]\\+|?v=\$SHA|g\" \"\$f\"; \
  done && \
  echo \"  cache-buster bumped to ?v=\$SHA\" && \
  grep -hoE '\\?v=[A-Za-z0-9._-]+' website/index.html | sort -u"

# ─── 4. Stop services (clean restart) ─────────────────────────────────────────
log "4/8  Stop services before migration"
sudo_run "systemctl stop slomix-web slomix-bot"

# ─── 5. Apply migrations ──────────────────────────────────────────────────────
if ! $SKIP_MIGRATIONS; then
  log "5/8  Apply migrations 052 + 053 + 054 (all idempotent, IF NOT EXISTS)"
  for MIG in 052_composite_indexes_proximity.sql \
             053_add_weapon_stats_mv.sql \
             054_add_storytelling_kis_shadow_audit.sql; do
    log "  -> $MIG"
    run_remote "cd $VM_PATH && \
      PGPASSWORD=\$(grep -E '^(DB|POSTGRES)_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '\"') \
      psql -h localhost -U etlegacy_user -d etlegacy -v ON_ERROR_STOP=1 -f migrations/$MIG"
  done
  log "Verify weapon_stats_mv populated + shadow audit table exists"
  run_remote "cd $VM_PATH && \
    PGPASSWORD=\$(grep -E '^(DB|POSTGRES)_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '\"') \
    psql -h localhost -U etlegacy_user -d etlegacy -c \
    'SELECT COUNT(*) AS mv_rows, MAX(last_seen_at) AS last_data FROM weapon_stats_mv;'"
  run_remote "cd $VM_PATH && \
    PGPASSWORD=\$(grep -E '^(DB|POSTGRES)_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '\"') \
    psql -h localhost -U etlegacy_user -d etlegacy -tAc \
    \"SELECT to_regclass('public.storytelling_kis_shadow_audit') IS NOT NULL\""
else
  log "5/8  Skipping migrations (--skip-migrations)"
fi

# ─── 6. Update .env flags (idempotent, sudo'd) ────────────────────────────────
# /opt/slomix/.env is owned by slomix_bot:slomix mode 640. The deploy user
# (slomix) has read but not write — every write must go through sudo.
# We learned this the hard way on 2026-05-13 (PermissionError mid-deploy).
if ! $SKIP_FLAGS; then
  log "6/8  Add feature flags to /opt/slomix/.env (via sudo)"
  for KV in "USE_WEAPON_STATS_MV=true" "WEAPON_STATS_MV_REFRESH_SECONDS=300"; do
    KEY="${KV%%=*}"
    # Replace if exists, else append — wrapped in sudo bash -c for write perms.
    # The inner single-quoted block is the literal command sudo executes.
    sudo_run "bash -c 'cd $VM_PATH && \
      if grep -qE \"^${KEY}=\" .env; then \
        sed -i \"s|^${KEY}=.*|${KV}|\" .env; \
      else \
        echo \"${KV}\" >> .env; \
      fi'"
  done
  log "Final flag state on VM:"
  run_remote "grep -E '^(USE_WEAPON_STATS_MV|WEAPON_STATS_MV_REFRESH_SECONDS)=' $VM_PATH/.env || true"
else
  log "6/8  Skipping .env edit (--skip-flags)"
fi

# ─── 7. Start services (web first, then bot per runbook) ──────────────────────
log "7/8  Start services (web → bot)"
sudo_run "systemctl daemon-reload"
sudo_run "systemctl start slomix-web"
$DRY_RUN || sleep 3
sudo_run "systemctl is-active slomix-web && journalctl -u slomix-web --since '30 seconds ago' --no-pager | grep -E 'weapon_stats_mv|ERROR|started' | head -10 || true"

sudo_run "systemctl start slomix-bot"
$DRY_RUN || sleep 5
sudo_run "systemctl is-active slomix-bot"

# ─── 8. Smoke test ────────────────────────────────────────────────────────────
log "8/8  Public smoke test"
if $DRY_RUN; then
  log "[dry-run] would curl $PUBLIC_URL/api/status and /api/stats/weapons?period=7d"
else
  echo "  /api/status:"
  curl -fsS "$PUBLIC_URL/api/status" | head -c 200; echo
  echo "  /api/stats/weapons?period=7d&limit=3:"
  curl -fsS "$PUBLIC_URL/api/stats/weapons?period=7d&limit=3" -w "  time: %{time_total}s\n" -o /tmp/weapons_smoke.json
  head -c 200 /tmp/weapons_smoke.json; echo
fi

# ─── Done ─────────────────────────────────────────────────────────────────────
echo
log "Deploy complete. To rollback to pre-deploy commit ($CURRENT_COMMIT):"
echo "  ssh $VM_USER@$VM_HOST 'cd $VM_PATH && git checkout $CURRENT_COMMIT && sudo systemctl restart slomix-web slomix-bot'"
echo "  To disable just the MV flag (cheaper rollback — keeps code, just falls back to live query):"
echo "  ssh $VM_USER@$VM_HOST 'sed -i s/^USE_WEAPON_STATS_MV=.*/USE_WEAPON_STATS_MV=false/ $VM_PATH/.env && sudo systemctl restart slomix-web'"
echo "  To DROP the materialized view if it caused issues:"
echo "    psql ... -c 'DROP MATERIALIZED VIEW IF EXISTS weapon_stats_mv;'"
echo
