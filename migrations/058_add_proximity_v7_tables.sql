-- migrations/058_add_proximity_v7_tables.sql
-- v7 draft (Lua 6.10): four DORMANT capture tables.
--
-- CONTEXT:
--   Phase 3 of the proximity-vision plan (docs/LUA_V7_CAPTURE_RESEARCH_2026-06.md).
--   The Lua 6.10 draft emits four optional, DEFAULT-OFF sections:
--     AIM_LOCK       — crosshair-on-enemy lock windows (trap_Trace confirmed)
--     SPAWN_SELECT   — chosen spawn point per real spawn (sess.spawnObjectiveIndex)
--     SKILL_SNAPSHOT — sess.skill array per player at round end (SK_* 0-6)
--     COMM_EVENTS    — voice-macro/chat-type usage (no free text captured)
--   Until the Lua features are enabled + deployed (owner-gated, separate step)
--   these tables stay empty — fully backward-compatible.
--
-- This migration is IDEMPOTENT (055-style): CREATE TABLE/INDEX IF NOT EXISTS.
-- UNIQUE indexes back the parser's ON CONFLICT DO NOTHING re-import keys.

BEGIN;

-- ===== AIM_LOCK =====
CREATE TABLE IF NOT EXISTS public.proximity_aim_lock (
    id                     SERIAL PRIMARY KEY,
    session_date           date NOT NULL,
    round_number           integer NOT NULL,
    round_start_unix       integer DEFAULT 0,
    round_end_unix         integer DEFAULT 0,
    map_name               character varying(64) NOT NULL,
    start_time             integer NOT NULL,
    end_time               integer NOT NULL,
    duration_ms            integer NOT NULL,
    guid                   character varying(32) NOT NULL,
    player_name            character varying(64),
    team                   character varying(10),
    target_guid            character varying(32) NOT NULL,
    target_name            character varying(64),
    avg_err_deg            real DEFAULT 0,
    avg_dist               integer DEFAULT 0,
    samples                integer DEFAULT 0,
    round_id               integer,
    round_link_source      character varying(32),
    round_link_reason      character varying(64),
    round_linked_at        timestamp without time zone,
    created_at             timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    guid_canonical         character varying(32),
    target_guid_canonical  character varying(32)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pal_identity
    ON public.proximity_aim_lock
    (session_date, round_number, round_start_unix, start_time, guid, target_guid);

CREATE INDEX IF NOT EXISTS idx_pal_guid_date
    ON public.proximity_aim_lock (guid, session_date);

CREATE INDEX IF NOT EXISTS idx_pal_round_id
    ON public.proximity_aim_lock (round_id);

-- ===== SPAWN_SELECT =====
CREATE TABLE IF NOT EXISTS public.proximity_spawn_select (
    id                  SERIAL PRIMARY KEY,
    session_date        date NOT NULL,
    round_number        integer NOT NULL,
    round_start_unix    integer DEFAULT 0,
    round_end_unix      integer DEFAULT 0,
    map_name            character varying(64) NOT NULL,
    event_time          integer NOT NULL,
    guid                character varying(32) NOT NULL,
    player_name         character varying(64),
    team                character varying(10),
    spawn_index         integer DEFAULT -1,
    last_spawn_time     integer DEFAULT 0,
    round_id            integer,
    round_link_source   character varying(32),
    round_link_reason   character varying(64),
    round_linked_at     timestamp without time zone,
    created_at          timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    guid_canonical      character varying(32)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pss_identity
    ON public.proximity_spawn_select
    (session_date, round_number, round_start_unix, event_time, guid);

CREATE INDEX IF NOT EXISTS idx_pss_guid_date
    ON public.proximity_spawn_select (guid, session_date);

-- ===== SKILL_SNAPSHOT =====
CREATE TABLE IF NOT EXISTS public.proximity_skill_snapshot (
    id                  SERIAL PRIMARY KEY,
    session_date        date NOT NULL,
    round_number        integer NOT NULL,
    round_start_unix    integer DEFAULT 0,
    round_end_unix      integer DEFAULT 0,
    map_name            character varying(64) NOT NULL,
    guid                character varying(32) NOT NULL,
    player_name         character varying(64),
    team                character varying(10),
    battle_sense        integer DEFAULT 0,
    engineering         integer DEFAULT 0,
    first_aid           integer DEFAULT 0,
    signals             integer DEFAULT 0,
    light_weapons       integer DEFAULT 0,
    heavy_weapons       integer DEFAULT 0,
    covertops           integer DEFAULT 0,
    round_id            integer,
    round_link_source   character varying(32),
    round_link_reason   character varying(64),
    round_linked_at     timestamp without time zone,
    created_at          timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    guid_canonical      character varying(32)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_psk_identity
    ON public.proximity_skill_snapshot
    (session_date, round_number, round_start_unix, guid);

CREATE INDEX IF NOT EXISTS idx_psk_guid_date
    ON public.proximity_skill_snapshot (guid, session_date);

-- ===== COMM_EVENTS =====
CREATE TABLE IF NOT EXISTS public.proximity_comm_event (
    id                  SERIAL PRIMARY KEY,
    session_date        date NOT NULL,
    round_number        integer NOT NULL,
    round_start_unix    integer DEFAULT 0,
    round_end_unix      integer DEFAULT 0,
    map_name            character varying(64) NOT NULL,
    event_time          integer NOT NULL,
    guid                character varying(32) NOT NULL,
    player_name         character varying(64),
    team                character varying(10),
    cmd                 character varying(16) NOT NULL,
    arg                 character varying(32) DEFAULT '',
    round_id            integer,
    round_link_source   character varying(32),
    round_link_reason   character varying(64),
    round_linked_at     timestamp without time zone,
    created_at          timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    guid_canonical      character varying(32)
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_pce_identity
    ON public.proximity_comm_event
    (session_date, round_number, round_start_unix, event_time, guid, cmd);

CREATE INDEX IF NOT EXISTS idx_pce_guid_date
    ON public.proximity_comm_event (guid, session_date);

COMMIT;
