-- migrations/035_add_guid_canonical_columns.sql
-- Canonical short-form (first 8 chars) of player GUIDs across proximity + storytelling tables.
--
-- CONTEXT:
--   These columns were added ad-hoc on the dev/prod DB during Mar-Apr 2026 (ET Rating v1
--   + storytelling work) but never committed to migrations/ or tools/schema_postgresql.sql,
--   causing a schema drift discovered during Mega Audit v3 (Faza A, 2026-04-17).
--
--   Verified 2026-04-19 on dev DB: 6 columns populated 100% (no NULLs), 6 indexes present.
--
-- This migration is IDEMPOTENT:
--   - CREATE COLUMN IF NOT EXISTS  (won't duplicate)
--   - CREATE INDEX IF NOT EXISTS   (won't duplicate)
--   - Backfill WHERE NULL          (won't overwrite existing values)
--
-- Canonical form = substring(guid FROM 1 FOR 8). Computed by application code
-- (bot/core/guid_utils.py::short_guid) and also backfilled here for rows that
-- pre-date the code path.

BEGIN;

-- 1. player_teamplay_stats.player_guid_canonical
ALTER TABLE player_teamplay_stats
    ADD COLUMN IF NOT EXISTS player_guid_canonical VARCHAR(32);
UPDATE player_teamplay_stats
    SET player_guid_canonical = substring(player_guid FROM 1 FOR 8)
    WHERE player_guid_canonical IS NULL AND player_guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_pts_player_canonical
    ON player_teamplay_stats(player_guid_canonical);

-- 2. proximity_combat_position.attacker_guid_canonical
ALTER TABLE proximity_combat_position
    ADD COLUMN IF NOT EXISTS attacker_guid_canonical VARCHAR(32);
UPDATE proximity_combat_position
    SET attacker_guid_canonical = substring(attacker_guid FROM 1 FOR 8)
    WHERE attacker_guid_canonical IS NULL AND attacker_guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cp_attacker_canonical
    ON proximity_combat_position(attacker_guid_canonical);

-- 3. proximity_kill_outcome.killer_guid_canonical
ALTER TABLE proximity_kill_outcome
    ADD COLUMN IF NOT EXISTS killer_guid_canonical VARCHAR(32);
UPDATE proximity_kill_outcome
    SET killer_guid_canonical = substring(killer_guid FROM 1 FOR 8)
    WHERE killer_guid_canonical IS NULL AND killer_guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ko_killer_canonical
    ON proximity_kill_outcome(killer_guid_canonical);

-- 4. proximity_lua_trade_kill.trader_guid_canonical
ALTER TABLE proximity_lua_trade_kill
    ADD COLUMN IF NOT EXISTS trader_guid_canonical VARCHAR(32);
UPDATE proximity_lua_trade_kill
    SET trader_guid_canonical = substring(trader_guid FROM 1 FOR 8)
    WHERE trader_guid_canonical IS NULL AND trader_guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_tk_trader_canonical
    ON proximity_lua_trade_kill(trader_guid_canonical);

-- 5. proximity_spawn_timing.killer_guid_canonical
ALTER TABLE proximity_spawn_timing
    ADD COLUMN IF NOT EXISTS killer_guid_canonical VARCHAR(32);
UPDATE proximity_spawn_timing
    SET killer_guid_canonical = substring(killer_guid FROM 1 FOR 8)
    WHERE killer_guid_canonical IS NULL AND killer_guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_st_killer_canonical
    ON proximity_spawn_timing(killer_guid_canonical);

-- 6. storytelling_kill_impact.killer_guid_canonical
ALTER TABLE storytelling_kill_impact
    ADD COLUMN IF NOT EXISTS killer_guid_canonical VARCHAR(32);
UPDATE storytelling_kill_impact
    SET killer_guid_canonical = substring(killer_guid FROM 1 FOR 8)
    WHERE killer_guid_canonical IS NULL AND killer_guid IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_ski_killer_canonical
    ON storytelling_kill_impact(killer_guid_canonical);

COMMIT;

-- Verification query (run manually after migration):
--   SELECT table_name, column_name FROM information_schema.columns
--   WHERE column_name LIKE '%guid_canonical%' ORDER BY table_name;
--
-- Expected: 6 rows (the 6 tables above).
