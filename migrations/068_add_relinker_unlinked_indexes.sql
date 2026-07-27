-- Complete the partial-index coverage for the proximity relinker's
-- round_id IS NULL discovery legs. Migration 014 created this index shape
-- for the 11 tables that existed in its original inventory; 13 later or
-- previously omitted tables still required full-table scans every five
-- minutes.
--
-- Deliberately transactional: the migration runner rejects live
-- CONCURRENTLY statements. Production applies this while services are
-- stopped through deploy_release.sh. IF NOT EXISTS makes retries safe.

CREATE INDEX IF NOT EXISTS idx_proximity_carrier_event_round_lookup_unlinked
    ON proximity_carrier_event (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_carrier_kill_round_lookup_unlinked
    ON proximity_carrier_kill (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_carrier_return_round_lookup_unlinked
    ON proximity_carrier_return (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_combat_position_round_lookup_unlinked
    ON proximity_combat_position (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_construction_event_round_lookup_unlinked
    ON proximity_construction_event (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_escort_credit_round_lookup_unlinked
    ON proximity_escort_credit (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_focus_fire_round_lookup_unlinked
    ON proximity_focus_fire (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_hit_region_round_lookup_unlinked
    ON proximity_hit_region (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_kill_outcome_round_lookup_unlinked
    ON proximity_kill_outcome (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_objective_run_round_lookup_unlinked
    ON proximity_objective_run (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_revive_round_lookup_unlinked
    ON proximity_revive (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_vehicle_progress_round_lookup_unlinked
    ON proximity_vehicle_progress (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_weapon_accuracy_round_lookup_unlinked
    ON proximity_weapon_accuracy (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
