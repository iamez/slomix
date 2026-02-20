# System Log Audit Findings (2026-02-18 to 2026-02-19 Rollover)

Status: Completed  
Date created: 2026-02-19 (CET)  
Requested mission: "check all today's logs from bot, database, website, game server; verify everything and report findings"

## Objective

Produce an evidence-based, cross-system log audit covering:

1. Bot/application logs
2. Website logs
3. Database log signals + live DB state
4. Game-server logs and generated artifacts on `puran.hehe.si`

## Audit Window and Timezone Normalization

This audit crossed midnight in CET. To avoid false conclusions, we normalized by timezone:

1. Local app host clock during audit: `2026-02-19 00:14:02 CET (+0100)`
2. Game server clock: `2026-02-19T00:19:10+01:00`
3. PostgreSQL clock: `2026-02-18 23:17:43+00` (`Etc/UTC`)

Interpretation:

1. `2026-02-18` is the active "today" window in DB UTC terms.
2. `2026-02-19 00:xx CET` was also checked for immediate post-midnight regressions.

## Scope and Sources

### Local bot and app logs

1. `logs/bot.log`
2. `logs/errors.log`
3. `logs/game.log`
4. `logs/webhook.log`
5. `logs/smart_sync.log`
6. `logs/database.log`
7. `bot/logs/bot.log`
8. `bot/logs/ultimate_bot.log`
9. `bot/logs/server_control_access.log`

### Website logs

1. `website/logs/access.log`
2. `website/logs/app.log`
3. `website/logs/error.log`
4. `website/logs/debug.log`
5. `website/logs/security.log`

### Database verification

1. Live PostgreSQL checks against configured production DB (`192.168.64.116`, `etlegacy_user`)
2. Live PostgreSQL checks against website DB role (`localhost`, `website_app`)
3. File-based DB logs: `logs/database.log`, `postgresql_manager.log`, `database_manager.log`

### Game server verification (SSH)

1. `puran.hehe.si` (`ssh -p 48101 -i ~/.ssh/etlegacy_bot et@puran.hehe.si`)
2. Artifact directories:
   - `/home/et/.etlegacy/legacy/gamestats`
   - `/home/et/.etlegacy/legacy/gametimes`
   - `/home/et/.etlegacy/legacy/proximity`
3. Logs:
   - `/home/et/.etlegacy/legacy/etconsole.log`
   - `/home/et/.etlegacy/legacy/legacy3.log`
   - `/home/et/.etlegacy/legacy/sv_protect.log`
   - `/home/et/scripts/webhook_notify.log`
   - `/home/et/start_servers.log`

## Executive Summary

Overall state: `pass-with-known-gaps`

1. Core ingestion pipeline is actively writing rounds and related telemetry; no evidence of end-of-night ingestion stall.
2. Website has a real schema mismatch in Greatshot crossref path (`skill_rating` missing) producing logged errors.
3. Bot had transient DNS resolution failures and repeated restarts during the day, then stabilized later in the night.
4. Endstats duplicate-key errors occurred but latest rounds recovered and published successfully.
5. Post-midnight (`2026-02-19 00:xx CET`) window is clean: no new app/website critical errors.

## Volume Snapshot

### 2026-02-18 (local logs)

1. `logs/bot.log`: `total=7043`, `err=48`, `warn=267`
2. `logs/errors.log`: `total=275`, `err=28`, `warn=247`
3. `logs/webhook.log`: `total=791`, `err=2`, `warn=31`
4. `logs/database.log`: `total=374`, `err=0`, `warn=102`
5. `website/logs/access.log`: `total=18285`, `http5xx=0`
6. `website/logs/app.log`: `total=18285`, `err=2`
7. `website/logs/error.log`: `total=2`, `err=2`

### 2026-02-19 (early CET rollover)

1. `logs/bot.log`: `total=16`, `err=0`, `warn=0`
2. `website/logs/access.log`: `total=829`, `http5xx=0`
3. `website/logs/app.log`: `total=829`, `err=0`
4. `website/logs/error.log`: `total=0`
5. `logs/database.log`: `total=0`

## Severity-Ranked Findings

## F-001 (High) - Greatshot crossref schema mismatch in website path

Impact:

1. Greatshot cross-reference enrichment fails on some requests.
2. API path still returns HTTP 200, so failure is partially masked in client behavior.

Evidence:

1. `website/logs/error.log:4579` (`Cross-reference enrichment failed for round_id=9763`)
2. `website/logs/error.log:4599` (`Cross-reference enrichment failed for round_id=9809`)
3. `website/logs/error.log:4598` (`asyncpg.exceptions.UndefinedColumnError: column "skill_rating" does not exist`)
4. `website/logs/error.log:4618` (same `skill_rating` missing)
5. `website/logs/access.log:186536` (error logged)
6. `website/logs/access.log:186556` (`/crossref` returned `200`)
7. Live DB schema query confirms no `skill_rating` column in public schema (both `etlegacy_user` and `website_app` contexts).

Conclusion:

1. This is a real contract drift between website query expectations and current DB schema.
2. Because errors are logged but status is 200, this can silently degrade feature quality.

## F-002 (Medium) - Bot DNS outage window for game-host resolution

Impact:

1. SSH-based scans/downloads temporarily failed.
2. Can delay ingestion of proximity or other remote-dependent artifacts.

Evidence:

1. `logs/bot.log:93570` (`SSH list files failed: Temporary failure in name resolution`)
2. `logs/bot.log:93849` (`DNS resolution failed for puran.hehe.si`)
3. Pattern count for `Temporary failure in name resolution`: `36` lines on `2026-02-18`.
4. Recovery evidence later in day: repeated successful Paramiko connections/authentication in `logs/bot.log` near `23:xx` and `00:xx`.

