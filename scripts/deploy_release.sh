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
    *)                 echo "ERROR: unknown flag $arg" >&2; exit 1 ;;
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

# ─── Mid-deploy recovery trap ─────────────────────────────────────────────────
# If anything fails *after* services are stopped (step 4) but *before* they're
# confirmed restarted (end of step 7), the EXIT trap auto-restarts both
# services so the operator doesn't have to scramble for SSH to bring prod back.
#
# Why this trap matters: previously a migration error in step 5 or a sudo
# permission glitch in step 6 would leave slomix-web + slomix-bot stopped
# until manual intervention — possibly minutes/hours of public downtime.
# (Deferred follow-up from #253 Copilot review.)
#
# Edge cases handled:
#   - Failure before step 4 → SERVICES_STOPPED=false, trap no-ops.
#     (Services are still running on the old tag; nothing to recover.)
#   - Success path → SERVICES_RESTARTED=true at end of step 7, trap no-ops.
#   - Dry-run → trap no-ops (no real state change happened).
#   - Failure mid-step-7 (e.g. slomix-bot fails is-active) → trap fires.
#     `systemctl start` is idempotent so retrying both services is safe.
#   - Trap function inlines the SSH+sudo call instead of using `sudo_run`,
#     because `sudo_run` calls `fail` on error which would re-enter the trap.
#
# Second recovery window (Codex review on #509): steps 3/3b/3c check out the
# new tag and rewrite the on-disk frontend (cache-buster + React build) while
# the OLD services are still running (they don't stop until step 4). If the
# React build (3c) or any command in that window fails, the old backend would
# keep serving newly-rewritten frontend assets — a mixed old-backend/new-
# frontend state. So when we fail AFTER the checkout but BEFORE services stop,
# restore the previous checkout so the still-running services match their
# assets again.
CHECKOUT_CHANGED=false
SERVICES_STOPPED=false
SERVICES_RESTARTED=false

recover_on_failure() {
  local rc=$?
  if $DRY_RUN || [ "$rc" -eq 0 ]; then
    exit "$rc"
  fi

  # Window 1: failed after checkout/cache-bust/build but before services were
  # stopped. Roll the VM checkout back to the pre-deploy commit so the running
  # old backend and the on-disk frontend come from the same commit again. Also
  # restore the gitignored modern bundle: `git checkout -f` does NOT touch
  # website/static/modern (it's ignored), but step 3c swapped the new build in
  # and kept the old one as static/modern.prev — move it back so the still-old
  # services don't serve the new modern bundle (Codex #509).
  if $CHECKOUT_CHANGED && ! $SERVICES_STOPPED; then
    echo "" >&2
    warn "═════════════════════════════════════════════════════════════"
    warn "Deploy aborted (rc=$rc) after checkout but before services"
    warn "stopped. Restoring VM checkout to $CURRENT_COMMIT + previous"
    warn "modern bundle so the still-running services match their assets."
    warn "═════════════════════════════════════════════════════════════"
    local restore_rc=0
    $SSH "cd $VM_PATH && git checkout -f $CURRENT_COMMIT && \
      rm -rf website/static/modern.new; \
      if [ -d website/static/modern.prev ]; then \
        rm -rf website/static/modern && \
        mv website/static/modern.prev website/static/modern && \
        echo '  restored previous modern bundle from static/modern.prev'; \
      fi; \
      git log --oneline -1" || restore_rc=$?
    if [ "$restore_rc" -eq 0 ]; then
      warn "Checkout restored. The old services were never stopped, so no"
      warn "restart is needed. Investigate the failure (rc=$rc) before re-deploying."
    else
      warn "Checkout restore FAILED (rc=$restore_rc). Manual intervention:"
      warn "  ssh -i $VM_KEY $VM_USER@$VM_HOST 'cd $VM_PATH && git checkout -f $CURRENT_COMMIT'"
    fi
    exit "$rc"
  fi

  # Window 2: failed after services were stopped, before they were confirmed
  # restarted — auto-restart both on whatever code is currently checked out.
  if ! $SERVICES_STOPPED || $SERVICES_RESTARTED; then
    exit "$rc"
  fi
  echo "" >&2
  warn "═════════════════════════════════════════════════════════════"
  warn "Deploy aborted (rc=$rc) after services were stopped, before"
  warn "they were confirmed restarted. Auto-recovery: starting both"
  warn "services on whatever code is currently checked out on the VM."
  warn "═════════════════════════════════════════════════════════════"
  local recover_rc=0
  if [ -n "${SUDO_PASS:-}" ]; then
    printf '%s\n' "$SUDO_PASS" | $SSH "sudo -S -- systemctl start slomix-web slomix-bot" || recover_rc=$?
  else
    $SSH "sudo -n -- systemctl start slomix-web slomix-bot" || recover_rc=$?
  fi
  if [ "$recover_rc" -eq 0 ]; then
    warn "Recovery succeeded. Verify state with:"
    warn "  ssh -i $VM_KEY $VM_USER@$VM_HOST 'systemctl is-active slomix-web slomix-bot'"
    warn "Then investigate the original failure (rc=$rc) before re-deploying."
  else
    warn "Recovery FAILED (rc=$recover_rc). Manual intervention required:"
    warn "  ssh -i $VM_KEY $VM_USER@$VM_HOST"
    warn "  sudo systemctl start slomix-web slomix-bot"
    warn "  sudo journalctl -u slomix-web -u slomix-bot --since '5 minutes ago' --no-pager"
  fi
  exit "$rc"
}
trap recover_on_failure EXIT

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
# Clean-tree guard with allow-list: step 3b mutates `website/index.html`
# plus every direct child `website/js/*.js` (cache-buster `?v=$SHA` is
# injected into bare imports too — see step 3b's rationale below). Those
# files stay dirty between deploys. We tolerate them here but abort on
# ANY OTHER dirty file (manual prod edits, leftover hotfix, etc.).
log "3/8  Fetch tags + verify clean tree (allow-listed bumped files) + checkout $TAG"
# Status codes from `git status --porcelain` are 2 chars: X (staged) + Y
# (unstaged). After step 3b's sed mutation, our files are ` M` (space-M,
# unstaged modified). After a manual `git add`, they'd be `M ` or `MM`.
# Tighten the allow-list to only tolerate THOSE three states under the
# expected paths — any untracked (`??`), deleted (` D`), or renamed (`R `)
# entry, even under website/js/, must abort because `git checkout -f`
# won't reconcile those. (Copilot review on #261.)
run_remote "cd $VM_PATH && \
  UNEXPECTED=\$(git status --porcelain | grep -vE '^(M |MM| M) website/(index\\.html|js/[^/]+\\.js)\$' || true); \
  if [ -n \"\$UNEXPECTED\" ]; then \
    echo 'ERROR: Unexpected dirty files in VM working tree. Only `M`/`MM`/` M` (modified) under website/(index.html|js/*.js) are allow-listed. Aborting before checkout.' >&2; \
    echo \"\$UNEXPECTED\" >&2; \
    exit 1; \
  fi"
