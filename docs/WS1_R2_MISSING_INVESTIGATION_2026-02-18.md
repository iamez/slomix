# WS1 R2 Missing Investigation (2026-02-18)

Status: Investigated  
Scope: Re-analysis of the live session on `2026-02-16` where timing output reported frequent `NO LUA DATA` on R2.

## Executive Finding
The missing data is a real upstream capture gap for specific R2 rounds, not a DB join-only issue.

Confirmed missing Lua-linked rounds:
1. `9856` (`etl_adlernest` R2)
2. `9865` (`te_escape2` R2)
3. `9868` (`te_escape2` R2, second map pair)
4. `9871` (`et_brewdog` R2)

Session summary:
1. Rounds observed: `12`
2. Rounds with Lua linkage: `8`
3. Rounds missing Lua linkage: `4` (all R2)

## Evidence

### 1) DB Coverage Snapshot
Direct round-to-Lua join for `round_id` `9855..9871` shows no `lua_round_teams` row for `9856/9865/9868/9871`, while R2 rows for `9859` and `9862` do exist.

Additional check for the four missing rounds confirms both tables are empty for those IDs:
1. `lua_round_teams`: false
2. `lua_spawn_stats`: false

Interpretation: fallback ingestion did not recover these rounds either.

### 2) Bot/Webhook Log Correlation
For each missing round, `logs/webhook.log` shows filename-trigger processing of `...-round-2.txt`, for example:
1. `2026-02-16-212429-etl_adlernest-round-2.txt`
2. `2026-02-16-222606-te_escape2-round-2.txt`
3. `2026-02-16-224736-te_escape2-round-2.txt`
4. `2026-02-16-225928-et_brewdog-round-2.txt`

But there are no matching `STATS_READY: <map> R2` entries and no `Stored Lua round data` lines for those same R2 events.

Interpretation: stats-file trigger leg worked, Lua metadata leg did not fire for these rounds.

### 3) Game Server Fallback Artifact Check
Server directory `/home/et/.etlegacy/legacy/gametimes` contains:
1. `gametime-etl_adlernest-R1-...json`
2. `gametime-te_escape2-R1-...json` (multiple)
3. `gametime-et_brewdog-R1-...json`

It does not contain corresponding `R2` gametime files for those missing map/round events.

Interpretation: missing rounds were not rescued by gametime JSON fallback because fallback artifacts were not produced for those rounds.

## Conclusion
The `NO LUA DATA` pattern on `2026-02-16` is primarily a server-side Lua capture gap affecting specific R2 map transitions.  
Observed behavior matches the known hypothesis of an R2 map-transition race (Lua intermission handling path skipped/deduped before webhook+gametime write), while stats-file trigger ingestion still proceeds.

## Additional System Findings (2026-02-18)
During deeper re-check of the live pipeline:

1. Deprecated watcher service still active on game server:
   - `et-stats-webhook.service` is `enabled` + `active` and running `stats_webhook_notify.py`.
   - This is an overlapping trigger source and should be disabled for clean Lua-only webhook flow.
2. Duplicate voice monitor processes observed:
   - `pgrep -af /home/et/scripts/log_monitor.sh` returned two processes.
   - Runbook should enforce exactly one active process before live sessions.
3. Bot-side hardening needed and implemented locally:
   - Metadata queueing changed from overwrite-by-key to queued+pruned matching.
   - Round normalization handles Lua `round=0` as R2 in webhook/gametime paths.
   - Separate `STATS_READY` burst limit and webhook message-id dedupe added.

Detailed handoff with patch plan for next agent:
`docs/PIPELINE_DEEP_DIVE_HANDOFF_2026-02-18.md`

## Repro/Validation Commands

```bash
# A) Round coverage vs Lua linkage (summary)
PGPASSWORD="$POSTGRES_PASSWORD" bash scripts/check_ws1_ws1c_gates.sh

# B) Round-by-round join for the target session window
PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DATABASE" -F $'\t' -Atc "
SELECT r.id AS round_id, r.map_name, r.round_number, l.id AS lua_id, l.round_number AS lua_round_number
FROM rounds r
LEFT JOIN lua_round_teams l ON l.round_id = r.id
WHERE r.round_date = '2026-02-16' AND r.id BETWEEN 9855 AND 9871
ORDER BY r.id;
"

# C) Confirm lua_round_teams + lua_spawn_stats are both missing for the 4 failing rounds
PGPASSWORD="$POSTGRES_PASSWORD" psql -h "$POSTGRES_HOST" -p "${POSTGRES_PORT:-5432}" -U "$POSTGRES_USER" -d "$POSTGRES_DATABASE" -F $'\t' -Atc "
SELECT r.id,
       EXISTS (SELECT 1 FROM lua_round_teams l WHERE l.round_id = r.id) AS has_lua_round_row,
       EXISTS (SELECT 1 FROM lua_spawn_stats s WHERE s.round_id = r.id) AS has_spawn_row
FROM rounds r
WHERE r.id IN (9856,9865,9868,9871)
ORDER BY r.id;
"

# D) Show file-trigger evidence for missing rounds in webhook logs
rg -n \"(2026-02-16-212429-etl_adlernest-round-2|2026-02-16-222606-te_escape2-round-2|2026-02-16-224736-te_escape2-round-2|2026-02-16-225928-et_brewdog-round-2|STATS_READY|Stored Lua round data)\" logs/webhook.log

# E) Check game server gametime fallback artifacts
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \"ls -lt /home/et/.etlegacy/legacy/gametimes | head -60\"
```
