# Live Pipeline Audit - 2026-02-18

## Active instructions and contract source
1. No repository `AGENTS.md` overrides were found under project directories for this task.
2. Source-of-truth contract docs used:
   - `docs/TWO_WEEK_CLOSEOUT_PLAN_2026-02-11.md`
   - `docs/WEBHOOK_TRIAGE_CHECKLIST_2026-02-11.md`
   - `docs/COMPLETE_SYSTEM_RUNDOWN.md`
   - `docs/ACHIEVEMENT_SYSTEM.md`

## Current pipeline map
1. Lua webhook posts `STATS_READY` metadata.
2. Bot stores Lua payload in `lua_round_teams`/`lua_spawn_stats` and queues metadata.
3. Stats file is fetched/imported into `rounds`, `player_comprehensive_stats`, `weapon_comprehensive_stats`.
4. Round summary is published.
5. Endstats file is fetched (polling or webhook), parsed, linked to authoritative `round_id`.
6. Readiness gate validates:
   - round exists
   - `round_status` is `completed`, `cancelled`, `substitution`, or `NULL`
   - player stats rows exist for that `round_id`
7. Endstats rows (`round_awards`, `round_vs_stats`) are stored and endstats embed is published.
8. Live achievements are checked per player; persistent ledger blocks reposts across restarts.

## Live evidence snapshot (2026-02-18 UTC)
1. Recent rows show mixed R1/R2 plus duplicate `round_number=0` rows for the same match timestamp (`rounds.id=9878/9877`, `9875/9874`).
2. `lua_round_teams` has only R1 rows for current `etl_adlernest`/`supply` runs (no R2 Lua rows in the same window), which explains `NO LUA DATA` for R2 timing comparisons.
3. `processed_endstats_files` currently has duplicate rows for multiple `round_id`s in production data (historical drift before this patch).
4. `round_linker` warnings match date-filter drift (`date_filter_excluded_rows`) when rows exist by map+round but not exact `round_date`.

## Doc->code drift found
1. `docs/COMPLETE_SYSTEM_RUNDOWN.md` describes strict 30-second monitor cadence and old scheduled-start behavior, while `bot/ultimate_bot.py` has adaptive cadence/dead-hour gating and deprecates scheduled-start flow.
2. Docs imply webhook/live flow is strictly linear; code shows dual ingestion legs (webhook + SSH polling) with race protection, retries, and fallback metadata queues.

## Industry patterns mapped to Slomix
1. At-least-once + duplicates/out-of-order:
   - Applied in `bot/ultimate_bot.py` via webhook message-id dedupe, filename dedupe, and endstats retry loop.
2. Idempotency keys for side effects:
   - Endstats side effect key is `round_id` with unique-success index on `processed_endstats_files`.
   - Achievement side effect key is `achievement_id` in `achievement_notification_ledger`.
3. Idempotent consumer / processed ledger:
   - `processed_files`, `processed_endstats_files`, and `achievement_notification_ledger`.
4. Transactional outbox concept (adapted minimal subset):
   - Endstats claim + DB persistence wrapped in one DB transaction before publish path in `bot/ultimate_bot.py`.
5. Readiness gates + state transitions:
   - `_is_endstats_round_ready` verifies authoritative round status and player rows before publish/retry.
6. Retry/backoff + poison cap:
   - Existing exponential backoff (`_schedule_endstats_retry`) with max attempts; new publish-failure path leaves `success=FALSE` so retries can recover without repost spam.

## Live audit checklist commands and queries
1. Pipeline stage report:
```bash
python3 tools/pipeline_health_report.py --limit 20
```
2. Round-level endstats dedupe check (must return zero rows):
```sql
SELECT round_id, COUNT(*)
FROM processed_endstats_files
WHERE round_id IS NOT NULL
GROUP BY round_id
HAVING COUNT(*) > 1;
```
3. Endstats readiness sanity for recent rounds:
```sql
SELECT
  r.id AS round_id,
  r.round_status,
  COUNT(p.id) AS player_stats_rows,
  MAX(pef.processed_at) AS endstats_processed_at
FROM rounds r
LEFT JOIN player_comprehensive_stats p ON p.round_id = r.id
LEFT JOIN processed_endstats_files pef ON pef.round_id = r.id AND pef.success = TRUE
GROUP BY r.id, r.round_status
ORDER BY r.id DESC
LIMIT 20;
```
4. Achievement dedupe ledger visibility:
```sql
SELECT achievement_type, COUNT(*) AS claims
FROM achievement_notification_ledger
GROUP BY achievement_type
ORDER BY achievement_type;
```
5. Confirm idempotency index presence:
```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE tablename = 'processed_endstats_files'
  AND indexname = 'uq_processed_endstats_round_id';
```

## vNext state machine
1. `RECEIVED` -> filename accepted and parsed.
2. `ROUND_LINKED` -> `round_id` resolved from authoritative linker.
3. `READY_CHECK`:
   - pass -> continue
   - fail webhook path -> schedule retry/backoff
   - fail polling path -> skip, next cycle retries
4. `CLAIMED` -> transactional insert into `processed_endstats_files` (`ON CONFLICT DO NOTHING`).
5. `DB_PERSISTED` -> `round_awards` and `round_vs_stats` inserted.
6. `PUBLISHED` -> endstats embed sent once.
7. `DUPLICATE_ROUND_SKIP` -> already claimed/processed for same `round_id`.

## Implemented changes
1. Endstats now gates publish on round readiness (`round` existence, allowed status, non-zero player rows).
2. Endstats publish path is idempotent per `round_id`, not just filename.
3. Endstats webhook retry path now retries on not-ready rounds (existing backoff unchanged).
4. Endstats polling path now defers not-ready rounds to the next polling cycle.
5. Structured endstats transition logging added with `source`, `state`, `filename`, `round_id`.
6. Achievement dedupe now persists to `achievement_notification_ledger` with atomic claim (`ON CONFLICT DO NOTHING`).
7. New health script added to print stage completeness and freshness for latest rounds.
8. Schema updated for:
   - `achievement_notification_ledger`
   - `uq_processed_endstats_round_id` unique round-level idempotency index
9. Server Lua webhook hardening (`vps_scripts/stats_discord_webhook.lua`):
   - `Lua_Timelimit` embed field changed to string-safe formatting (`%s`) so fractional stopwatch R2 timelimits do not crash payload formatting.
   - `send_webhook` payload/send block wrapped with `pcall`; `send_in_progress` is now reset even on exceptions to prevent stuck `Webhook send already in progress` loops.
   - Added timelimit guard logging (`Timelimit raw/type/display`) for live diagnosis.

## Verification steps
1. Run syntax checks:
```bash
python3 -m py_compile bot/ultimate_bot.py bot/core/achievement_system.py postgresql_database_manager.py tools/pipeline_health_report.py
```
2. Apply migrations/startup schema path in a non-production environment.
3. Trigger duplicate endstats filenames for same round and verify only one publish occurs.
4. Trigger webhook endstats before main stats import and verify retry/backoff until ready.
5. Restart bot and verify previously claimed achievements do not repost.
