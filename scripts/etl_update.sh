#!/bin/bash
# =============================================================================
# etl_update.sh — ET:Legacy game-server updater (snapshot | stable)
#
# Runs ON the game server (puran). Codifies the proven safe in-place overlay
# procedure (verified 2026-06-20/21). Fixes the pitfalls of the old etlupdate*.sh:
#   - kills the WATCHDOG first (else it respawns the server mid-overlay)
#   - PRESERVES custom files the stock tarball clobbers (et_botnames_ext.gm)
#   - snapshot vs stable mode + version/Lua verification
#
# Usage:
#   etl_update.sh <stable|snapshot> <download-url>
#
# Get <download-url> from https://www.etlegacy.com/download — copy the
#   Linux "x86_64 archive" (.tar.gz) link:
#     stable   -> e.g. https://www.etlegacy.com/download/file/715
#     snapshot -> the x86_64 archive link from the "Snapshot builds" section
#
# Keeps the game dir NAME unchanged (~/etlegacy-v2.83.1-x86_64) so crontab,
# etdaemon.sh and vektor.cfg paths stay valid — same as past manual updates.
# =============================================================================

set -u

# ----------------------------- config ---------------------------------------
GAME_DIR="$HOME/etlegacy-v2.83.1-x86_64"          # dir name kept on purpose
LEGACY_DIR="$GAME_DIR/legacy"
WATCHDOG_PAT="etlegacy-v2.83.1-x86_64/etdaemon.sh" # pkill -f pattern (watchdog)
SCREEN_NAME="vektor"
ETCONSOLE="$HOME/.etlegacy/legacy/etconsole.log"
BACKUP_ROOT="$HOME/backups"
# Custom files the stock tarball overlays/clobbers — backed up then restored:
PRESERVE_FILES=(
  "legacy/omni-bot/et/scripts/et_botnames_ext.gm"
)

TS="$(date '+%Y%m%d-%H%M%S')"
BACKUP_DIR="$BACKUP_ROOT/pre-update-$TS"
LOG="$BACKUP_ROOT/etl_update-$TS.log"
TMP="$(mktemp -d "${TMPDIR:-/tmp}/etlupd-XXXXXX")"

# ----------------------------- helpers ---------------------------------------
log()  { echo "[$(date '+%H:%M:%S')] $*" | tee -a "$LOG"; }
ok()   { echo "  ✅ $*" | tee -a "$LOG"; }
warn() { echo "  ⚠️  $*" | tee -a "$LOG"; }

cleanup_tmp() { [ -n "${TMP:-}" ] && rm -rf "$TMP" 2>/dev/null; }
trap cleanup_tmp EXIT

abort() {  # abort BEFORE overlay — server untouched
  echo "  ❌ ABORT: $*" | tee -a "$LOG" >&2
  exit 1
}

fail_post() {  # failure AFTER overlay — print rollback
  echo "  ❌ FAILED (after overlay): $*" | tee -a "$LOG" >&2
  print_rollback
  exit 1
}

print_rollback() {
  cat <<EOF | tee -a "$LOG"

  ─── ROLLBACK (run manually if needed) ───
  pkill -f etdaemon.sh; screen -S $SCREEN_NAME -X quit
  cp "$BACKUP_DIR/etlded.x86_64" "$GAME_DIR/"
  cp "$BACKUP_DIR/qagame.mp.x86_64.so" "$LEGACY_DIR/"
  cp "$BACKUP_DIR/"legacy_v*.pk3 "$LEGACY_DIR/"
  rm -f "$LEGACY_DIR/$NEW_PK3"            # remove the freshly-applied pk3
  cd "$GAME_DIR" && nohup bash etdaemon.sh > etdaemon.log 2>&1 &
  ─────────────────────────────────────────
EOF
}

# ----------------------------- 1) validate args -----------------------------
MODE="${1:-}"; URL="${2:-}"
case "$MODE" in stable|snapshot) ;; *)
  echo "Usage: $0 <stable|snapshot> <download-url>"; exit 2;; esac
[ -n "$URL" ] || { echo "Usage: $0 <stable|snapshot> <download-url>"; exit 2; }

mkdir -p "$BACKUP_ROOT"
log "ET:Legacy updater — mode=$MODE"
log "URL: $URL"
case "$URL" in
  *.sh) warn "URL looks like a .sh installer — this script wants the x86_64 ARCHIVE (.tar.gz)";;
esac
[ -d "$GAME_DIR" ]   || abort "GAME_DIR not found: $GAME_DIR"
[ -d "$LEGACY_DIR" ] || abort "LEGACY_DIR not found: $LEGACY_DIR"

