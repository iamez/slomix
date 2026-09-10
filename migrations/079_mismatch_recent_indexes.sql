-- The relinker's five-minute sweep has TWO leg families per detection table:
-- the round_id IS NULL legs (indexed by 014/068/069/071) and the MISMATCH
-- legs, which join rounds over rows that HAVE a round_id and filter on the
-- six-hour cutoff (round_start_unix >= $1). Only proximity_shot_fired ever
-- got an index for that shape (069) — measured on dev 2026-08-26, the other
-- 28 tables answer the mismatch legs with sequential scans, and the four
-- largest (proximity_team_cohesion 390 MB, player_track 274 MB,
-- combat_engagement 211 MB, proximity_hit_region 177 MB) put the whole
-- sweep at 10-22 s per run, twelve times an hour, for 0 rows.
--
-- Shape copied from 069's idx_proximity_shot_fired_mismatch_recent:
-- (round_start_unix, round_id) WHERE round_id IS NOT NULL. The partial
-- predicate keeps the index disjoint from the unlinked family and the
-- leading cutoff column makes the leg seekable.
--
-- Deliberately transactional: the migration runner rejects live CONCURRENTLY
-- statements. Production applies this while services are stopped through
-- deploy_release.sh. IF NOT EXISTS makes retries safe.
--
-- ⚠️ proximity_reaction_metric is NOT in this file. It is owned by
-- website_app (the only detection table that is), and this runner connects
-- as etlegacy_user, which cannot create an index on a table it does not
-- own. Apply the same statement separately, as the owner:
--
--   PGPASSWORD=... psql -h 127.0.0.1 -U website_app -d etlegacy -c \
--     "CREATE INDEX IF NOT EXISTS idx_proximity_reaction_metric_mismatch_recent
--        ON proximity_reaction_metric (round_start_unix, round_id)
--        WHERE round_id IS NOT NULL;"

CREATE INDEX IF NOT EXISTS idx_proximity_spawn_timing_mismatch_recent
    ON proximity_spawn_timing (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_team_cohesion_mismatch_recent
    ON proximity_team_cohesion (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_kill_outcome_mismatch_recent
    ON proximity_kill_outcome (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_carrier_event_mismatch_recent
    ON proximity_carrier_event (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_carrier_kill_mismatch_recent
    ON proximity_carrier_kill (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_carrier_return_mismatch_recent
    ON proximity_carrier_return (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_combat_position_mismatch_recent
    ON proximity_combat_position (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_construction_event_mismatch_recent
    ON proximity_construction_event (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_crossfire_opportunity_mismatch_recent
    ON proximity_crossfire_opportunity (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_escort_credit_mismatch_recent
    ON proximity_escort_credit (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_focus_fire_mismatch_recent
    ON proximity_focus_fire (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_hit_region_mismatch_recent
    ON proximity_hit_region (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_lua_trade_kill_mismatch_recent
    ON proximity_lua_trade_kill (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_objective_focus_mismatch_recent
    ON proximity_objective_focus (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_objective_run_mismatch_recent
    ON proximity_objective_run (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_support_summary_mismatch_recent
    ON proximity_support_summary (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_team_push_mismatch_recent
    ON proximity_team_push (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_trade_event_mismatch_recent
    ON proximity_trade_event (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_vehicle_progress_mismatch_recent
    ON proximity_vehicle_progress (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_combat_engagement_mismatch_recent
    ON combat_engagement (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_player_track_mismatch_recent
    ON player_track (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_revive_mismatch_recent
    ON proximity_revive (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_weapon_accuracy_mismatch_recent
    ON proximity_weapon_accuracy (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_aim_lock_mismatch_recent
    ON proximity_aim_lock (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_comm_event_mismatch_recent
    ON proximity_comm_event (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_skill_snapshot_mismatch_recent
    ON proximity_skill_snapshot (round_start_unix, round_id) WHERE round_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_spawn_select_mismatch_recent
    ON proximity_spawn_select (round_start_unix, round_id) WHERE round_id IS NOT NULL;

-- lua_round_teams runs its own leg pair (no session_date column) and had
-- NEITHER family: its null leg filters round_id IS NULL AND
-- round_start_unix >= $1, its mismatch leg the NOT NULL complement. The
-- table is small today (~1 MB); the indexes are for the shape, not the
-- size, so the sweep stays flat as it grows.
CREATE INDEX IF NOT EXISTS idx_lua_round_teams_unlinked_recent
    ON lua_round_teams (round_start_unix) WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_lua_round_teams_mismatch_recent
    ON lua_round_teams (round_start_unix, round_id) WHERE round_id IS NOT NULL;
