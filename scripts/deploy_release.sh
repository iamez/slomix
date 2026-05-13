#!/usr/bin/env bash
# deploy_release.sh — Generic tag-based release deploy to slomix_vm
#
# Replaces the per-release scripts/deploy_release_v<TAG>.sh files. The runner
# itself is release-agnostic; per-release knobs (migrations to apply, .env
# flags to add) live in scripts/release_configs/<TAG>.sh.
#
# Usage:
#   SUDO_PASS=<pass> ./scripts/deploy_release.sh v1.14.3              # full deploy
#   ./scripts/deploy_release.sh v1.14.3 --dry-run                     # show actions, no changes
#   ./scripts/deploy_release.sh v1.14.3 --skip-migrations             # skip migration apply
#   ./scripts/deploy_release.sh v1.14.3 --skip-flags                  # skip .env edit
#
# Per-release config (REQUIRED unless --skip-migrations AND --skip-flags):
#   scripts/release_configs/<TAG>.sh must define:
#     MIGRATIONS=("052_foo.sql" "053_bar.sql")     # filenames under migrations/
#     FLAGS=("USE_X=true" "Y_REFRESH_SECONDS=300") # KV pairs appended/updated in .env
#     RELEASE_NOTES="optional human-readable summary"
#
# Strictly follows docs/DEPLOYMENT_RUNBOOK.md: git checkout tag, apply
# migrations, update .env flags, restart in correct order, verify.

set -euo pipefail

# ─── Parse args ───────────────────────────────────────────────────────────────
TAG="${1:-}"
if [ -z "$TAG" ] || [[ "$TAG" == --* ]]; then
  echo "ERROR: TAG is required as first argument." >&2
  echo "Usage: SUDO_PASS=<pass> $0 <tag> [--dry-run] [--skip-migrations] [--skip-flags]" >&2
  echo "Example: SUDO_PASS=... $0 v1.14.3" >&2
  exit 1
fi
shift

# Hard-validate TAG before any path/shell interpolation. Two attack vectors
# this closes (Copilot review on #259):
#   - Path traversal: TAG="../../../etc/passwd" would have caused us to
#     `source $SCRIPT_DIR/release_configs/$TAG.sh`, executing arbitrary
#     local shell code.
#   - Remote command injection: TAG is later interpolated into an SSH
#     command (`git checkout -f $TAG`). Shell metacharacters in TAG would
#     execute on the VM.
# Strict allow-list: vN.N.N optionally followed by a hyphenated suffix
# (e.g. v1.14.3, v1.14.3-rc1). Matches the actual git tag scheme used in
# this repo's release-please workflow.
if [[ ! "$TAG" =~ ^v[0-9]+\.[0-9]+\.[0-9]+(-[A-Za-z0-9.]+)?$ ]]; then
  echo "ERROR: TAG must match ^v[0-9]+\\.[0-9]+\\.[0-9]+(-[A-Za-z0-9.]+)?\$ — got: $TAG" >&2
  echo "(Strict validation prevents path traversal + remote command injection.)" >&2
  exit 1
fi

DRY_RUN=false
SKIP_MIGRATIONS=false
SKIP_FLAGS=false
for arg in "$@"; do
  case "$arg" in
    --dry-run)         DRY_RUN=true ;;
    --skip-migrations) SKIP_MIGRATIONS=true ;;
    --skip-flags)      SKIP_FLAGS=true ;;
    *)                 echo "WARN: unknown flag $arg (ignored)" >&2 ;;
  esac
done

# ─── Config ───────────────────────────────────────────────────────────────────
VM_HOST="192.168.64.159"
VM_USER="slomix"
VM_KEY="$HOME/.ssh/slomix_vm_ed25519"
VM_PATH="/opt/slomix"
PUBLIC_URL="https://www.slomix.fyi"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CONFIG_FILE="$SCRIPT_DIR/release_configs/${TAG}.sh"

# ─── Load per-release config ──────────────────────────────────────────────────
MIGRATIONS=()
FLAGS=()
RELEASE_NOTES=""

if [ -f "$CONFIG_FILE" ]; then
  # shellcheck disable=SC1090
  source "$CONFIG_FILE"