# ----------------------------- 2) preflight ----------------------------------
CUR_BIN_VER="$(strings "$GAME_DIR/etlded.x86_64" 2>/dev/null | grep -m1 -E 'ET Legacy v[0-9]+\.[0-9]')"
log "Current binary: ${CUR_BIN_VER:-unknown}"
FREE_KB="$(df -Pk "$HOME" | awk 'NR==2{print $4}')"
[ "${FREE_KB:-0}" -gt 524288 ] || abort "Low disk (<512MB free in $HOME)"
HHMM="$(date '+%H%M')"
if [ "$HHMM" -ge 1955 ] && [ "$HHMM" -le 2005 ]; then
  warn "It is ~20:00 — the daily cron kills etlded now. Consider waiting."
fi
# best-effort player check (omni-bot/human connects without disconnect in tail)
if [ -f "$ETCONSOLE" ]; then
  RECENT_CONN="$(tail -40 "$ETCONSOLE" 2>/dev/null | grep -c 'ClientBegin')"
  [ "${RECENT_CONN:-0}" -gt 0 ] && warn "Recent ClientBegin in console — make sure server is EMPTY."
fi

# ----------------------------- 3) confirm ------------------------------------
echo
echo "  About to update the game server:"
echo "    mode      : $MODE"
echo "    url       : $URL"
echo "    game dir  : $GAME_DIR  (name kept)"
echo "    backup    : $BACKUP_DIR"
echo "    preserve  : ${PRESERVE_FILES[*]}"
echo "  This will STOP the server (watchdog first), overlay the new files and RESTART."
read -r -p "  Proceed? [y/N] " ans
case "$ans" in y|Y|yes|YES) ;; *) echo "  Aborted by user."; exit 0;; esac

# ----------------------------- 4) download + validate ------------------------
DL="$TMP/etl.tar.gz"
log "Downloading…"
if command -v wget >/dev/null; then
  wget -q --show-progress -O "$DL" "$URL" || abort "download failed"
else
  curl -fL -o "$DL" "$URL" || abort "download failed"
fi
tar -tzf "$DL" >/dev/null 2>&1 || abort "downloaded file is not a valid .tar.gz"
tar -xzf "$DL" -C "$TMP" || abort "extract failed"
SRC="$(find "$TMP" -maxdepth 1 -type d -name 'etlegacy-v*' | head -1)"
[ -n "$SRC" ] || abort "extracted etlegacy-v* dir not found"
[ -f "$SRC/etlded.x86_64" ] || abort "tarball missing etlded.x86_64 (wrong/incomplete archive)"
NEW_PK3="$(cd "$SRC/legacy" 2>/dev/null && ls -1 legacy_v*.pk3 2>/dev/null | head -1)"
[ -n "$NEW_PK3" ] || abort "tarball missing legacy/legacy_v*.pk3"
ok "Archive valid — new pk3: $NEW_PK3"

# ----------------------------- 5) versions + mode check ----------------------
OLD_PK3="$(cd "$LEGACY_DIR" && ls -1 legacy_v*.pk3 2>/dev/null | head -1)"
log "Old pk3: ${OLD_PK3:-none}    New pk3: $NEW_PK3"
# snapshot pk3 has a -<n>-g<hash> suffix; stable does not
if echo "$NEW_PK3" | grep -qE 'legacy_v[0-9.]+-[0-9]+-g[0-9a-f]+\.pk3'; then
  PK3_KIND="snapshot"
else
  PK3_KIND="stable"
fi
if [ "$PK3_KIND" != "$MODE" ]; then
  abort "mode=$MODE but the archive pk3 ($NEW_PK3) looks like '$PK3_KIND'. Wrong link?"
fi
ok "pk3 kind matches mode ($MODE)"

# ----------------------------- 6) backup -------------------------------------
mkdir -p "$BACKUP_DIR"
cp "$GAME_DIR/etlded.x86_64"            "$BACKUP_DIR/" 2>/dev/null
cp "$LEGACY_DIR/qagame.mp.x86_64.so"    "$BACKUP_DIR/" 2>/dev/null
[ -n "$OLD_PK3" ] && cp "$LEGACY_DIR/$OLD_PK3" "$BACKUP_DIR/" 2>/dev/null
for rel in "${PRESERVE_FILES[@]}"; do
  if [ -f "$GAME_DIR/$rel" ]; then
    mkdir -p "$BACKUP_DIR/preserve/$(dirname "$rel")"
    cp "$GAME_DIR/$rel" "$BACKUP_DIR/preserve/$rel"
  fi
done
ok "Backed up to $BACKUP_DIR"