# `git checkout -f $TAG` force-overwrites any cache-buster-bumped files left
# from the previous deploy with the tagged content. Without -f, git would
# refuse with "Your local changes would be overwritten by checkout".
# Safe because the allow-list guard above already proved nothing else is dirty.
run_remote "cd $VM_PATH && git fetch origin --tags && git checkout -f $TAG && git log --oneline -1"
# Arm the checkout-rollback recovery window: from here until services stop
# (step 4), a failure restores $CURRENT_COMMIT so old services don't serve
# newly-rewritten frontend assets (Codex review on #509).
$DRY_RUN || CHECKOUT_CHANGED=true

# ─── 3b. Auto-bump JS cache-buster to current git SHA (CF edge cache purge) ───
# Why: every <script src="..."> in index.html and every `from './foo.js'`
# in the JS module graph is a candidate URL that Cloudflare caches by
# (URL + query-string) for 24h. Unless the URL changes between releases,
# CF keeps serving the previous deploy's bytes after the origin updates.
# We hit this on 2026-05-13 — session-detail.js was Apr-19 cached, user saw
# old UI.
#
# Two-step rewrite (run on the VM after `git checkout -f $TAG`):
#
#   (1) Bump any *existing* `?v=...` query in website/{index.html,**.js}
#       to `?v=$SHA`. Catches files that already had a buster.
#
#   (2) Inject `?v=$SHA` into any *local* import / src reference that
#       doesn't already have a query string. Covers the long tail of
#       legacy imports like `from './auth.js'` that we'd otherwise have
#       to remember to manually add a buster to. Patterns matched:
#         JS:   from '\./<path>.js'              from "./<path>.js"
#               import '\./<path>.js'            import "./<path>.js"
#               (side-effect import, no `from` clause — e.g.
#                `import './compare.js';` in app.js — Copilot #261.)
#         HTML: src="js/<path>.js"               src='js/<path>.js'
#       Stops at the first `?` or quote, so files that already have a
#       query are left alone (handled by step 1 instead).
#
# IMPORTANT: the rewrite PERSISTS on disk after the deploy completes. The
# web backend serves index.html via FastAPI's FileResponse and mounts the
# rest as StaticFiles — both read from disk on every request — so the
# bumped `?v=$SHA` URLs MUST stay on disk for traffic after the deploy to
# keep getting the new cache key. Step 3 above tolerates these known-dirty
# files via an allow-list; step 3's `git checkout -f` overwrites them on
# the next deploy run.
log "3b/8 Auto-bump cache-buster to current git SHA (persists after deploy)"
run_remote "cd $VM_PATH && \
  SHA=\$(git rev-parse --short HEAD) && \
  echo \"  step 1: bump existing ?v= queries (index.html + all js/*.js)\" && \
  sed -i \"s|?v=[A-Za-z0-9._-]\\+|?v=\$SHA|g\" website/index.html website/js/*.js && \
  echo \"  step 2: inject ?v=\$SHA into bare local imports/refs\" && \
  sed -i -E \"s|(from '\\./[^'?]+\\.js)'|\\1?v=\$SHA'|g; s|(from \\\"\\./[^\\\"?]+\\.js)\\\"|\\1?v=\$SHA\\\"|g; s|(import '\\./[^'?]+\\.js)'|\\1?v=\$SHA'|g; s|(import \\\"\\./[^\\\"?]+\\.js)\\\"|\\1?v=\$SHA\\\"|g\" website/js/*.js website/index.html && \
  sed -i -E \"s|(src=\\\"js/[^\\\"?]+\\.js)\\\"|\\1?v=\$SHA\\\"|g; s|(src='js/[^'?]+\\.js)'|\\1?v=\$SHA'|g\" website/index.html && \
  echo \"  unique busters now in index.html:\" && \
  grep -hoE '\\?v=[A-Za-z0-9._-]+' website/index.html | sort -u"

