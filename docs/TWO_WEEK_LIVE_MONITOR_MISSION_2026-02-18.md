# Two-Week Live Monitor Mission (2026-02-18 to 2026-03-03)

## Mission Objective
Run live monitoring every day for 14 days to keep the round pipeline reliable end-to-end (game server -> STATS_READY webhook -> bot -> DB -> fallback gametimes).

Success targets:
- R1 and R2 are both observed live for active maps.
- `STATS_READY` is logged and `lua_round_teams` persists for each round.
- Any missing R2 `STATS_READY` is detected within 2 minutes and escalated by matrix below.

Baseline that triggered this mission (session on 2026-02-16):
- `12` rounds observed
- `8/12` with Lua data
- Missing R2 rounds: `9856`, `9865`, `9868`, `9871`
- Investigation doc: `docs/WS1_R2_MISSING_INVESTIGATION_2026-02-18.md`
- Deep-dive handoff + patch plan: `docs/PIPELINE_DEEP_DIVE_HANDOFF_2026-02-18.md`

## Exact 14-Day Schedule (UTC)
Daily window for every date: `18:45-19:00` preflight, `19:00-23:00` live monitoring, `23:00-23:20` closeout.

| Date | Day | Focus | Required Outcome |
|---|---|---|---|
| 2026-02-18 | Wed | Kickoff baseline | Start watchers, capture baseline counts/log health |
| 2026-02-19 | Thu | R1/R2 continuity | Verify at least 1 full R1+R2 pair with Lua persisted |
| 2026-02-20 | Fri | High-traffic stability | No untriaged webhook errors during peak session |
| 2026-02-21 | Sat | Weekend load check | Confirm DB ingest under sustained live play |
| 2026-02-22 | Sun | Fallback readiness | Confirm gametimes fallback path is observable |
| 2026-02-23 | Mon | Week-2 handoff prep | Record unresolved issues + owner per issue |
| 2026-02-24 | Tue | R2-miss drill | Run escalation flow once if R2 miss occurs |
| 2026-02-25 | Wed | Midpoint audit | Compare Day 1 vs midpoint counts and error rate |
| 2026-02-26 | Thu | Server-log correlation | Match server round-end lines to webhook lines |
| 2026-02-27 | Fri | Duplicate/latency watch | Check delayed or duplicate STATS_READY handling |
| 2026-02-28 | Sat | Weekend regression guard | Ensure no regression in R2 persistence |
| 2026-03-01 | Sun | Fallback + DB linkage | Validate fallback and DB linkage for same map |
| 2026-03-02 | Mon | Final hardening day | Resolve or escalate all open R2 misses |
| 2026-03-03 | Tue | Mission closeout | Final summary: pass/fail per target + open escalations |

## Preflight Checks (18:45-19:00 UTC)
Run these before starting watchers:

Host fallback: if DNS for `puran.hehe.si` fails, use `91.185.207.163` in the same SSH commands.

1. Confirm deprecated watcher service is not running:
```bash
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si 'if command -v systemctl >/dev/null 2>&1; then echo "enabled=$(systemctl is-enabled et-stats-webhook.service 2>/dev/null || true)"; echo "active=$(systemctl is-active et-stats-webhook.service 2>/dev/null || true)"; else echo "systemctl unavailable"; fi'
```
Expected: `enabled=disabled` and `active=inactive` (or `systemctl unavailable` on non-systemd host).

2. Confirm exactly one `log_monitor.sh` process exists:
```bash
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si "pgrep -af '/home/et/scripts/log_monitor.sh'; echo count=\$(pgrep -fc '/home/et/scripts/log_monitor.sh')"
```
Expected: `count=1`.

3. Confirm exactly one local bot process is active:
```bash
pgrep -af "/venv/bin/python3 bot/ultimate_bot.py"
pgrep -fc "/venv/bin/python3 bot/ultimate_bot.py"  # expect: 1
```

## Live-Session Checklist (Each Round)

### Before Round
1. Load DB env once in your shell:
```bash
set -a; source .env; set +a
export PGHOST="${POSTGRES_HOST:-$DB_HOST}" PGPORT="${POSTGRES_PORT:-$DB_PORT}" PGDATABASE="${POSTGRES_DATABASE:-$DB_NAME}" PGUSER="${POSTGRES_USER:-$DB_USER}" PGPASSWORD="${POSTGRES_PASSWORD:-$DB_PASSWORD}"
```
2. Start monitors (commands below) in separate terminals.
3. Capture baseline DB snapshot:
```bash
psql -v ON_ERROR_STOP=1 -F $'\t' -Atc "SELECT now(), (SELECT COUNT(*) FROM lua_round_teams), (SELECT COUNT(*) FROM lua_spawn_stats);"
```