Conclusion:

1. Outage was transient; system recovered.
2. Fallback/DNS hardening is still needed to reduce recurrence.

## F-003 (Medium) - Repeated bot restarts during day

Impact:

1. Elevated operational risk (race windows, session-state discontinuity, noisier logs).
2. Can amplify retry turbulence in webhook/round-linker paths.

Evidence:

1. `logs/bot.log` contains `15` startup events (`ET:LEGACY DISCORD BOT - STARTING UP`) on `2026-02-18`.
2. Example startup lines: `logs/bot.log:97442`, `logs/bot.log:97506`, `logs/bot.log:99375`.
3. Around restart periods, recurring test DB timeout noise appears:
   - `logs/bot.log:97460`
   - `logs/bot.log:98686`
   - message: `Failed to connect to PostgreSQL at localhost:5432/etlegacy_test: TimeoutError`

Conclusion:

1. Service was still functioning later, but restart frequency is above normal.
2. Root cause and restart policy behavior should be tightened.

## F-004 (Medium-Low) - Endstats duplicate-key errors observed, but latest rounds recovered

Impact:

1. Error noise and confusion in logs.
2. Potential duplicate-processing pressure, but no confirmed data loss for latest rounds.

Evidence:

1. Duplicate key errors:
   - `logs/webhook.log:3663`
   - `logs/webhook.log:3736`
   - constraint: `uq_processed_endstats_round_id`
2. Recovery/publish for latest frostbite rounds:
   - `logs/webhook.log:4117` (`round-1 ... published`)
   - `logs/webhook.log:4154` (`round-2 ... published`)
3. DB verification:
   - latest rounds: `9897`, `9898`, `9899` present with expected timestamps
   - `round_awards` rows: `9897=25`, `9898=26`
   - `round_vs_stats` rows: `9897=18`, `9898=18`
4. `processed_endstats_files` failed rows for today are supersede markers, not hard failures:
   - superseded richer payload rows (e.g. id `152`, id `140`).

Conclusion:

1. Behavior is mostly idempotent/recoverable.
2. Log level and dedupe path should be hardened to avoid false-red operational alerts.

## F-005 (Low) - High warning volume (round linker and time validation), ingestion still healthy

Impact:

1. Warning fatigue obscures true incidents.
2. Potential quality drift in computed metrics if not monitored.

Evidence:

1. `Round linker unresolved` pattern count: `52`
2. `[TIME VALIDATION]` mismatch pattern count: `122`
3. `logs/database.log` still shows successful imports at end of session (`23:50:11`).
4. `rounds` table status for DB current date (`UTC 2026-02-18`):
   - `completed=24`
   - `cancelled=3`

Conclusion:

1. Pipeline worked, but warning reduction and calibration should be planned.

## F-006 (Low) - Game server appears healthy for latest cycle

Impact:

1. No immediate outage signal from game-server log generation.

Evidence:

1. Remote artifact freshness:
   - `gamestats` latest: `2026-02-18 23:50:05 ... round-2.txt`
   - `gametimes` latest: `2026-02-18 23:50:02 ... R2 ... json`
   - `proximity` latest: `2026-02-18 23:50:02 ... engagements.txt`
2. `webhook_notify.log` on `2026-02-18`: `total=173`, `err=0`, `warn=1` (small-file warning).
3. `start_servers.log` shows expected daily restart event at `20:00`.
4. `sv_protect.log` shows rate-limit/drop behavior (expected hardening behavior).

Observation to track:

1. `etconsole.log` recent window includes repeated `qagame.mp.x86_64.so ... failed` fallback messages around shutdown/init transitions.
2. Count in recent sample window (`last 4000 lines`): `8`.
3. No immediate crash correlation found in this audit, but keep monitored.

## Database State Verification (Live)

Context:

1. DB time: `2026-02-18 23:17:43+00` (`Etc/UTC`)
2. Current DB date at query time: `2026-02-18`

Key checks:

1. `rounds`: `1724` total, latest `2026-02-18 23:50:11.5787`, today rows `27`
2. `round_awards`: `3700` total, latest `2026-02-18 22:50:14.44718`, today rows `384`
3. `round_vs_stats`: `2787` total, latest `2026-02-18 22:50:14.44718`, today rows `251`
4. `lua_round_teams`: latest `2026-02-18 22:50:35.660601+00`, today rows `14`
5. `lua_spawn_stats`: latest `2026-02-18 22:50:35.674803+00`, today rows `84`
6. `proximity_support_summary`: latest `2026-02-18 22:54:29.677958`, today rows `18`
7. `daily_polls`: empty (`0` rows)
8. `processed_files`: latest `2026-02-18 23:53:34.449361`, failures `0`
9. `processed_endstats_files`: latest `2026-02-18 22:50:14.78809`, today rows `15`, failure rows are superseded duplicates

## What Is Confirmed Healthy Right Now

1. New rounds are still being ingested and persisted.
2. Endstats for latest frostbite rounds were published and persisted with expected row counts.
3. No website 5xx burst in the current (`2026-02-19 00:xx CET`) window.
4. Game server continues to produce stats/gametime/proximity files up to latest completed round.

## Open Risks

1. Greatshot crossref query/schema drift remains unresolved (High).
2. Bot restart churn source remains unresolved (Medium).
3. DNS fallback hardening is not yet implemented (Medium).
4. Warning noise remains high, reducing signal clarity for true incidents (Low).

## Next Document

Execution-ready remediation checklist:

1. `docs/SYSTEM_LOG_AUDIT_DELEGATION_CHECKLIST_2026-02-18.md`

