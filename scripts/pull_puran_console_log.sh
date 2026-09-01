#!/bin/bash
# Appends the game server's etconsole.log to a local day-file on the dev box.
# The server TRUNCATES that log on every restart (cron kills it daily at
# 20:00), which is how the 2026-09-01 19:30 lag episode's evidence was lost —
# this collector exists so a restart can no longer erase the record.
# Run from cron every 10 minutes as the samba user; state is a byte offset.
set -euo pipefail

DEST="${SLOMIX_CONSOLE_LOG_DIR:-$HOME/slomix-server-logs}"
SSH_OPTS=(-p 48101 -i "$HOME/.ssh/etlegacy_bot" -o ConnectTimeout=10 -o BatchMode=yes)
HOST="et@puran.hehe.si"
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
