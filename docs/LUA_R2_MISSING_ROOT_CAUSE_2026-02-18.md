# Lua R2 Missing Root Cause (2026-02-18)

Status: Investigated  
Scope: Fresh live incidents on `2026-02-18` where Round 2 posted stats but timing embed showed `NO LUA DATA`.

## Executive Summary
`NO LUA DATA` for fresh R2 rounds is caused by a server-side Lua runtime crash in `stats_discord_webhook.lua` while building the `STATS_READY` payload.

This is not a DB join bug and not a bot rejection bug.

Crash signature:
- `bad argument #9 to 'format' (number has no integer representation)`
- location: `stats_discord_webhook.lua:830` (`string.format` payload construction)

The crash occurs when stopwatch sets a fractional timelimit (for R2), but payload formatting uses `%d` integer placeholders.

## Confirmed Impacted Rounds (2026-02-18)
1. `etl_adlernest` R2 (`round_id=9874`) - Lua missing
2. `supply` R2 (`round_id=9877`) - Lua missing

Both have:
1. stats file processed and posted
2. no `STATS_READY` Lua metadata for R2
3. no `lua_round_teams` / `lua_spawn_stats` row for R2

## Evidence

### 1) Bot log timeline shows R1 success and R2 Lua metadata absence

`logs/webhook.log`:
1. R1 has `STATS_READY` accepted and stored:
   - `logs/webhook.log:3388`
   - `logs/webhook.log:3390`
   - `logs/webhook.log:3393`
2. R1 gametime fallback file is detected and ingested:
   - `logs/webhook.log:3415`
   - `logs/webhook.log:3416`
   - `logs/webhook.log:3420`
   - `logs/webhook.log:3421`
3. R2 only has stats/endstats trigger path, no `STATS_READY`:
   - `logs/webhook.log:3430`
   - `logs/webhook.log:3436`
   - `logs/webhook.log:3441`
4. Same pattern repeats for supply:
   - R1 `STATS_READY`: `logs/webhook.log:3454` to `logs/webhook.log:3459`
   - R2 only file trigger: `logs/webhook.log:3500` to `logs/webhook.log:3504`

Interpretation: bot is not rejecting R2 Lua webhooks; Lua webhook message was never emitted for these R2 rounds.

### 2) DB confirms R1 has Lua rows, R2 does not

Query output (`rounds` joined to `lua_round_teams` + `lua_spawn_stats`):

`etl_adlernest` (`2026-02-18`):
- `9873 ... round_number=1 ... lua_id=61 lua_duration=441 spawn_rows=6`
- `9874 ... round_number=2 ... lua_id=NULL lua_duration=NULL spawn_rows=0`

`supply` (`2026-02-18`):
- `9876 ... round_number=1 ... lua_id=63 lua_duration=543 spawn_rows=6`
- `9877 ... round_number=2 ... lua_id=NULL lua_duration=NULL spawn_rows=0`

Interpretation: missing Lua rows are real upstream misses, not consumer join misses.

### 3) Game server logs show exact Lua crash on R2 end

Server file: `/home/et/.etlegacy/legacy/etconsole.log`

`etl_adlernest` R2:
1. round end captured:
   - `/home/et/.etlegacy/legacy/etconsole.log:2467`
2. immediate crash:
   - `/home/et/.etlegacy/legacy/etconsole.log:2476`
   - `... stats_discord_webhook.lua:830: bad argument #9 to 'format' (number has no integer representation)`
3. next frame retries round-end branch and skips send:
   - `/home/et/.etlegacy/legacy/etconsole.log:2485`
   - `Webhook send already in progress, skipping`

`supply` R2:
1. same crash signature:
   - `/home/et/.etlegacy/legacy/etconsole.log:5100`
2. same follow-up skip:
   - `/home/et/.etlegacy/legacy/etconsole.log:5109`

Interpretation: crash happens in payload construction before webhook send/gametime write; then `send_in_progress` remains true, blocking retry in the same round.

### 4) Stopwatch R2 timelimit is fractional in server logs

`etl_adlernest` R2 map init:
- `/home/et/.etlegacy/legacy/etconsole.log:1856`
- `Server: timelimit changed to 7.374583`

`supply` R2 map init:
- `/home/et/.etlegacy/legacy/etconsole.log:4335`
- `Server: timelimit changed to 9.058750`

R2 stats file header examples (stopwatch):
- `local_stats/2026-02-18-215113-etl_adlernest-round-2.txt:1` shows `...\\7:22\\4:35`
- `local_stats/2026-02-18-221029-supply-round-2.txt:1` shows `...\\9:03\\9:03`

Interpretation: fractional timelimit is normal in stopwatch R2 and must be handled without `%d`-strict formatting.

### 5) Code path matches failure signature

`vps_scripts/stats_discord_webhook.lua`:
1. timelimit source can be non-integer:
   - `vps_scripts/stats_discord_webhook.lua:677`
   - `return tonumber(et.trap_Cvar_Get("timelimit")) or 0`
2. payload uses `%d` for `Lua_Timelimit` and neighboring numeric fields:
   - `vps_scripts/stats_discord_webhook.lua:830`
   - `vps_scripts/stats_discord_webhook.lua:843`
   - `vps_scripts/stats_discord_webhook.lua:844`
3. `send_in_progress=true` is set before formatting:
   - `vps_scripts/stats_discord_webhook.lua:782`
