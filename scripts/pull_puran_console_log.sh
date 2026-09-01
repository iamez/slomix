#!/bin/bash
# Appends the game server's etconsole.log to a local day-file on the dev box.
# The server TRUNCATES that log on every restart (cron kills it daily at
# 20:00), which is how the 2026-09-01 19:30 lag episode's evidence was lost —
# this collector exists so a restart can no longer erase the record.
# Run from cron every 10 minutes as the samba user; state is a byte offset.
set -euo pipefail

DEST="${SLOMIX_CONSOLE_LOG_DIR:-$HOME/slomix-server-logs}"
# Same override names as scripts/system_status.sh, so one env reconfigures
# every game-server script at once.
GAME_SSH_HOST="${GAME_SSH_HOST:-et@puran.hehe.si}"
GAME_SSH_PORT="${GAME_SSH_PORT:-48101}"
GAME_SSH_KEY="${GAME_SSH_KEY:-$HOME/.ssh/etlegacy_bot}"
SSH_OPTS=(-p "$GAME_SSH_PORT" -i "$GAME_SSH_KEY" -o ConnectTimeout=10 -o BatchMode=yes)
HOST="$GAME_SSH_HOST"
REMOTE_LOG='~/.etlegacy/legacy/etconsole.log'
STATE="$DEST/.etconsole.offset"

mkdir -p "$DEST"
OUT="$DEST/etconsole-$(date +%F).log"

size=$(ssh "${SSH_OPTS[@]}" "$HOST" "stat -c %s $REMOTE_LOG" 2>/dev/null) || exit 0
off=$(cat "$STATE" 2>/dev/null || echo 0)

# A smaller file than our offset means the server restarted and reopened the
# log — mark the seam and start from byte zero, losing nothing.
if [ "$size" -lt "$off" ]; then
    printf '==== server restart detected %s (size %s < offset %s) ====\n' \
        "$(date -Is)" "$size" "$off" >> "$OUT"
    off=0
fi

if [ "$size" -gt "$off" ]; then
    ssh "${SSH_OPTS[@]}" "$HOST" "tail -c +$((off + 1)) $REMOTE_LOG" >> "$OUT"
    printf '%s\n' "$size" > "$STATE"
fi
