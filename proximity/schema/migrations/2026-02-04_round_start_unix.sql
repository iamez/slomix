-- Add round_start_unix / round_end_unix to proximity tables
-- and update unique constraints to prevent same-day collisions.

-- combat_engagement
ALTER TABLE combat_engagement
    ADD COLUMN IF NOT EXISTS round_start_unix INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS round_end_unix INTEGER DEFAULT 0;

ALTER TABLE combat_engagement
    DROP CONSTRAINT IF EXISTS combat_engagement_session_date_round_number_engagement_id_key;

ALTER TABLE combat_engagement
    ADD CONSTRAINT combat_engagement_session_date_round_number_round_start_unix_engagement_id_key
    UNIQUE (session_date, round_number, round_start_unix, engagement_id);

-- player_track
ALTER TABLE player_track
    ADD COLUMN IF NOT EXISTS round_start_unix INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS round_end_unix INTEGER DEFAULT 0;

ALTER TABLE player_track
    DROP CONSTRAINT IF EXISTS player_track_session_date_round_number_player_guid_spawn_time_ms_key;

ALTER TABLE player_track
    ADD CONSTRAINT player_track_session_date_round_number_round_start_unix_player_guid_spawn_time_ms_key
    UNIQUE (session_date, round_number, round_start_unix, player_guid, spawn_time_ms);

-- proximity_objective_focus
ALTER TABLE proximity_objective_focus
    ADD COLUMN IF NOT EXISTS round_start_unix INTEGER DEFAULT 0,
    ADD COLUMN IF NOT EXISTS round_end_unix INTEGER DEFAULT 0;

ALTER TABLE proximity_objective_focus
    DROP CONSTRAINT IF EXISTS proximity_objective_focus_session_date_round_number_player_guid_key;

ALTER TABLE proximity_objective_focus
    ADD CONSTRAINT proximity_objective_focus_session_date_round_number_round_start_unix_player_guid_key
    UNIQUE (session_date, round_number, round_start_unix, player_guid);
