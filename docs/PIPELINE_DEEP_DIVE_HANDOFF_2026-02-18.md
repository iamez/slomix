# Pipeline Deep-Dive Handoff (2026-02-18)

## Purpose
This document is a handoff for the next AI agent to continue investigation and stabilization of missing Lua round metadata, especially R2 gaps.

Primary problem statement:
1. Lua metadata (`STATS_READY` + `lua_round_teams`) is missing for some R2 rounds.
2. Pipeline has overlapping/duplicate signal paths in production, which can mask root causes.

## Snapshot (As Of 2026-02-18)
1. Repository has local hardening patches for bot ingestion and logging idempotency:
   - `bot/ultimate_bot.py`
   - `bot/logging_config.py`
2. Lua webhook on game server is currently `v1.6.1` and loaded from:
   - `/home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua`
3. Game server still has deprecated watcher service active:
   - `et-stats-webhook.service` is `enabled` and `active`.
4. Game server has duplicate voice monitor processes:
   - two `log_monitor.sh` processes observed via `pgrep`.

## Confirmed Findings

### 1) Missing R2 is a real upstream capture gap
For session on `2026-02-16`, rounds:
1. `9856` (`etl_adlernest` R2) -> `MISSING_LUA`
2. `9865` (`te_escape2` R2) -> `MISSING_LUA`
3. `9868` (`te_escape2` R2) -> `MISSING_LUA`
4. `9871` (`et_brewdog` R2) -> `MISSING_LUA`

Session summary:
1. Total rounds: `12`
2. Lua linked: `8`
3. Missing: `4` (all R2)

### 2) Deprecated service overlap is real in production
Host `puran` currently reports:
1. `et-stats-webhook.service` loaded, enabled, and running.
2. Process:
   - `/usr/bin/python3 /home/et/scripts/stats_webhook_notify.py`

This creates overlapping trigger behavior with Lua webhook pipeline.

### 3) Duplicate `log_monitor.sh` processes are present
Observed on game server:
1. `pgrep -af /home/et/scripts/log_monitor.sh` returned 2 running processes.

This is not directly the Lua R2 root cause, but it is an operational duplication risk and noise amplifier.

### 4) Historical DB coverage is heavily skewed toward missing Lua
Read-only DB checks:
1. `lua_round_teams` by round:
   - round `1`: `15`
   - round `2`: `4`
2. Last 30 days (`rounds` table, R1/R2 only):
   - R1: `66 total`, `52 missing Lua`
   - R2: `71 total`, `67 missing Lua`
3. Last 14 days daily snapshot:
   - `2026-02-16`: `12 total`, `4 missing`, `4 missing R2`
   - `2026-02-11`: `16 total`, `6 missing`, `6 missing R2`
   - `2026-02-06`: `11 total`, `11 missing`, `8 missing R2`
   - `2026-02-04`: `1 total`, `1 missing`, `1 missing R2`

### 5) Bot log history shows duplicate ingestion symptoms
`logs/webhook.log` contains repeated pairs of:
1. `Received STATS_READY webhook with metadata`
2. `Stored Lua round data ...`

This is consistent with duplicate trigger/message paths and/or repeated startup cycles.

## What Has Already Been Patched Locally

### A) Bot pipeline hardening
File: `bot/ultimate_bot.py`
1. Added round normalization for Lua metadata paths:
   - treat `round=0` as R2 in webhook/gametime ingestion.
2. Replaced overwrite-prone pending metadata map with queued + pruned storage.
3. `_pop_pending_metadata` now matches by filename timestamp proximity.
4. Added dedicated STATS_READY rate limiter (separate from filename trigger limiter).
5. Added webhook message-id dedupe in-process.

### B) Logging setup hardening
File: `bot/logging_config.py`
1. `setup_logging` now clears child logger handlers before re-adding them.
2. Prevents in-process handler duplication and repeated log lines when setup is called again.