elif ! $SKIP_MIGRATIONS || ! $SKIP_FLAGS; then
  echo "ERROR: per-release config not found: $CONFIG_FILE" >&2
  echo "" >&2
  echo "Create it with:" >&2
  echo "  mkdir -p $SCRIPT_DIR/release_configs" >&2
  echo "  cat > $CONFIG_FILE <<'EOF'" >&2
  echo "  # Release config for $TAG" >&2
  echo "  # shellcheck shell=bash" >&2
  echo "  # shellcheck disable=SC2034" >&2
  echo "  MIGRATIONS=(" >&2
  echo "    # \"055_example.sql\"" >&2
  echo "  )" >&2
  echo "  FLAGS=(" >&2
  echo "    # \"NEW_FLAG=true\"" >&2
  echo "  )" >&2
  echo "  RELEASE_NOTES=\"...\"" >&2
  echo "  EOF" >&2
  echo "" >&2
  echo "Or re-run with --skip-migrations --skip-flags for a code-only deploy." >&2
  exit 1
fi

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
  # Password is piped over SSH stdin (not embedded in argv) so it never
  # appears in `ps`/process args on the local box. `sudo -S` reads its own
  # password from stdin, then the rest of the command (no stdin needed for
  # systemctl/grep). Also safe against passwords containing single quotes.
  if [ -n "${SUDO_PASS:-}" ]; then
    printf '%s\n' "$SUDO_PASS" | $SSH "sudo -S -- $*"
  else
    $SSH "sudo -n -- $*" || fail "sudo failed — re-run with SUDO_PASS=<pass>"
  fi
}