4. reset to `false` only at normal function end:
   - `vps_scripts/stats_discord_webhook.lua:931`
5. round-end caller sets emitted flags only after `send_webhook()` returns:
   - `vps_scripts/stats_discord_webhook.lua:1147`
   - `vps_scripts/stats_discord_webhook.lua:1154`
   - `vps_scripts/stats_discord_webhook.lua:1155`

Interpretation:
1. format error aborts `send_webhook()` before line `931`
2. `send_in_progress` stays true
3. second pass logs `Webhook send already in progress, skipping`
4. no webhook + no gametime file for that R2

## Why argument `#9` points to timelimit

`string.format(fmt, ...)` counts `fmt` as argument #1.  
So error `bad argument #9` maps to the 8th payload value after `fmt`.

In payload arg order (`vps_scripts/stats_discord_webhook.lua:863` to `vps_scripts/stats_discord_webhook.lua:866`):
1. mapname
2. round
3. mapname
4. round
5. winner
6. defender
7. actual_duration
8. `time_limit`  <- corresponds to function argument #9

This matches fractional `timelimit` from server (`7.374583`, `9.058750`).

## Root Cause

Primary:
1. `stats_discord_webhook.lua` uses `%d` integer formatting for timelimit in payload.
2. Stopwatch R2 sets fractional timelimit.
3. Lua `string.format` throws and aborts webhook send path.

Secondary reliability issue:
1. `send_in_progress` is not guaranteed to reset on exception.
2. The same round’s fallback re-entry then self-skips (`Webhook send already in progress, skipping`).

## Fix Plan (for next session)

### A) Format-safety fix (required)
1. Replace strict `%d` usage for timelimit with safe integer conversion or string formatting.
2. Recommended normalization:
   - keep raw timelimit as float for logic (`get_end_reason`)
   - derive `timelimit_minutes_display = math.floor(time_limit + 0.5)` (or `math.floor(time_limit)`) for embed field
   - ensure all `%d` args are explicit integers (`math.floor(...)` / cast helper)
3. Consider `%s` for display-only fields where integer strictness is not required.

### B) Exception-safety fix (required)
1. Wrap payload build/send block in `pcall` (or equivalent guard).
2. Ensure `send_in_progress=false` in all exit paths (success and failure).
3. On payload build failure:
   - log structured error with map/round/timelimit
   - still attempt gametime fallback write with sanitized metadata where possible.

### C) Guardrail logging (recommended)
1. Add a single line before payload format:
   - `timelimit raw=<value> type=<type>`
2. Add explicit log when skipping due to `send_in_progress` with map/round/signature.

### D) Verification checklist (post-fix)
1. Play a live stopwatch R1/R2 pair on map(s) that produce fractional R2 timelimit.
2. Confirm no Lua runtime format errors in `etconsole.log`.
3. Confirm `STATS_READY` for both R1 and R2 in `logs/webhook.log`.
4. Confirm `gametime-<map>-R2-*.json` exists for fresh round.
5. Confirm DB linkage for both rounds (`lua_round_teams` + `lua_spawn_stats`).
6. Confirm timing embed no longer reports `NO LUA DATA` for R2.

## Commands Used (Session Evidence)

```bash
# 1) Bot-side timeline (R1 success, R2 missing STATS_READY)
nl -ba logs/webhook.log | sed -n '3384,3452p'
nl -ba logs/webhook.log | tail -n 260

# 2) Bot warnings around unresolved round linkage
nl -ba logs/errors.log | sed -n '120236,120258p'

# 3) R2 headers showing stopwatch values
nl -ba local_stats/2026-02-18-215113-etl_adlernest-round-2.txt | sed -n '1,12p'
nl -ba local_stats/2026-02-18-221029-supply-round-2.txt | sed -n '1,6p'

# 4) Server-side Lua crash evidence
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "nl -ba /home/et/.etlegacy/legacy/etconsole.log | sed -n '2448,2505p'"
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "nl -ba /home/et/.etlegacy/legacy/etconsole.log | sed -n '5078,5122p'"
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
  "grep -n 'timelimit' /home/et/.etlegacy/legacy/etconsole.log | tail -n 120"

# 5) DB linkage check (R1 present, R2 missing)
PGPASSWORD='***' psql -h 192.168.64.116 -p 5432 -U etlegacy_user -d etlegacy \
  -F $'\t' -Atc "
SELECT r.id, r.round_date::text, r.round_time::text, r.map_name, r.round_number,
       r.actual_time, r.time_limit,
       COALESCE(l.id::text,'NULL') AS lua_id,
       COALESCE(l.actual_duration_seconds::text,'NULL') AS lua_duration,
       COALESCE(ls.cnt::text,'0') AS spawn_rows
FROM rounds r
LEFT JOIN lua_round_teams l ON l.round_id = r.id
LEFT JOIN (SELECT round_id, COUNT(*) AS cnt FROM lua_spawn_stats GROUP BY round_id) ls
  ON ls.round_id = r.id
WHERE r.round_date='2026-02-18' AND r.map_name='etl_adlernest' AND r.round_number IN (1,2)
ORDER BY r.round_number;
"
```

## Notes

This finding supersedes the earlier broad “R2 transition race” hypothesis for these fresh incidents:  
for the `2026-02-18` failures, the direct trigger is deterministic payload formatting failure on fractional timelimit values.
