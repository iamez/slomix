-- migrations/055_add_proximity_shot_fired.sql
-- v9 true-aim (Lua 6.02 SHOT_FIRED): per-shot shooter origin + view angles.
--
-- CONTEXT:
--   Phase 5.2 of the proximity redesign. The Lua emits an optional, DEFAULT-OFF
--   SHOT_FIRED section (features.shot_fired=false); the parser writes it here
--   when present. Until the Lua feature is enabled + deployed (separate HARD
--   STOP), this table simply stays empty — fully backward-compatible.
--
-- This migration is IDEMPOTENT (035-style):
--   - CREATE TABLE IF NOT EXISTS
--   - CREATE INDEX IF NOT EXISTS
--   - re-runnable with no effect once applied
--
-- Columns mirror parser.ProximityParserV4._import_shots_fired. The UNIQUE
-- index backs the parser's ON CONFLICT DO NOTHING (idempotent re-import).

BEGIN;

CREATE TABLE IF NOT EXISTS public.proximity_shot_fired (
    id                  SERIAL PRIMARY KEY,
    session_date        date NOT NULL,
    round_number        integer NOT NULL,
    round_start_unix    integer DEFAULT 0,
    round_end_unix      integer DEFAULT 0,
    map_name            character varying(64) NOT NULL,
    event_time          integer NOT NULL,
    guid                character varying(32) NOT NULL,
    weapon_id           integer NOT NULL,
    origin_x            integer NOT NULL,
    origin_y            integer NOT NULL,
    origin_z            integer NOT NULL,
    view_yaw            real DEFAULT 0,
    view_pitch          real DEFAULT 0,
    round_id            integer,
    round_link_source   character varying(32),
    round_link_reason   character varying(64),
    round_linked_at     timestamp without time zone,
    created_at          timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    guid_canonical      character varying(32)
);

-- Idempotent-import key (matches parser ON CONFLICT target).
CREATE UNIQUE INDEX IF NOT EXISTS uq_psf_identity
    ON public.proximity_shot_fired
    (session_date, round_number, round_start_unix, event_time, guid, weapon_id);

-- Per-player heatmap query path: WHERE map_name + session_date + guid.
CREATE INDEX IF NOT EXISTS idx_psf_guid_map_date
    ON public.proximity_shot_fired (guid, map_name, session_date);

CREATE INDEX IF NOT EXISTS idx_psf_canonical
    ON public.proximity_shot_fired (guid_canonical);

CREATE INDEX IF NOT EXISTS idx_psf_map_date
    ON public.proximity_shot_fired (map_name, session_date);

COMMIT;
