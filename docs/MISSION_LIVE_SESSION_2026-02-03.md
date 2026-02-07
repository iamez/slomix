# Live Session Mission Notes - 2026-02-03

## Mission Goal
Verify the live pipeline end‑to‑end during the next session:
- Session start detection
- Live round posting
- Live endstats posting
- Live achievements posting
- Timing webhook accuracy

## Live Preconditions
- Voice threshold = 3 (SESSION_START_THRESHOLD=3).
- Bot restarted with latest code.
- Webhook timing (STATS_READY) operational.

## What We Watch In Logs
### Session Start
- `🎮 GAMING SESSION STARTED!`
- `🔄 Monitoring enabled`

### Round Import + Live Posting
- `📥 NEW FILE DETECTED: <filename>`
- `⚙️ Processing file: <filename>`
- `📊 Posting to Discord`
- `✅ Successfully processed and posted: <filename>`

### Lua Timing Webhook
- `📥 Received STATS_READY webhook with metadata`
- `📊 STATS_READY: <map> R<round> (winner=..., playtime=...)`
- `📥 Selected closest file: <filename> (Δ <sec>s)`

### Endstats
- `🏆 Processing endstats file`
- `✅ Stored <n> awards`
- `✅ Endstats embed posted`

### Achievements
- `🏆 Achievement notification sent: <player>`

## Discord Channels to Observe
- Production channel: live round + endstats embeds
- Dev channel: timing debug (if enabled)

## Quick Troubleshooting
- If live round posts are missing:
  - Check for `⚠️ No round_id for <file>, skipping post`
  - Confirm recent patch to resolve round_id after Postgres import
- If endstats missing:
  - Check if endstats file exists in `local_stats`
  - Check `processed_endstats_files` for the filename

## Restart Steps (If Crash)
1. Restart service: `systemctl restart etlegacy-bot`
2. Tail logs: `journalctl -u etlegacy-bot -f`
3. Verify bot login and cog load messages
4. Confirm `endstats_monitor` is running

## Notes / Status
- VS stats removed from endstats pagination.
- Live achievements now posted after each round import.
- Endstats dedupe uses `processed_endstats_files`.