# ----------------------------- 7) stop (watchdog FIRST!) ---------------------
log "Stopping server (watchdog first)…"
pkill -f "$WATCHDOG_PAT" 2>/dev/null; sleep 2
screen -S "$SCREEN_NAME" -X quit 2>/dev/null; sleep 2
pkill -f 'etlded.x86_64 +exec' 2>/dev/null; sleep 2
for _ in 1 2 3 4 5; do
  pgrep -f 'etlded.x86_64|etdaemon.sh' >/dev/null || break
  sleep 2
done
if pgrep -f 'etlded.x86_64|etdaemon.sh' >/dev/null; then
  abort "could not stop server/watchdog cleanly — server still up, nothing overlaid"
fi
ok "Server + watchdog stopped"

# ----------------------------- 8) overlay ------------------------------------
log "Overlaying new files into $GAME_DIR …"
cp -rf "$SRC"/* "$GAME_DIR"/ || fail_post "overlay cp failed"

# ----------------------------- 9) remove old pk3 -----------------------------
if [ -n "$OLD_PK3" ] && [ "$OLD_PK3" != "$NEW_PK3" ]; then
  rm -f "$LEGACY_DIR/$OLD_PK3"
fi
PK3_COUNT="$(cd "$LEGACY_DIR" && ls -1 legacy_v*.pk3 2>/dev/null | wc -l)"
[ "$PK3_COUNT" -eq 1 ] || fail_post "expected exactly 1 legacy pk3, found $PK3_COUNT"
ok "Single legacy pk3: $(cd "$LEGACY_DIR" && ls -1 legacy_v*.pk3)"

# ----------------------------- 10) restore preserved files -------------------
for rel in "${PRESERVE_FILES[@]}"; do
  if [ -f "$BACKUP_DIR/preserve/$rel" ]; then
    cp "$BACKUP_DIR/preserve/$rel" "$GAME_DIR/$rel" && ok "Restored custom: $rel"
  fi
done

# ----------------------------- 11) pre-start verify --------------------------
NEW_BIN_VER="$(strings "$GAME_DIR/etlded.x86_64" | grep -m1 -E 'ET Legacy v[0-9]+\.[0-9]')"
QA_VER="$(strings "$LEGACY_DIR/qagame.mp.x86_64.so" | grep -m1 -E 'ET Legacy v[0-9]+\.[0-9]')"
log "New binary: $NEW_BIN_VER"
log "New qagame: $QA_VER"
if [ "$MODE" = "stable" ] && echo "$NEW_BIN_VER" | grep -qE '\-g[0-9a-f]+'; then
  warn "stable mode but binary version string contains a git hash"
fi

# ----------------------------- 12) restart -----------------------------------
log "Restarting via etdaemon.sh…"
( cd "$GAME_DIR" && nohup bash etdaemon.sh > etdaemon.log 2>&1 & )
sleep 15

# ----------------------------- 13) post-start verify -------------------------
if pgrep -f 'etlded.x86_64' >/dev/null && screen -ls 2>/dev/null | grep -q "$SCREEN_NAME"; then
  ok "Server process + screen up"
else
  fail_post "server did not come back up after restart"
fi
# NB: etconsole.log is TRUNCATED on each restart, so the last 5 'loaded into Lua VM'
# lines are this boot's modules (robust to truncate or append — no byte-offset diff).
LUA_LOADS="$(grep 'loaded into Lua VM' "$ETCONSOLE" 2>/dev/null | tail -5)"
LUA_N="$(printf '%s\n' "$LUA_LOADS" | grep -c 'loaded into Lua VM')"
log "Lua modules loaded this boot: $LUA_N (expect 5)"
printf '%s\n' "$LUA_LOADS" | sed -E 's/.*file .(.*). loaded.*/    \1/' | tee -a "$LOG"
# real Lua errors this boot (exclude the benign Sys_LoadDll homepath qagame miss)
LUA_ERR="$(tail -200 "$ETCONSOLE" 2>/dev/null | grep -iE 'nil value|traceback|attempt to|outputData ERROR' | grep -vc 'Sys_LoadDll')"
if [ "${LUA_N:-0}" -ge 5 ] && [ "${LUA_ERR:-1}" -eq 0 ]; then
  ok "All Lua modules loaded, no errors"
else
  warn "Lua check: modules=$LUA_N errors=$LUA_ERR — inspect $ETCONSOLE"
fi

# ----------------------------- 14) cleanup + 15) summary ---------------------
cleanup_tmp
echo
log "════════ UPDATE COMPLETE ════════"
log "  $MODE update"
log "  ${CUR_BIN_VER:-?}  →  $NEW_BIN_VER"
log "  pk3: ${OLD_PK3:-none} → $NEW_PK3"
log "  backup:  $BACKUP_DIR"
log "  log:     $LOG"
echo "  Rollback if needed:"; print_rollback
