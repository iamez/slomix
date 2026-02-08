-- Monitoring table ownership + permissions fix
-- Run as a PostgreSQL superuser (or current owner of these objects).
--
-- Purpose:
-- 1) Ensure bot role can manage both monitoring tables consistently.
-- 2) Remove startup DDL ownership conflicts for voice/server history objects.
--
-- Example:
--   sudo -u postgres psql -d etlegacy -f website/fix_monitoring_table_ownership.sql

DO $$
BEGIN
    IF to_regclass('public.server_status_history') IS NOT NULL THEN
        ALTER TABLE public.server_status_history OWNER TO etlegacy_user;
    END IF;

    IF to_regclass('public.voice_status_history') IS NOT NULL THEN
        ALTER TABLE public.voice_status_history OWNER TO etlegacy_user;
    END IF;

    IF to_regclass('public.server_status_history_id_seq') IS NOT NULL THEN
        ALTER SEQUENCE public.server_status_history_id_seq OWNER TO etlegacy_user;
    END IF;

    IF to_regclass('public.voice_status_history_id_seq') IS NOT NULL THEN
        ALTER SEQUENCE public.voice_status_history_id_seq OWNER TO etlegacy_user;
    END IF;

    IF to_regclass('public.idx_server_status_history_recorded_at') IS NOT NULL THEN
        ALTER INDEX public.idx_server_status_history_recorded_at OWNER TO etlegacy_user;
    END IF;

    IF to_regclass('public.idx_server_status_history_player_count') IS NOT NULL THEN
        ALTER INDEX public.idx_server_status_history_player_count OWNER TO etlegacy_user;
    END IF;

    IF to_regclass('public.idx_voice_status_history_recorded_at') IS NOT NULL THEN
        ALTER INDEX public.idx_voice_status_history_recorded_at OWNER TO etlegacy_user;
    END IF;

    IF to_regclass('public.idx_voice_status_history_first_joiner') IS NOT NULL THEN
        ALTER INDEX public.idx_voice_status_history_first_joiner OWNER TO etlegacy_user;
    END IF;
END
$$;

GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.server_status_history TO etlegacy_user;
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLE public.voice_status_history TO etlegacy_user;

GRANT USAGE, SELECT ON SEQUENCE public.server_status_history_id_seq TO etlegacy_user;
GRANT USAGE, SELECT ON SEQUENCE public.voice_status_history_id_seq TO etlegacy_user;