# ─── Header ───────────────────────────────────────────────────────────────────
MIG_DESC="SKIP"
FLAG_DESC="SKIP"
if ! $SKIP_MIGRATIONS && [ ${#MIGRATIONS[@]} -gt 0 ]; then
  MIG_DESC="apply ${#MIGRATIONS[@]} migration(s)"
fi
if ! $SKIP_FLAGS && [ ${#FLAGS[@]} -gt 0 ]; then
  FLAG_DESC="set ${#FLAGS[@]} flag(s)"
fi

echo
echo "╔══════════════════════════════════════════════╗"
echo "║  slomix_vm release deploy — $TAG"
echo "╠══════════════════════════════════════════════╣"
printf "  Target     : %s@%s:%s\n" "$VM_USER" "$VM_HOST" "$VM_PATH"
printf "  Public URL : %s\n" "$PUBLIC_URL"
printf "  Dry run    : %s\n" "$DRY_RUN"
printf "  Migrations : %s\n" "$MIG_DESC"
printf "  Env flags  : %s\n" "$FLAG_DESC"
[ -n "$RELEASE_NOTES" ] && printf "  Notes      : %s\n" "$RELEASE_NOTES"
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
if ! $SKIP_MIGRATIONS && [ ${#MIGRATIONS[@]} -gt 0 ]; then
  log "2/8  Backup DB before migrations"
  BACKUP_NAME="pre-${TAG}-$(date +%Y%m%d-%H%M%S).sql.gz"
  # set -o pipefail: pg_dump errors propagate through the `| gzip` pipeline
  # instead of silently producing an empty .sql.gz that `ls` would still
  # report as "success", letting migrations run without a real backup.
  run_remote "set -o pipefail; cd $VM_PATH && mkdir -p backups && \
    PGPASSWORD=\$(grep -E '^(DB|POSTGRES)_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '\"') \
    pg_dump -h localhost -U etlegacy_user -d etlegacy \
      | gzip > backups/$BACKUP_NAME && \
    ls -lh backups/$BACKUP_NAME && \
    [ -s backups/$BACKUP_NAME ] || { echo 'ERROR: backup file is empty — pg_dump likely failed' >&2; exit 1; }"
else
  log "2/8  Skipping DB backup (no migrations queued)"
fi

# ─── 3. Fetch + checkout tag ──────────────────────────────────────────────────
# Clean-tree guard with allow-list: step 3b leaves website/index.html,
# website/js/app.js, and website/js/session-detail.js permanently modified
# (bumped to that release's git SHA — see step 3b's rationale block below).
# We tolerate those known-bumped files here but abort on ANY OTHER dirty
# file (manual prod edits, leftover hotfix, etc.).
log "3/8  Fetch tags + verify clean tree (allow-listed bumped files) + checkout $TAG"
run_remote "cd $VM_PATH && \
  UNEXPECTED=\$(git status --porcelain | grep -vE ' website/(index\\.html|js/(app|session-detail)\\.js)\$' || true); \
  if [ -n \"\$UNEXPECTED\" ]; then \
    echo 'ERROR: Unexpected dirty files in VM working tree (not the allow-listed cache-buster files). Aborting before checkout.' >&2; \
    echo \"\$UNEXPECTED\" >&2; \
    exit 1; \
  fi"
# `git checkout -f $TAG` force-overwrites any cache-buster-bumped files left
# from the previous deploy with the tagged content. Without -f, git would
# refuse with "Your local changes would be overwritten by checkout".
# Safe because the allow-list guard above already proved nothing else is dirty.
run_remote "cd $VM_PATH && git fetch origin --tags && git checkout -f $TAG && git log --oneline -1"

# ─── 3b. Auto-bump JS cache-buster to current git SHA (CF edge cache purge) ───
# Why: index.html / app.js / session-detail.js reference static JS files with a
# fixed `?v=...` query. Cloudflare's edge cache keys include the query string,
# so unless the buster changes between releases, CF keeps serving the previous
# version of any updated JS file (24h max-age). We saw this exact failure on
# 2026-05-13 — session-detail.js was Apr-19 cached, user saw old UI.
#
# Rewriting these three files in place (post-checkout, pre-restart) gives every
# release a unique buster derived from the commit SHA. The files are otherwise
# byte-identical to the tagged content.
#
# IMPORTANT: the bump PERSISTS on disk after the deploy completes. The web
# backend serves index.html via FastAPI's FileResponse and mounts the rest as
# StaticFiles — both read from disk on every request — so the bumped `?v=SHA`
# URLs MUST stay on disk for traffic after the deploy to keep getting the new
# cache key. Step 3 above tolerates these known-dirty files; step 3's
# `git checkout -f` overwrites them on the next deploy run.
log "3b/8 Auto-bump cache-buster to current git SHA (persists after deploy)"
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
if ! $SKIP_MIGRATIONS && [ ${#MIGRATIONS[@]} -gt 0 ]; then
  log "5/8  Apply ${#MIGRATIONS[@]} migration(s) (each must be idempotent / IF NOT EXISTS)"
  for MIG in "${MIGRATIONS[@]}"; do
    log "  -> $MIG"
    run_remote "cd $VM_PATH && \
      PGPASSWORD=\$(grep -E '^(DB|POSTGRES)_PASSWORD=' .env | head -1 | cut -d= -f2- | tr -d '\"') \
      psql -h localhost -U etlegacy_user -d etlegacy -v ON_ERROR_STOP=1 -f migrations/$MIG"
  done
  # After successful psql applies, record the rows in schema_migrations so
  # the migration runner doesn't treat them as pending next time. Uses the
  # `--mark` mode (added in PR #257) which inserts without re-running SQL.
  # Falls back to a warning if apply_migrations.py is missing or errors —
  # we don't want a tracking-table glitch to fail the whole deploy.
  log "  Recording migrations in schema_migrations via apply_migrations.py --mark"
  run_remote "cd $VM_PATH && \
    if [ -f scripts/apply_migrations.py ] && [ -x venv/bin/python ]; then \
      venv/bin/python scripts/apply_migrations.py --mark ${MIGRATIONS[*]} \
        || echo 'WARN: --mark failed; reconcile manually after deploy'; \
    else \
      echo 'WARN: apply_migrations.py or venv/bin/python missing; skipping --mark'; \
    fi"
else
  log "5/8  Skipping migrations (--skip-migrations or empty MIGRATIONS=)"
fi

# ─── 6. Update .env flags (idempotent, sudo'd) ────────────────────────────────
# /opt/slomix/.env is owned by slomix_bot:slomix mode 640. The deploy user
# (slomix) has read but not write — every write must go through sudo.
# We learned this the hard way on 2026-05-13 (PermissionError mid-deploy).
if ! $SKIP_FLAGS && [ ${#FLAGS[@]} -gt 0 ]; then
  log "6/8  Add ${#FLAGS[@]} feature flag(s) to /opt/slomix/.env (via sudo)"
  for KV in "${FLAGS[@]}"; do
    KEY="${KV%%=*}"
    VAL="${KV#*=}"
    # Hard-validate KEY against the standard env-var pattern. A KEY with
    # regex metacharacters would corrupt the grep/sed below. (Copilot review
    # on #259.)
    if [[ ! "$KEY" =~ ^[A-Z_][A-Z0-9_]*$ ]]; then
      fail "Invalid flag KEY in FLAGS[]: '$KEY' (must match ^[A-Z_][A-Z0-9_]*\$)"
    fi
    # Escape VAL for sed's replacement side. Three characters are special:
    #   \   — escape character, must be doubled first
    #   |   — our delimiter, must be backslash-escaped
    #   &   — backreference to the whole match
    # We deliberately substitute order: backslash first so we don't escape
    # the backslashes we add for the other two.
    VAL_ESC="${VAL//\\/\\\\}"
    VAL_ESC="${VAL_ESC//|/\\|}"
    VAL_ESC="${VAL_ESC//&/\\&}"
    # Replace if exists, else append — wrapped in sudo bash -c for write perms.
    # The inner single-quoted block is the literal command sudo executes.
    # Bash's builtin echo (no -e) prints literally + adds newline; KEY is
    # validated so the appended line never starts with `-`.
    sudo_run "bash -c 'cd $VM_PATH && \
      if grep -qE \"^${KEY}=\" .env; then \
        sed -i \"s|^${KEY}=.*|${KEY}=${VAL_ESC}|\" .env; \
      else \
        echo \"${KEY}=${VAL}\" >> .env; \
      fi'"
  done
  log "Final flag state on VM (this release only):"
  ALL_KEYS="$(printf '%s\n' "${FLAGS[@]}" | cut -d= -f1 | paste -sd '|')"
  run_remote "grep -E '^(${ALL_KEYS})=' $VM_PATH/.env || true"
else
  log "6/8  Skipping .env edit (--skip-flags or empty FLAGS=)"
fi

# ─── 7. Start services (web first, then bot per runbook) ──────────────────────
log "7/8  Start services (web → bot)"
sudo_run "systemctl daemon-reload"
sudo_run "systemctl start slomix-web"
$DRY_RUN || sleep 3
# Split is-active (must pass) from journalctl-grep (cosmetic). Earlier
# version combined them via `&& ... || true` which let an inactive
# service slip through because `|| true` neutralized the whole chain.
sudo_run "systemctl is-active slomix-web" || fail "slomix-web failed to start — check 'journalctl -u slomix-web'"
sudo_run "bash -c \"journalctl -u slomix-web --since '30 seconds ago' --no-pager | grep -E 'ERROR|started' | head -10 || true\""

sudo_run "systemctl start slomix-bot"
$DRY_RUN || sleep 5
sudo_run "systemctl is-active slomix-bot" || fail "slomix-bot failed to start — check 'journalctl -u slomix-bot'"

# ─── 8. Smoke test ────────────────────────────────────────────────────────────
log "8/8  Public smoke test"
if $DRY_RUN; then
  log "[dry-run] would curl $PUBLIC_URL/api/status"
else
  echo "  /api/status:"
  curl -fsS "$PUBLIC_URL/api/status" | head -c 200; echo
fi

# ─── Done ─────────────────────────────────────────────────────────────────────
echo
log "Deploy complete. To rollback to pre-deploy commit ($CURRENT_COMMIT):"
# Use `git checkout -f` because step 3b leaves the cache-buster files
# permanently bumped on disk; rollback must force-overwrite them.
# Include `-i $VM_KEY` so the printed commands match the script's own SSH
# connection params — without it, the rollback fails for anyone who doesn't
# have $VM_KEY as their default identity for $VM_HOST. (Copilot review on #259.)
echo "  ssh -i $VM_KEY $VM_USER@$VM_HOST 'cd $VM_PATH && git checkout -f $CURRENT_COMMIT && sudo systemctl restart slomix-web slomix-bot'"
if [ ${#FLAGS[@]} -gt 0 ]; then
  echo "  To disable one of this release's flags (cheaper rollback — keeps code):"
  for KV in "${FLAGS[@]}"; do
    KEY="${KV%%=*}"
    echo "    ssh -i $VM_KEY $VM_USER@$VM_HOST \"sudo sed -i 's/^${KEY}=.*/${KEY}=false/' $VM_PATH/.env && sudo systemctl restart slomix-web slomix-bot\""
  done
fi
echo