# ─── 3c. Build the React (modern) frontend + atomic verify + SHA cache-bust ────
# The 4 MODERN routes (proximity-player/replay/teams, skill-rating) load
# /static/modern/route-host.js, which is gitignored and produced ONLY by the
# Vite build (website/frontend). Nothing built it on deploy before, so a fresh
# checkout served "Modern Route Offline". Build it here into a STAGING dir, verify
# the entry exists and is non-empty, then swap atomically (keep the previous build
# on any failure so a broken/missing build never replaces a working one). Finally
# set modern-route-host.js's BUILD_VERSION const to $SHA so the modern entry gets
# the same cache-buster the legacy assets got in 3b (the 3b `?v=` sed can't match
# its `?v=${BUILD_VERSION}` template). Non-fatal: a build failure logs and keeps
# the previous build. A failed or missing build is FATAL (audit remediation
# plan U1): four live routes depend on it, and this step runs BEFORE services
# stop, so aborting here causes no downtime.
log "3c/8 Build modern (React) frontend + atomic verify + SHA cache-bust"
run_remote "cd $VM_PATH && \
  SHA=\$(git rev-parse --short HEAD) && \
  if ! command -v npm >/dev/null 2>&1; then \
    echo 'ERROR: npm not found on VM — cannot build the 4 live React routes' >&2; \
    exit 1; \
  fi && \
  echo '  building website/frontend (vite) → static/modern.new' && \
  ( cd website/frontend && npm ci --no-audit --no-fund && npm run build -- --outDir ../static/modern.new --emptyOutDir ) && \
  if [ -s website/static/modern.new/route-host.js ]; then \
    echo '  build OK — atomic swap into static/modern' && \
    rm -rf website/static/modern.prev && \
    { [ -d website/static/modern ] && mv website/static/modern website/static/modern.prev || true; } && \
    mv website/static/modern.new website/static/modern && \
    sed -i \"s|const BUILD_VERSION = '[^']*'|const BUILD_VERSION = '\$SHA'|\" website/js/modern-route-host.js && \
    echo \"  modern BUILD_VERSION set to \$SHA\"; \
  else \
    echo 'ERROR: build produced no route-host.js — keeping previous static/modern and aborting' >&2 && \
    rm -rf website/static/modern.new; \
    exit 1; \
  fi"

# ─── 4. Stop services (clean restart) ─────────────────────────────────────────
log "4/8  Stop services before migration"
sudo_run "systemctl stop slomix-web slomix-bot"
# Arm the recovery trap. Any non-zero exit from here until the end of
# step 7 will trigger an auto-restart of both services.
SERVICES_STOPPED=true

# ─── 5. Apply migrations via the runner ───────────────────────────────────────
# The runner (scripts/apply_migrations.py) applies each migration and its
# schema_migrations ledger row in the SAME transaction and exits non-zero on
# any failure. The previous raw `psql -f` + best-effort `--mark` path silently
# skipped ledger recording when its interpreter was missing — that is exactly
# how production drifted for migrations 052-060 (audit AUD-002). The
# interpreter is pinned to the production web venv; a missing interpreter,
# an apply failure, or post-apply ledger drift each abort the deploy.
VM_PY="venv-web/bin/python"
if ! $SKIP_MIGRATIONS && [ ${#MIGRATIONS[@]} -gt 0 ]; then
  log "5/8  Apply ${#MIGRATIONS[@]} migration(s) via apply_migrations.py (transactional + ledger)"
  run_remote "cd $VM_PATH && \
    if [ ! -x $VM_PY ]; then \
      echo \"ERROR: $VM_PY missing on VM — refusing to run migrations without the ledger runner\" >&2; \
      exit 1; \
    fi"
  run_remote "cd $VM_PATH && $VM_PY scripts/apply_migrations.py --only ${MIGRATIONS[*]}"
  log "  Validating migration ledger (pending/failed/checksum drift aborts deploy)"
  run_remote "cd $VM_PATH && $VM_PY scripts/apply_migrations.py --validate"
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
# Disarm the recovery trap — both services are confirmed up.
SERVICES_RESTARTED=true

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
