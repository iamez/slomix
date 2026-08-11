-- proximity_aim_lock, proximity_comm_event, proximity_skill_snapshot and
-- proximity_spawn_select join the relinker's detection legs and fanout
-- (FIX 9, 2026-08-11), so they need the same partial index the other
-- detection tables got in migrations 014, 068 and 069. The four were created
-- by migration 058 (proximity v7) with a round_id and the full four-column
-- round identity, but were never added to any relinker list — the same hole
-- proximity_shot_fired sat in for three months, this time found by the
-- schema coverage contract (tests/unit/test_round_id_coverage_contract.py)
-- rather than by an incident. Measured on dev 2026-08-11: aim_lock 2,808
-- orphan rows of 28,427 total; comm_event 38; skill_snapshot 6;
-- spawn_select 91.
--
-- Column order matches 068 exactly (map_name, round_number,
-- round_start_unix, session_date): the detection leg selects all four and
-- the primary relink template filters on all four. These tables are small
-- (largest: aim_lock, ~28k rows), so the shot_fired-style recency-led
-- discovery/mismatch indexes from 069 are not warranted — 068 set the same
-- precedent for its thirteen small tables.
--
-- Deliberately transactional: the migration runner rejects live
-- CONCURRENTLY statements. Production applies this while services are
-- stopped through deploy_release.sh. IF NOT EXISTS makes retries safe.

CREATE INDEX IF NOT EXISTS idx_proximity_aim_lock_round_lookup_unlinked
    ON proximity_aim_lock (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_comm_event_round_lookup_unlinked
    ON proximity_comm_event (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_skill_snapshot_round_lookup_unlinked
    ON proximity_skill_snapshot (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
CREATE INDEX IF NOT EXISTS idx_proximity_spawn_select_round_lookup_unlinked
    ON proximity_spawn_select (map_name, round_number, round_start_unix, session_date)
    WHERE round_id IS NULL;
