# Webhook Triage Checklist (STATS_READY)
Date: 2026-02-11  
Scope: Read-only verification, no code changes.

## Goal
Confirm the full pipeline is working for a real round:
1. Lua detects round start/end.
2. Lua sends STATS_READY to Discord.
3. Bot accepts STATS_READY and stores `lua_round_teams`.
4. Optional fallback writes/ingests gametime JSON.

## Pipeline Topology Note
There are multiple live ingestion legs and they are complementary:
1. `stats_webhook_notify.py` filename trigger leg ("new stats file exists").
2. `stats_discord_webhook.lua` STATS_READY metadata leg (timing/team/winner metadata).
3. Proximity file importer leg (`*_engagements.txt` via `ProximityCog`).
4. Gametime JSON fallback leg (when Discord metadata leg fails).

Passing this checklist proves STATS_READY health only.  
It does not prove full universal correlation unless the same round is traceable across at least filename + STATS_READY.

## Current Known State (Before Test)
- `lua_round_teams` latest row is old (`2026-01-24`), count is `1`.
- `lua_spawn_stats` count is `0`.
- `gametimes` directory exists on server but is empty.
- Script loads (`v1.6.0`) but recent logs do not show round-end webhook send lines.

## Executed Result (2026-02-11 Live Session, Logged 2026-02-12)
Outcome: **partial pass / storage fail**

What passed:
1. Server logs show round-end Lua events and webhook send attempts.
2. Bot logs show repeated accepted STATS_READY events for real rounds.
3. Webhook payload fields (winner, score, surrender context) are present in bot logs.

What failed:
1. Lua team/timing persistence failed for each STATS_READY:
   - `Could not store Lua team data: the server expects 24 arguments for this query, 3 were passed`
2. `lua_round_teams` stayed at `1` row (stale).
3. `NO LUA DATA` remained expected for timing consumers reading `lua_round_teams`.

Important nuance:
1. This is **not** a Lua send failure.
2. It is a bot-side DB insert parameter packing failure in `_store_lua_round_teams`.
3. `lua_spawn_stats` ingest is active (fresh rows on `2026-02-11`), so webhook intake path is alive.

## Pre-Round Checks (2 minutes)
1. Confirm bot trigger config:
```bash
grep -nE '^WEBHOOK_TRIGGER_CHANNEL_ID=|^WEBHOOK_TRIGGER_USERNAME=|^WEBHOOK_TRIGGER_WHITELIST=' .env
```
Expected:
- channel: `1424620499975274496`
- username: `ET:Legacy Stats`
- whitelist includes webhook id from Lua URL.

2. Confirm live webhook target details from server:
```bash
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
'url=$(grep -m1 "discord_webhook_url =" /home/et/etlegacy-v2.83.1-x86_64/legacy/luascripts/stats_discord_webhook.lua | sed -E "s/.*\"(https:[^\"]+)\".*/\1/"); curl -s "$url"'
```
Expected JSON:
- `"channel_id":"1424620499975274496"`
- webhook id appears in bot whitelist.

## During One Real Round (5-10 minutes)
1. Watch server Lua logs:
```bash
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
"grep -nE '\[stats_discord_webhook\]|Round started|Round ended|Sending webhook|Sent round notification|Webhook send failed|Gametime file written' /home/et/.etlegacy/legacy/etconsole.log | tail -n 120"
```
Expected sequence:
- `Round started ...`
- `Round ended ...`
- `Sending webhook ...`
- `Sent round notification ...`
- optionally `Gametime file written ...`

2. Check fallback file output:
```bash
ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si \
"ls -lt /home/et/.etlegacy/legacy/gametimes | head"
```
Expected: new `gametime-*.json` file after round.

## Bot-Side Acceptance Checks (1-2 minutes)
1. Webhook logs:
```bash
rg -n "STATS_READY|Username mismatch|Unauthorized webhook|missing embeds|rate limited|Stored Lua round data|Error processing STATS_READY" logs/webhook.log logs/bot.log | tail -n 120
```
Expected:
- `Received STATS_READY webhook with metadata`
- `Stored Lua round data ...`
- no username/whitelist mismatch warnings.

2. DB confirmation:
```bash
/bin/bash -lc "PGPASSWORD='REDACTED_DB_PASSWORD' psql -h 192.168.64.116 -p 5432 -U etlegacy_user -d etlegacy -F $'\t' -Atc \"SELECT (SELECT COUNT(*) FROM lua_round_teams),(SELECT COUNT(*) FROM lua_spawn_stats);\""
```
Expected:
- `lua_round_teams` increments.
- `lua_spawn_stats` increments if spawn payload/fallback is present.

3. Correlation evidence (universal contract):
- Capture one shared round identity tuple for the same round:
  - `map_name`
  - `round_number`
  - `round_end_unix` (if present)
  - `round_date + round_time` (filename side)
- Confirm filename-triggered import and STATS_READY metadata can be traced to the same round in logs/DB.

## Failure Matrix
1. Lua loads but no `Round ended` lines:
- Detection logic not firing in live gamestate transitions.

2. `Round ended` appears but no bot STATS_READY logs:
- Discord send failed or webhook payload rejected.
- Remember: Lua currently backgrounds curl and suppresses response body; "started" does not prove HTTP 2xx.

2b. STATS_READY appears but store fails with argument-count mismatch:
- Bot accepted metadata, but `_store_lua_round_teams` query parameter packing is broken.
- Treat this as **store-stage failure**, not Discord/Lua failure.

3. Bot logs `Username mismatch` or `Unauthorized webhook`:
- Webhook metadata and bot strict security checks are misaligned (username/whitelist).

4. No Discord success, but gametime file appears:
- Discord leg failed; fallback leg may still recover data if bot ingests gametimes.

5. Discord message exists but bot says `missing embeds`:
- Payload contract drift (content/embeds format).

## Exit Criteria
Mark webhook pipeline healthy only when all are true in one live round:
1. Server shows round end + webhook send logs.
2. Bot logs STATS_READY accepted.
3. `lua_round_teams` row count increases.
4. Timing embed no longer shows `NO LUA DATA` for that round.
5. Round correlation evidence exists between filename trigger and STATS_READY metadata for that same round.

Current gate status (as of 2026-02-12):
- Steps `1` and `2`: **pass**
- Steps `3` and `4`: **fail**
- Step `5`: **partial** (metadata correlation visible in logs, but no stored Lua team row)