### C) Documentation/runbook updates
Updated docs include corrected log paths and preflight checks:
1. `docs/TWO_WEEK_LIVE_MONITOR_MISSION_2026-02-18.md`
2. `docs/GAMESERVER_CLAUDE.md`
3. `docs/WS1_R2_MISSING_INVESTIGATION_2026-02-18.md`
4. plus additional docs with corrected `logs/*.log` references.

## Potential Fixes/Patches For Next Agent

## P0: Remove overlapping production signal paths
1. Disable deprecated watcher service:
```bash
sudo systemctl disable --now et-stats-webhook.service
systemctl is-enabled et-stats-webhook.service
systemctl is-active et-stats-webhook.service
```
2. Keep only one `log_monitor.sh` process:
```bash
pgrep -af "/home/et/scripts/log_monitor.sh"
pkill -f "/home/et/scripts/log_monitor.sh"
nohup bash /home/et/scripts/log_monitor.sh >/home/et/scripts/log_monitor.log 2>&1 &
pgrep -fc "/home/et/scripts/log_monitor.sh"
```

3. Add process lock in `/home/et/scripts/log_monitor.sh`:
```bash
exec 9>/tmp/log_monitor.lock
flock -n 9 || exit 0
```
This prevents accidental double starts.

## P1: Deploy and activate bot hardening patch
1. Ensure patched files are present on bot host:
   - `bot/ultimate_bot.py`
   - `bot/logging_config.py`
2. Compile-check:
```bash
python3 -m py_compile bot/ultimate_bot.py bot/logging_config.py
```
3. Restart bot process/service.
4. Verify runtime:
```bash
pgrep -af "/venv/bin/python3 bot/ultimate_bot.py"
tail -F logs/webhook.log | rg --line-buffered "STATS_READY|Stored Lua round data|rate limited|duplicate webhook message id"
```

## P1: Confirm Lua webhook path is the only metadata source
On game server:
```bash
grep -nE "lua_modules|stats_discord_webhook|c0rnp0rn7|endstats" /home/et/etlegacy-v2.83.1-x86_64/legacy/legacy.cfg
tail -n 200 /home/et/.etlegacy/legacy/etconsole.log | grep -nE "stats_discord_webhook|Gamestate transition|Round started|Round ended|Shutdown fallback"
```
Goal:
1. Lua module loaded once.
2. R2 round end emits webhook/fallback artifacts consistently.

## P2: Add automated missing-Lua guardrail
Create periodic check comparing `rounds` vs `lua_round_teams` for recent rounds:
1. If round exists but no Lua row within 2-5 minutes, raise alert in dev channel.
2. Include map, round id, match id, and last relevant webhook log lines.

## P2: Data repair/backfill strategy
1. Recoverable cases:
   - rounds with fallback gametime JSON artifacts available.
2. Non-recoverable cases:
   - rounds with no STATS_READY and no gametime artifact.
3. Keep explicit incident list of non-recoverable rounds for audit trail.

## Execution Plan For Next Agent
1. Apply P0 (disable old service + single log monitor).
2. Deploy/restart bot with local hardening patch (P1).
3. Run controlled live monitoring session (or next real play window).
4. Validate:
   - no duplicate STATS_READY handling,
   - no stale metadata mismatches,
   - improved R2 Lua persistence.
5. If R2 still misses:
   - capture `etconsole.log` around transition,
   - capture webhook log window,
   - append evidence to `docs/WS1_R2_MISSING_INVESTIGATION_2026-02-18.md`.

## Acceptance Criteria
1. `et-stats-webhook.service` disabled and inactive.
2. Exactly one `log_monitor.sh` process on server.
3. One bot process handling webhook ingestion.
4. For next live map sets, R2 Lua coverage improves and no unexplained duplicates in `logs/webhook.log`.
5. Any remaining misses include complete triage packet (server log + webhook log + DB diff).

## Quick Access Links
1. Baseline investigation: `docs/WS1_R2_MISSING_INVESTIGATION_2026-02-18.md`
2. Live monitor mission: `docs/TWO_WEEK_LIVE_MONITOR_MISSION_2026-02-18.md`
3. Game server runbook: `docs/GAMESERVER_CLAUDE.md`