### During Round
1. Confirm game-server events appear: round start/end and webhook send attempt.
2. Confirm `logs/webhook.log` shows `STATS_READY` accepted.
3. Confirm `Stored Lua round data` appears for that round.

### After Round
1. Check newest Lua rows:
```bash
psql -F $'\t' -Atc "SELECT captured_at, map_name, round_number, winner_team, match_id FROM lua_round_teams ORDER BY captured_at DESC LIMIT 10;"
```
2. Check round coverage and missing R2 quickly:
```bash
psql -F $'\t' -Atc "SELECT r.id, r.round_date, r.round_time, r.map_name, r.round_number, CASE WHEN EXISTS (SELECT 1 FROM lua_round_teams l WHERE l.round_id = r.id OR (l.match_id = r.match_id AND l.round_number = r.round_number)) THEN 'HAS_LUA' ELSE 'MISSING_LUA' END AS lua_status FROM rounds r WHERE r.round_date >= '2026-02-18' AND r.round_number IN (0,2) ORDER BY r.id DESC LIMIT 20;"
```
3. If any `MISSING_LUA` for R2 (`0` or `2`), apply escalation matrix immediately.

## Log-Watch Matrix (Exact Commands)

| Stream | File / Path | Exact Command |
|---|---|---|
| Bot runtime | `logs/bot.log` | `tail -F logs/bot.log` |
| DB writes/imports | `logs/database.log` | `tail -F logs/database.log` |
| App errors | `logs/errors.log` | `tail -F logs/errors.log` |
| Webhook ingest/persist | `logs/webhook.log` | `tail -F logs/webhook.log` |
| Remote server console (Lua/webhook flow) | `/home/et/.etlegacy/legacy/etconsole.log` | `ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si "tail -F /home/et/.etlegacy/legacy/etconsole.log"` |

Focused filters (optional):
```bash
tail -F logs/webhook.log | rg --line-buffered "STATS_READY|Stored Lua round data|Could not store Lua team data|Error processing STATS_READY|Gametime|No matching file found"
```
```bash
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si "tail -F /home/et/.etlegacy/legacy/etconsole.log" | rg --line-buffered "\[stats_discord_webhook\]|Round started|Round ended|Sending webhook|Sent round notification|Webhook send failed|Gametime file written"
```

## Additional Watch Commands

### DB Checks (continuous)
```bash
while true; do date -u; psql -F $'\t' -Atc "SELECT now(), (SELECT COUNT(*) FROM lua_round_teams), (SELECT COUNT(*) FROM lua_spawn_stats);"; sleep 30; done
```

### Game Server Gametimes Directory (fallback files)
```bash
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si "while true; do date -u; ls -lt /home/et/.etlegacy/legacy/gametimes | head -n 12; sleep 15; done"
```

### Local Gametimes Directory (downloaded fallback)
```bash
while true; do date -u; ls -lt local_gametimes | head -n 12; sleep 15; done
```

## Escalation Matrix: Missing R2 `STATS_READY`

R2 may appear as `round_number=0` or `round_number=2` in DB checks.

| Trigger | Time From R2 End | Action | Exact Command | Escalate To |
|---|---|---|---|---|
| No `STATS_READY` for R2 in webhook log | T+2 min | Confirm absence and check webhook errors | `rg -n "STATS_READY: .* R2|Error processing STATS_READY|Could not store Lua team data" logs/webhook.log | tail -n 80` | Live monitor on-call |
| No fallback gametime file for same R2 | T+5 min | Check server fallback write path | `ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si "ls -lt /home/et/.etlegacy/legacy/gametimes | head -n 20"` | Game-server on-call |
| R2 stats round exists but `MISSING_LUA` in DB | T+10 min | Verify DB gap and mark incident | `psql -F $'\t' -Atc "SELECT r.id, r.match_id, r.map_name, r.round_number FROM rounds r WHERE r.round_date >= '2026-02-18' AND r.round_number IN (0,2) AND NOT EXISTS (SELECT 1 FROM lua_round_teams l WHERE l.round_id = r.id OR (l.match_id = r.match_id AND l.round_number = r.round_number)) ORDER BY r.id DESC LIMIT 20;"` | Bot/DB on-call |
| Two consecutive R2 misses or any miss unresolved >30 min | T+30 min | Declare P1 incident; keep monitor active; request immediate server-side Lua investigation for map-transition race | Use all three checks above and attach outputs to incident thread | Incident lead + Lua owner |
