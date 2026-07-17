-- ============================================================================
-- PostgreSQL Schema Reference for ET:Legacy Discord Bot (Slomix)
-- ============================================================================
-- Source: pg_dump -s --no-owner --no-privileges (live `etlegacy` database)
-- Regenerated: 2026-05-11 via tools/regen_schema_dump.sh
-- PostgreSQL: 14 (dev) / 17 (prod)
-- Total tables: 90 | Total indexes: 416
--   (252 CREATE INDEX + 164 from PK/UNIQUE constraints)
--
-- This file is AUTHORITATIVE — generated from real schema state, not
-- hand-curated. For canonical change history use migrations/*.sql.
--
-- To regenerate after schema migrations:
--   PGPASSWORD=... ./tools/regen_schema_dump.sh
-- ============================================================================

--
-- PostgreSQL database dump
--


-- Dumped from database version 14.22 (Ubuntu 14.22-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 14.22 (Ubuntu 14.22-0ubuntu0.22.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: compute_guid_canonical(text, text); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.compute_guid_canonical(raw_guid text, raw_name text) RETURNS text
    LANGUAGE plpgsql IMMUTABLE
    AS $$
BEGIN
    IF raw_guid IS NULL OR raw_guid = '' THEN
        RETURN NULL;
    END IF;
    IF raw_guid LIKE 'OMNIBOT%' OR raw_guid LIKE 'SLOT%' THEN
        -- Bot: OMNIBOT0 + sha256(clean_name)[:24]
        IF raw_name IS NOT NULL AND raw_name != '' THEN
            RETURN 'OMNIBOT0' || LEFT(encode(digest(regexp_replace(raw_name, E'\\^.', '', 'g'), 'sha256'), 'hex'), 24);
        END IF;
        RETURN NULL;
    END IF;
    -- Human: first 8 chars
    RETURN LEFT(raw_guid, 8);
END;
$$;


--
-- Name: get_crossfire_partners(character varying); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.get_crossfire_partners(p_guid character varying) RETURNS TABLE(partner_guid character varying, partner_name character varying, crossfire_count integer, crossfire_kills integer, avg_delay_ms real)
    LANGUAGE plpgsql
    AS $$
BEGIN
    RETURN QUERY
    SELECT 
        CASE WHEN player1_guid = p_guid THEN player2_guid ELSE player1_guid END,
        CASE WHEN player1_guid = p_guid THEN player2_name ELSE player1_name END,
        cp.crossfire_count,
        cp.crossfire_kills,
        cp.avg_delay_ms
    FROM crossfire_pairs cp
    WHERE player1_guid = p_guid OR player2_guid = p_guid
    ORDER BY cp.crossfire_kills DESC;
END;
$$;


--
-- Name: trg_cp_canonical(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_cp_canonical() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN NEW.attacker_guid_canonical := compute_guid_canonical(NEW.attacker_guid, NEW.attacker_name); RETURN NEW; END;
$$;


--
-- Name: trg_ko_canonical(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_ko_canonical() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN NEW.killer_guid_canonical := compute_guid_canonical(NEW.killer_guid, NEW.killer_name); RETURN NEW; END;
$$;


--
-- Name: trg_pts_canonical(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_pts_canonical() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN NEW.player_guid_canonical := compute_guid_canonical(NEW.player_guid, NEW.player_name); RETURN NEW; END;
$$;


--
-- Name: trg_ski_canonical(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_ski_canonical() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN NEW.killer_guid_canonical := compute_guid_canonical(NEW.killer_guid, NEW.killer_name); RETURN NEW; END;
$$;


--
-- Name: trg_st_canonical(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_st_canonical() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN NEW.killer_guid_canonical := compute_guid_canonical(NEW.killer_guid, NEW.killer_name); RETURN NEW; END;
$$;


--
-- Name: trg_tk_canonical(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.trg_tk_canonical() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN NEW.trader_guid_canonical := compute_guid_canonical(NEW.trader_guid, NEW.trader_name); RETURN NEW; END;
$$;


--
-- Name: update_player_stats_from_engagement(integer); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.update_player_stats_from_engagement(p_engagement_id integer) RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    eng RECORD;
    attacker RECORD;
BEGIN
    -- Get engagement
    SELECT * INTO eng FROM combat_engagement WHERE id = p_engagement_id;
    IF NOT FOUND THEN RETURN; END IF;
    
    -- Update target's defensive stats
    INSERT INTO player_teamplay_stats (player_guid, player_name, times_targeted)
    VALUES (eng.target_guid, eng.target_name, 1)
    ON CONFLICT (player_guid) DO UPDATE SET
        player_name = EXCLUDED.player_name,
        times_targeted = player_teamplay_stats.times_targeted + 1,
        last_updated = CURRENT_TIMESTAMP;
    
    -- Update based on outcome and attacker count
    IF eng.num_attackers >= 2 THEN
        -- Was focused
        UPDATE player_teamplay_stats SET
            times_focused = times_focused + 1,
            focus_escapes = focus_escapes + CASE WHEN eng.outcome = 'escaped' THEN 1 ELSE 0 END,
            focus_deaths = focus_deaths + CASE WHEN eng.outcome = 'killed' THEN 1 ELSE 0 END
        WHERE player_guid = eng.target_guid;
    ELSE
        -- 1v1
        UPDATE player_teamplay_stats SET
            solo_escapes = solo_escapes + CASE WHEN eng.outcome = 'escaped' THEN 1 ELSE 0 END,
            solo_deaths = solo_deaths + CASE WHEN eng.outcome = 'killed' THEN 1 ELSE 0 END
        WHERE player_guid = eng.target_guid;
    END IF;
    
    -- Note: Attacker stats are updated by the Python parser since it needs to iterate JSON
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account_link_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_link_audit_log (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    discord_user_id bigint,
    action text NOT NULL,
    actor_discord_id bigint,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT account_link_audit_log_action_check CHECK ((action = ANY (ARRAY['discord_linked'::text, 'discord_unlinked'::text, 'player_linked'::text, 'player_unlinked'::text, 'player_changed'::text])))
);


--
-- Name: account_link_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_link_audit_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_link_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_link_audit_log_id_seq OWNED BY public.account_link_audit_log.id;


--
-- Name: achievement_notification_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.achievement_notification_ledger (
    id integer NOT NULL,
    achievement_id text NOT NULL,
    player_guid text NOT NULL,
    achievement_type character varying(16) NOT NULL,
    milestone_threshold text NOT NULL,
    claimed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: achievement_notification_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.achievement_notification_ledger_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: achievement_notification_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.achievement_notification_ledger_id_seq OWNED BY public.achievement_notification_ledger.id;


--
-- Name: availability_channel_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.availability_channel_links (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    channel_type text NOT NULL,
    destination text,
    verification_token_hash text,
    token_expires_at timestamp without time zone,
    verification_requested_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    verified_at timestamp without time zone,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT availability_channel_links_channel_type_check CHECK ((channel_type = ANY (ARRAY['discord'::text, 'telegram'::text, 'signal'::text])))
);


--
-- Name: availability_channel_links_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.availability_channel_links_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: availability_channel_links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.availability_channel_links_id_seq OWNED BY public.availability_channel_links.id;


--
-- Name: availability_entries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.availability_entries (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    user_name text,
    entry_date date NOT NULL,
    status text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT availability_entries_status_check CHECK ((status = ANY (ARRAY['LOOKING'::text, 'AVAILABLE'::text, 'MAYBE'::text, 'NOT_PLAYING'::text])))
);


--
-- Name: availability_entries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.availability_entries_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: availability_entries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.availability_entries_id_seq OWNED BY public.availability_entries.id;


--
-- Name: availability_promotion_campaigns; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.availability_promotion_campaigns (
    id bigint NOT NULL,
    campaign_date date NOT NULL,
    target_timezone text DEFAULT 'Europe/Ljubljana'::text NOT NULL,
    target_start_time time without time zone DEFAULT '21:00:00'::time without time zone NOT NULL,
    initiated_by_user_id bigint NOT NULL,
    initiated_by_discord_id bigint NOT NULL,
    include_maybe boolean DEFAULT false NOT NULL,
    include_available boolean DEFAULT false NOT NULL,
    dry_run boolean DEFAULT false NOT NULL,
    status text DEFAULT 'scheduled'::text NOT NULL,
    idempotency_key text NOT NULL,
    recipient_count integer DEFAULT 0 NOT NULL,
    channels_summary jsonb DEFAULT '{}'::jsonb NOT NULL,
    recipients_snapshot jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT availability_promotion_campaigns_status_check CHECK ((status = ANY (ARRAY['scheduled'::text, 'running'::text, 'sent'::text, 'followup_sent'::text, 'partial'::text, 'failed'::text, 'cancelled'::text])))
);


--
-- Name: availability_promotion_campaigns_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.availability_promotion_campaigns_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: availability_promotion_campaigns_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.availability_promotion_campaigns_id_seq OWNED BY public.availability_promotion_campaigns.id;


--
-- Name: availability_promotion_jobs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.availability_promotion_jobs (
    id bigint NOT NULL,
    campaign_id bigint NOT NULL,
    job_type text NOT NULL,
    run_at timestamp with time zone NOT NULL,
    status text DEFAULT 'pending'::text NOT NULL,
    attempts integer DEFAULT 0 NOT NULL,
    max_attempts integer DEFAULT 5 NOT NULL,
    last_error text,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    sent_at timestamp with time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT availability_promotion_jobs_job_type_check CHECK ((job_type = ANY (ARRAY['send_reminder_2045'::text, 'send_start_2100'::text, 'voice_check_2100'::text]))),
    CONSTRAINT availability_promotion_jobs_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'running'::text, 'sent'::text, 'skipped'::text, 'failed'::text])))
);


--
-- Name: availability_promotion_jobs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.availability_promotion_jobs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: availability_promotion_jobs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.availability_promotion_jobs_id_seq OWNED BY public.availability_promotion_jobs.id;


--
-- Name: availability_promotion_send_logs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.availability_promotion_send_logs (
    id bigint NOT NULL,
    campaign_id bigint NOT NULL,
    job_id bigint,
    user_id bigint NOT NULL,
    channel_type text NOT NULL,
    status text NOT NULL,
    message_id text,
    error text,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT availability_promotion_send_logs_channel_type_check CHECK ((channel_type = ANY (ARRAY['discord'::text, 'telegram'::text, 'signal'::text]))),
    CONSTRAINT availability_promotion_send_logs_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'sent'::text, 'failed'::text, 'skipped'::text])))
);


--
-- Name: availability_promotion_send_logs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.availability_promotion_send_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: availability_promotion_send_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.availability_promotion_send_logs_id_seq OWNED BY public.availability_promotion_send_logs.id;


--
-- Name: availability_subscriptions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.availability_subscriptions (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    channel_type text NOT NULL,
    channel_address text,
    enabled boolean DEFAULT true NOT NULL,
    verified_at timestamp without time zone,
    preferences jsonb DEFAULT '{}'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT availability_subscriptions_channel_type_check CHECK ((channel_type = ANY (ARRAY['discord'::text, 'telegram'::text, 'signal'::text])))
);


--
-- Name: availability_subscriptions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.availability_subscriptions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: availability_subscriptions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.availability_subscriptions_id_seq OWNED BY public.availability_subscriptions.id;


--
-- Name: availability_user_settings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.availability_user_settings (
    user_id bigint NOT NULL,
    sound_enabled boolean DEFAULT true NOT NULL,
    sound_cooldown_seconds integer DEFAULT 480 NOT NULL,
    availability_reminders_enabled boolean DEFAULT true NOT NULL,
    timezone text DEFAULT 'UTC'::text NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: crossfire_pairs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.crossfire_pairs (
    id integer NOT NULL,
    player1_guid character varying(32) NOT NULL,
    player1_name character varying(64),
    player2_guid character varying(32) NOT NULL,
    player2_name character varying(64),
    crossfire_count integer DEFAULT 0,
    crossfire_kills integer DEFAULT 0,
    total_combined_damage integer DEFAULT 0,
    avg_delay_ms real,
    games_together integer DEFAULT 0,
    first_played timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_played timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: best_duos; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.best_duos AS
 SELECT crossfire_pairs.player1_name,
    crossfire_pairs.player2_name,
    crossfire_pairs.crossfire_count,
    crossfire_pairs.crossfire_kills,
    round(((100.0 * (crossfire_pairs.crossfire_kills)::numeric) / (NULLIF(crossfire_pairs.crossfire_count, 0))::numeric), 1) AS kill_rate,
    round((crossfire_pairs.avg_delay_ms)::numeric, 0) AS sync_ms,
    crossfire_pairs.games_together
   FROM public.crossfire_pairs
  WHERE (crossfire_pairs.crossfire_count >= 5)
  ORDER BY crossfire_pairs.crossfire_kills DESC;


--
-- Name: combat_engagement; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.combat_engagement (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    map_name character varying(64) NOT NULL,
    engagement_id integer NOT NULL,
    start_time_ms integer NOT NULL,
    end_time_ms integer NOT NULL,
    duration_ms integer NOT NULL,
    target_guid character varying(32) NOT NULL,
    target_name character varying(64) NOT NULL,
    target_team character varying(10) NOT NULL,
    outcome character varying(20) NOT NULL,
    total_damage_taken integer NOT NULL,
    killer_guid character varying(32),
    killer_name character varying(64),
    position_path jsonb DEFAULT '[]'::jsonb NOT NULL,
    start_x real NOT NULL,
    start_y real NOT NULL,
    start_z real NOT NULL,
    end_x real NOT NULL,
    end_y real NOT NULL,
    end_z real NOT NULL,
    distance_traveled real NOT NULL,
    attackers jsonb DEFAULT '[]'::jsonb NOT NULL,
    num_attackers integer NOT NULL,
    is_crossfire boolean DEFAULT false NOT NULL,
    crossfire_delay_ms integer,
    crossfire_participants jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone
);


--
-- Name: combat_engagement_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.combat_engagement_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: combat_engagement_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.combat_engagement_id_seq OWNED BY public.combat_engagement.id;


--
-- Name: crossfire_pairs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.crossfire_pairs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: crossfire_pairs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.crossfire_pairs_id_seq OWNED BY public.crossfire_pairs.id;


--
-- Name: voice_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voice_members (
    id integer NOT NULL,
    discord_id bigint NOT NULL,
    member_name character varying(255) NOT NULL,
    channel_id bigint NOT NULL,
    channel_name character varying(255),
    joined_at timestamp with time zone DEFAULT now(),
    left_at timestamp with time zone
);


--
-- Name: current_voice_status; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.current_voice_status AS
 SELECT count(*) AS member_count,
    voice_members.channel_id,
    voice_members.channel_name,
    jsonb_agg(jsonb_build_object('discord_id', voice_members.discord_id, 'name', voice_members.member_name, 'joined_at', voice_members.joined_at) ORDER BY voice_members.joined_at) AS members,
    min(voice_members.joined_at) AS session_start,
    ( SELECT voice_members_1.discord_id
           FROM public.voice_members voice_members_1
          WHERE (voice_members_1.left_at IS NULL)
          ORDER BY voice_members_1.joined_at
         LIMIT 1) AS first_joiner_id,
    ( SELECT voice_members_1.member_name
           FROM public.voice_members voice_members_1
          WHERE (voice_members_1.left_at IS NULL)
          ORDER BY voice_members_1.joined_at
         LIMIT 1) AS first_joiner_name
   FROM public.voice_members
  WHERE (voice_members.left_at IS NULL)
  GROUP BY voice_members.channel_id, voice_members.channel_name;


--
-- Name: daily_polls; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.daily_polls (
    id integer NOT NULL,
    poll_date date NOT NULL,
    channel_id bigint NOT NULL,
    message_id bigint NOT NULL,
    guild_id bigint NOT NULL,
    threshold_reached boolean DEFAULT false,
    threshold_notified_at timestamp without time zone,
    reminder_sent_at timestamp without time zone,
    event_id bigint,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: daily_polls_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.daily_polls_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: daily_polls_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.daily_polls_id_seq OWNED BY public.daily_polls.id;


--
-- Name: discord_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.discord_accounts (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    discord_user_id bigint NOT NULL,
    username text NOT NULL,
    display_name text,
    avatar text,
    linked_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_refreshed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: discord_accounts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.discord_accounts_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: discord_accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.discord_accounts_id_seq OWNED BY public.discord_accounts.id;


--
-- Name: greatshot_analysis; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.greatshot_analysis (
    demo_id text NOT NULL,
    metadata_json jsonb NOT NULL,
    stats_json jsonb NOT NULL,
    events_json jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    total_kills integer DEFAULT 0
);


--
-- Name: greatshot_demos; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.greatshot_demos (
    id text NOT NULL,
    user_id bigint NOT NULL,
    original_filename text NOT NULL,
    stored_path text NOT NULL,
    extension text NOT NULL,
    file_size_bytes bigint NOT NULL,
    content_hash_sha256 text NOT NULL,
    status text DEFAULT 'uploaded'::text NOT NULL,
    error text,
    metadata_json jsonb,
    warnings_json jsonb,
    analysis_json_path text,
    report_txt_path text,
    processing_started_at timestamp without time zone,
    processing_finished_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: greatshot_highlights; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.greatshot_highlights (
    id text NOT NULL,
    demo_id text NOT NULL,
    type text NOT NULL,
    player text,
    start_ms integer NOT NULL,
    end_ms integer NOT NULL,
    score double precision NOT NULL,
    meta_json jsonb,
    clip_demo_path text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: greatshot_renders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.greatshot_renders (
    id text NOT NULL,
    highlight_id text NOT NULL,
    status text DEFAULT 'queued'::text NOT NULL,
    mp4_path text,
    error text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: live_status; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.live_status (
    id integer NOT NULL,
    status_type character varying(50) NOT NULL,
    status_data jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp with time zone DEFAULT now()
);


--
-- Name: live_status_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.live_status_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: live_status_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.live_status_id_seq OWNED BY public.live_status.id;


--
-- Name: lua_round_teams; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lua_round_teams (
    id integer NOT NULL,
    match_id character varying(64) NOT NULL,
    round_number integer NOT NULL,
    axis_players jsonb DEFAULT '[]'::jsonb,
    allies_players jsonb DEFAULT '[]'::jsonb,
    round_start_unix bigint,
    round_end_unix bigint,
    actual_duration_seconds integer,
    total_pause_seconds integer DEFAULT 0,
    pause_count integer DEFAULT 0,
    end_reason character varying(20),
    winner_team integer,
    defender_team integer,
    map_name character varying(64),
    time_limit_minutes integer,
    captured_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP,
    lua_version character varying(16),
    lua_warmup_seconds integer DEFAULT 0,
    lua_warmup_start_unix bigint DEFAULT 0,
    lua_pause_events jsonb DEFAULT '[]'::jsonb,
    surrender_caller_guid character varying(32),
    surrender_caller_name character varying(64),
    surrender_team integer DEFAULT 0,
    axis_score integer DEFAULT 0,
    allies_score integer DEFAULT 0,
    round_id integer
);


--
-- Name: TABLE lua_round_teams; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.lua_round_teams IS 'Real-time round data captured by Slomix Lua webhook (stats_discord_webhook.lua v1.3.0). All timing fields with lua_ prefix come from this source, not from the stats file. Includes pause timestamps for detailed timing analysis.';


--
-- Name: COLUMN lua_round_teams.axis_players; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.axis_players IS 'JSON array of players on Axis team: [{"guid":"...","name":"..."}]';


--
-- Name: COLUMN lua_round_teams.allies_players; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.allies_players IS 'JSON array of players on Allies team: [{"guid":"...","name":"..."}]';


--
-- Name: COLUMN lua_round_teams.round_start_unix; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.round_start_unix IS 'Unix timestamp when GS_PLAYING started (from Slomix Lua)';


--
-- Name: COLUMN lua_round_teams.round_end_unix; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.round_end_unix IS 'Unix timestamp when GS_INTERMISSION started (from Slomix Lua)';


--
-- Name: COLUMN lua_round_teams.actual_duration_seconds; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.actual_duration_seconds IS 'Actual playtime in seconds, excluding pauses (from Slomix Lua)';


--
-- Name: COLUMN lua_round_teams.total_pause_seconds; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.total_pause_seconds IS 'Total time spent paused during round (from Slomix Lua)';


--
-- Name: COLUMN lua_round_teams.end_reason; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.end_reason IS 'How round ended: objective, surrender, time_expired';


--
-- Name: COLUMN lua_round_teams.lua_warmup_seconds; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.lua_warmup_seconds IS 'Pre-round warmup duration in seconds (from Slomix Lua v1.2.0+)';


--
-- Name: COLUMN lua_round_teams.lua_warmup_start_unix; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.lua_warmup_start_unix IS 'Unix timestamp when warmup phase began (from Slomix Lua v1.2.0+)';


--
-- Name: COLUMN lua_round_teams.lua_pause_events; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.lua_pause_events IS 'JSON array of pause events: [{n:pause_number, start:unix_timestamp, end:unix_timestamp, sec:duration}]';


--
-- Name: COLUMN lua_round_teams.surrender_caller_guid; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.surrender_caller_guid IS 'GUID of player who called surrender vote (v1.4.0)';


--
-- Name: COLUMN lua_round_teams.surrender_caller_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.surrender_caller_name IS 'Name of player who called surrender vote (v1.4.0)';


--
-- Name: COLUMN lua_round_teams.surrender_team; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.surrender_team IS 'Team that surrendered: 1=Axis, 2=Allies, 0=no surrender (v1.4.0)';


--
-- Name: COLUMN lua_round_teams.axis_score; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.axis_score IS 'Running Axis wins in match at time of this round (v1.4.0)';


--
-- Name: COLUMN lua_round_teams.allies_score; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.allies_score IS 'Running Allies wins in match at time of this round (v1.4.0)';


--
-- Name: COLUMN lua_round_teams.round_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_round_teams.round_id IS 'FK to rounds.id when resolvable (links Lua webhook rows to rounds)';


--
-- Name: lua_round_teams_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lua_round_teams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lua_round_teams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lua_round_teams_id_seq OWNED BY public.lua_round_teams.id;


--
-- Name: lua_spawn_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.lua_spawn_stats (
    id integer NOT NULL,
    match_id character varying(64) NOT NULL,
    round_number integer NOT NULL,
    round_id integer,
    map_name character varying(64),
    round_end_unix bigint,
    player_guid character varying(32),
    player_name character varying(64),
    spawn_count integer DEFAULT 0,
    death_count integer DEFAULT 0,
    dead_seconds integer DEFAULT 0,
    avg_respawn_seconds integer DEFAULT 0,
    max_respawn_seconds integer DEFAULT 0,
    captured_at timestamp with time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE lua_spawn_stats; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.lua_spawn_stats IS 'Per-player spawn/death timing captured by Lua webhook (v1.6.0).';


--
-- Name: COLUMN lua_spawn_stats.dead_seconds; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_spawn_stats.dead_seconds IS 'Total time spent dead (seconds) based on death→spawn intervals.';


--
-- Name: COLUMN lua_spawn_stats.avg_respawn_seconds; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.lua_spawn_stats.avg_respawn_seconds IS 'Average respawn time (dead_seconds / death_count).';


--
-- Name: lua_spawn_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.lua_spawn_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: lua_spawn_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.lua_spawn_stats_id_seq OWNED BY public.lua_spawn_stats.id;


--
-- Name: map_kill_heatmap; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_kill_heatmap (
    id integer NOT NULL,
    map_name character varying(64) NOT NULL,
    grid_x integer NOT NULL,
    grid_y integer NOT NULL,
    grid_size integer DEFAULT 512,
    total_kills integer DEFAULT 0,
    axis_kills integer DEFAULT 0,
    allies_kills integer DEFAULT 0,
    total_deaths integer DEFAULT 0,
    axis_deaths integer DEFAULT 0,
    allies_deaths integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: map_hotspots; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.map_hotspots AS
 SELECT map_kill_heatmap.map_name,
    map_kill_heatmap.grid_x,
    map_kill_heatmap.grid_y,
    map_kill_heatmap.total_kills,
    map_kill_heatmap.total_deaths,
    (map_kill_heatmap.total_kills + map_kill_heatmap.total_deaths) AS total_combat
   FROM public.map_kill_heatmap
  ORDER BY map_kill_heatmap.map_name, (map_kill_heatmap.total_kills + map_kill_heatmap.total_deaths) DESC;


--
-- Name: map_kill_heatmap_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.map_kill_heatmap_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: map_kill_heatmap_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.map_kill_heatmap_id_seq OWNED BY public.map_kill_heatmap.id;


--
-- Name: map_movement_heatmap; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_movement_heatmap (
    id integer NOT NULL,
    map_name character varying(64) NOT NULL,
    grid_x integer NOT NULL,
    grid_y integer NOT NULL,
    grid_size integer DEFAULT 512,
    traversal_count integer DEFAULT 0,
    combat_count integer DEFAULT 0,
    escape_count integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: map_movement_heatmap_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.map_movement_heatmap_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: map_movement_heatmap_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.map_movement_heatmap_id_seq OWNED BY public.map_movement_heatmap.id;


--
-- Name: map_performance; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.map_performance (
    id integer NOT NULL,
    player_guid text NOT NULL,
    map_name text NOT NULL,
    matches_played integer DEFAULT 0 NOT NULL,
    total_rounds integer DEFAULT 0 NOT NULL,
    wins integer DEFAULT 0 NOT NULL,
    losses integer DEFAULT 0 NOT NULL,
    win_rate real DEFAULT 0.0 NOT NULL,
    avg_kills real DEFAULT 0.0 NOT NULL,
    avg_deaths real DEFAULT 0.0 NOT NULL,
    avg_kd_ratio real DEFAULT 0.0 NOT NULL,
    avg_dpm real DEFAULT 0.0 NOT NULL,
    avg_efficiency real DEFAULT 0.0 NOT NULL,
    last_match_date text,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE map_performance; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.map_performance IS 'Player performance statistics per map for prediction engine (Phase 4)';


--
-- Name: COLUMN map_performance.win_rate; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.map_performance.win_rate IS 'Win rate on this map (0.0 to 1.0)';


--
-- Name: COLUMN map_performance.avg_dpm; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.map_performance.avg_dpm IS 'Average damage per minute on this map';


--
-- Name: map_performance_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.map_performance_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: map_performance_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.map_performance_id_seq OWNED BY public.map_performance.id;


--
-- Name: match_predictions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.match_predictions (
    id integer NOT NULL,
    prediction_time timestamp without time zone DEFAULT CURRENT_TIMESTAMP NOT NULL,
    session_date text NOT NULL,
    map_name text,
    format text NOT NULL,
    team_a_channel_id bigint NOT NULL,
    team_b_channel_id bigint NOT NULL,
    team_a_guids text NOT NULL,
    team_b_guids text NOT NULL,
    team_a_discord_ids text NOT NULL,
    team_b_discord_ids text NOT NULL,
    team_a_win_probability real NOT NULL,
    team_b_win_probability real NOT NULL,
    confidence text NOT NULL,
    confidence_score real NOT NULL,
    h2h_score real NOT NULL,
    form_score real NOT NULL,
    map_score real NOT NULL,
    subs_score real NOT NULL,
    weighted_score real NOT NULL,
    key_insight text NOT NULL,
    h2h_details text,
    form_details text,
    map_details text,
    subs_details text,
    actual_winner integer,
    team_a_actual_score integer,
    team_b_actual_score integer,
    prediction_correct boolean,
    prediction_accuracy real,
    discord_message_id bigint,
    discord_channel_id bigint,
    guid_coverage real NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    model_version text DEFAULT 'heuristic-v1'::text NOT NULL,
    publish_state text DEFAULT 'shadow'::text NOT NULL,
    prediction_event_key text,
    feature_snapshot jsonb,
    feature_coverage jsonb,
    eligibility_reasons text,
    gaming_session_id integer,
    brier_score real
);


--
-- Name: TABLE match_predictions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.match_predictions IS 'Stores automated match predictions from competitive analytics system (Phase 3-4)';


--
-- Name: COLUMN match_predictions.team_a_guids; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_predictions.team_a_guids IS 'JSON array of player GUIDs for Team A';


--
-- Name: COLUMN match_predictions.team_b_guids; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_predictions.team_b_guids IS 'JSON array of player GUIDs for Team B';


--
-- Name: COLUMN match_predictions.actual_winner; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_predictions.actual_winner IS '1 = Team A won, 2 = Team B won, 0 = draw/cancelled, NULL = not played yet';


--
-- Name: COLUMN match_predictions.prediction_correct; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_predictions.prediction_correct IS 'TRUE if predicted winner matches actual_winner';


--
-- Name: COLUMN match_predictions.prediction_accuracy; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.match_predictions.prediction_accuracy IS 'Calculated accuracy metric (Brier score or similar)';


--
-- Name: match_predictions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.match_predictions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: match_predictions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.match_predictions_id_seq OWNED BY public.match_predictions.id;


--
-- Name: matchup_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.matchup_history (
    id integer NOT NULL,
    matchup_id text NOT NULL,
    lineup_a_hash text NOT NULL,
    lineup_b_hash text NOT NULL,
    lineup_a_guids jsonb NOT NULL,
    lineup_b_guids jsonb NOT NULL,
    session_date text NOT NULL,
    gaming_session_id integer NOT NULL,
    winner_lineup_hash text,
    lineup_a_score integer DEFAULT 0,
    lineup_b_score integer DEFAULT 0,
    map_name text,
    player_stats jsonb,
    created_at timestamp without time zone DEFAULT now(),
    updated_at timestamp without time zone DEFAULT now()
);


--
-- Name: matchup_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.matchup_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: matchup_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.matchup_history_id_seq OWNED BY public.matchup_history.id;


--
-- Name: notifications_ledger; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.notifications_ledger (
    id bigint NOT NULL,
    user_id bigint NOT NULL,
    event_key text NOT NULL,
    channel_type text NOT NULL,
    sent_at timestamp without time zone,
    message_id text,
    error text,
    retries integer DEFAULT 0 NOT NULL,
    payload jsonb DEFAULT '{}'::jsonb NOT NULL,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT notifications_ledger_channel_type_check CHECK ((channel_type = ANY (ARRAY['discord'::text, 'telegram'::text, 'signal'::text])))
);


--
-- Name: notifications_ledger_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.notifications_ledger_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: notifications_ledger_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.notifications_ledger_id_seq OWNED BY public.notifications_ledger.id;


--
-- Name: permission_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.permission_audit_log (
    id integer NOT NULL,
    target_discord_id bigint NOT NULL,
    action character varying(50) NOT NULL,
    old_tier character varying(50),
    new_tier character varying(50),
    changed_by bigint NOT NULL,
    changed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    reason text,
    CONSTRAINT permission_audit_log_action_check CHECK (((action)::text = ANY ((ARRAY['add'::character varying, 'remove'::character varying, 'promote'::character varying, 'demote'::character varying])::text[])))
);


--
-- Name: permission_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.permission_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: permission_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.permission_audit_log_id_seq OWNED BY public.permission_audit_log.id;


--
-- Name: planning_sessions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.planning_sessions (
    id bigint NOT NULL,
    session_date date NOT NULL,
    created_by_user_id bigint NOT NULL,
    discord_thread_id text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: planning_sessions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.planning_sessions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: planning_sessions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.planning_sessions_id_seq OWNED BY public.planning_sessions.id;


--
-- Name: planning_team_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.planning_team_members (
    id bigint NOT NULL,
    session_id bigint NOT NULL,
    team_id bigint NOT NULL,
    user_id bigint NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: planning_team_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.planning_team_members_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: planning_team_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.planning_team_members_id_seq OWNED BY public.planning_team_members.id;


--
-- Name: planning_team_names; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.planning_team_names (
    id bigint NOT NULL,
    session_id bigint NOT NULL,
    suggested_by_user_id bigint NOT NULL,
    name text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: planning_team_names_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.planning_team_names_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: planning_team_names_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.planning_team_names_id_seq OWNED BY public.planning_team_names.id;


--
-- Name: planning_teams; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.planning_teams (
    id bigint NOT NULL,
    session_id bigint NOT NULL,
    side text NOT NULL,
    captain_user_id bigint,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT planning_teams_side_check CHECK ((side = ANY (ARRAY['A'::text, 'B'::text])))
);


--
-- Name: planning_teams_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.planning_teams_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: planning_teams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.planning_teams_id_seq OWNED BY public.planning_teams.id;


--
-- Name: planning_votes; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.planning_votes (
    id bigint NOT NULL,
    session_id bigint NOT NULL,
    user_id bigint NOT NULL,
    suggestion_id bigint NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: planning_votes_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.planning_votes_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: planning_votes_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.planning_votes_id_seq OWNED BY public.planning_votes.id;


--
-- Name: player_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.player_aliases (
    id integer NOT NULL,
    guid text NOT NULL,
    alias text NOT NULL,
    last_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    times_seen integer DEFAULT 1,
    first_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: player_aliases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.player_aliases_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: player_aliases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.player_aliases_id_seq OWNED BY public.player_aliases.id;


--
-- Name: player_comprehensive_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.player_comprehensive_stats (
    id integer NOT NULL,
    round_id integer NOT NULL,
    round_date text NOT NULL,
    map_name text NOT NULL,
    round_number integer NOT NULL,
    player_guid text NOT NULL,
    player_name text NOT NULL,
    clean_name text,
    team integer DEFAULT 0,
    kills integer DEFAULT 0,
    deaths integer DEFAULT 0,
    damage_given integer DEFAULT 0,
    damage_received integer DEFAULT 0,
    team_damage_given integer DEFAULT 0,
    team_damage_received integer DEFAULT 0,
    gibs integer DEFAULT 0,
    self_kills integer DEFAULT 0,
    team_kills integer DEFAULT 0,
    team_gibs integer DEFAULT 0,
    headshot_kills integer DEFAULT 0,
    headshots integer DEFAULT 0,
    time_played_seconds integer DEFAULT 0,
    time_played_minutes real DEFAULT 0,
    time_dead_minutes real DEFAULT 0,
    time_dead_ratio real DEFAULT 0,
    xp real DEFAULT 0,
    kd_ratio real DEFAULT 0,
    dpm real DEFAULT 0,
    efficiency real DEFAULT 0,
    bullets_fired integer DEFAULT 0,
    accuracy real DEFAULT 0,
    kill_assists integer DEFAULT 0,
    objectives_completed integer DEFAULT 0,
    objectives_destroyed integer DEFAULT 0,
    objectives_stolen integer DEFAULT 0,
    objectives_returned integer DEFAULT 0,
    dynamites_planted integer DEFAULT 0,
    dynamites_defused integer DEFAULT 0,
    times_revived integer DEFAULT 0,
    revives_given integer DEFAULT 0,
    most_useful_kills integer DEFAULT 0,
    useless_kills integer DEFAULT 0,
    kill_steals integer DEFAULT 0,
    denied_playtime integer DEFAULT 0,
    constructions integer DEFAULT 0,
    tank_meatshield integer DEFAULT 0,
    double_kills integer DEFAULT 0,
    triple_kills integer DEFAULT 0,
    quad_kills integer DEFAULT 0,
    multi_kills integer DEFAULT 0,
    mega_kills integer DEFAULT 0,
    killing_spree_best integer DEFAULT 0,
    death_spree_worst integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    time_dead_minutes_original double precision,
    full_selfkills integer DEFAULT 0,
    time_played_percent real DEFAULT 0
);


--
-- Name: COLUMN player_comprehensive_stats.full_selfkills; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.player_comprehensive_stats.full_selfkills IS 'Count of selfkills while at full health (from c0rnp0rn field 35).';


--
-- Name: player_comprehensive_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.player_comprehensive_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: player_comprehensive_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.player_comprehensive_stats_id_seq OWNED BY public.player_comprehensive_stats.id;


--
-- Name: player_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.player_links (
    id integer NOT NULL,
    player_guid text NOT NULL,
    discord_id bigint NOT NULL,
    discord_username text,
    player_name text,
    linked_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    display_name text,
    display_name_source text DEFAULT 'auto'::text,
    display_name_updated_at timestamp without time zone
);


--
-- Name: COLUMN player_links.display_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.player_links.display_name IS 'Custom display name chosen by player. NULL means use auto-resolution (most recent alias)';


--
-- Name: COLUMN player_links.display_name_source; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.player_links.display_name_source IS 'How display_name was set: auto (default), custom (user-chosen), alias (from player aliases)';


--
-- Name: COLUMN player_links.display_name_updated_at; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.player_links.display_name_updated_at IS 'Timestamp when display_name was last changed';


--
-- Name: player_links_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.player_links_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: player_links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.player_links_id_seq OWNED BY public.player_links.id;


--
-- Name: player_skill_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.player_skill_history (
    id integer NOT NULL,
    player_guid text NOT NULL,
    round_id integer,
    et_rating real NOT NULL,
    components jsonb DEFAULT '{}'::jsonb,
    calculated_at timestamp with time zone DEFAULT now(),
    session_date date,
    map_name text,
    rounds_in_scope integer DEFAULT 0,
    scope text DEFAULT 'global'::text
);


--
-- Name: player_skill_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.player_skill_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: player_skill_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.player_skill_history_id_seq OWNED BY public.player_skill_history.id;


--
-- Name: player_skill_ratings; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.player_skill_ratings (
    player_guid text NOT NULL,
    display_name text,
    et_rating real DEFAULT 0 NOT NULL,
    rating_class text DEFAULT 'unknown'::text,
    games_rated integer DEFAULT 0,
    last_rated_at timestamp with time zone DEFAULT now(),
    components jsonb DEFAULT '{}'::jsonb
);


--
-- Name: player_teamplay_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.player_teamplay_stats (
    id integer NOT NULL,
    player_guid character varying(32) NOT NULL,
    player_name character varying(64) NOT NULL,
    crossfire_participations integer DEFAULT 0,
    crossfire_kills integer DEFAULT 0,
    crossfire_damage integer DEFAULT 0,
    crossfire_final_blows integer DEFAULT 0,
    avg_crossfire_delay_ms real,
    solo_kills integer DEFAULT 0,
    solo_engagements integer DEFAULT 0,
    times_targeted integer DEFAULT 0,
    times_focused integer DEFAULT 0,
    focus_escapes integer DEFAULT 0,
    focus_deaths integer DEFAULT 0,
    solo_escapes integer DEFAULT 0,
    solo_deaths integer DEFAULT 0,
    avg_escape_distance real,
    avg_engagement_duration_ms real,
    total_damage_taken integer DEFAULT 0,
    total_damage_dealt_crossfire integer DEFAULT 0,
    first_seen timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_updated timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    player_guid_canonical character varying(32)
);


--
-- Name: player_teamplay_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.player_teamplay_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: player_teamplay_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.player_teamplay_stats_id_seq OWNED BY public.player_teamplay_stats.id;


--
-- Name: player_track; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.player_track (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    map_name character varying(64) NOT NULL,
    player_guid character varying(32) NOT NULL,
    player_name character varying(64) NOT NULL,
    team character varying(10) NOT NULL,
    player_class character varying(16) NOT NULL,
    spawn_time_ms integer NOT NULL,
    death_time_ms integer,
    duration_ms integer,
    first_move_time_ms integer,
    time_to_first_move_ms integer,
    sample_count integer NOT NULL,
    path jsonb DEFAULT '[]'::jsonb NOT NULL,
    total_distance real,
    avg_speed real,
    sprint_percentage real,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone,
    peak_speed real,
    stance_standing_sec real,
    stance_crouching_sec real,
    stance_prone_sec real,
    sprint_sec real,
    post_spawn_distance real
);


--
-- Name: player_track_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.player_track_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: player_track_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.player_track_id_seq OWNED BY public.player_track.id;


--
-- Name: poll_reminder_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.poll_reminder_preferences (
    discord_user_id bigint NOT NULL,
    discord_username text,
    threshold_notify boolean DEFAULT true,
    game_time_notify boolean DEFAULT true,
    notify_method text DEFAULT 'dm'::text,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT poll_reminder_preferences_notify_method_check CHECK ((notify_method = ANY (ARRAY['dm'::text, 'channel'::text, 'none'::text])))
);


--
-- Name: poll_responses; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.poll_responses (
    id integer NOT NULL,
    poll_id integer NOT NULL,
    discord_user_id bigint NOT NULL,
    discord_username text,
    response_type text NOT NULL,
    responded_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT poll_responses_response_type_check CHECK ((response_type = ANY (ARRAY['yes'::text, 'no'::text, 'tentative'::text])))
);


--
-- Name: poll_responses_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.poll_responses_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: poll_responses_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.poll_responses_id_seq OWNED BY public.poll_responses.id;


--
-- Name: processed_endstats_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.processed_endstats_files (
    id integer NOT NULL,
    filename text NOT NULL,
    round_id integer,
    success boolean DEFAULT true,
    error_message text,
    processed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: processed_endstats_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.processed_endstats_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: processed_endstats_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.processed_endstats_files_id_seq OWNED BY public.processed_endstats_files.id;


--
-- Name: processed_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.processed_files (
    id integer NOT NULL,
    filename text NOT NULL,
    file_hash text,
    success boolean DEFAULT true,
    error_message text,
    processed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: processed_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.processed_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: processed_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.processed_files_id_seq OWNED BY public.processed_files.id;


--
-- Name: proximity_carrier_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_carrier_event (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    carrier_guid character varying(32) NOT NULL,
    carrier_name character varying(64) NOT NULL,
    carrier_team character varying(10) NOT NULL,
    flag_team character varying(16) NOT NULL,
    pickup_time integer NOT NULL,
    drop_time integer NOT NULL,
    duration_ms integer NOT NULL,
    outcome character varying(16) NOT NULL,
    carry_distance real DEFAULT 0 NOT NULL,
    beeline_distance real DEFAULT 0 NOT NULL,
    efficiency real DEFAULT 0 NOT NULL,
    path_samples integer DEFAULT 0 NOT NULL,
    pickup_x integer DEFAULT 0,
    pickup_y integer DEFAULT 0,
    pickup_z integer DEFAULT 0,
    drop_x integer DEFAULT 0,
    drop_y integer DEFAULT 0,
    drop_z integer DEFAULT 0,
    killer_guid character varying(32) DEFAULT ''::character varying,
    killer_name character varying(64) DEFAULT ''::character varying,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_carrier_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_carrier_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_carrier_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_carrier_event_id_seq OWNED BY public.proximity_carrier_event.id;


--
-- Name: proximity_carrier_kill; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_carrier_kill (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    kill_time integer NOT NULL,
    carrier_guid character varying(32) NOT NULL,
    carrier_name character varying(64) NOT NULL,
    carrier_team character varying(10) NOT NULL,
    killer_guid character varying(32) NOT NULL,
    killer_name character varying(64) NOT NULL,
    killer_team character varying(10) NOT NULL,
    means_of_death integer DEFAULT 0 NOT NULL,
    carrier_distance_at_kill real DEFAULT 0 NOT NULL,
    flag_team character varying(16) NOT NULL,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_carrier_kill_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_carrier_kill_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_carrier_kill_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_carrier_kill_id_seq OWNED BY public.proximity_carrier_kill.id;


--
-- Name: proximity_carrier_return; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_carrier_return (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    return_time integer NOT NULL,
    returner_guid character varying(32) NOT NULL,
    returner_name character varying(64) NOT NULL,
    returner_team character varying(10) NOT NULL,
    flag_team character varying(16) NOT NULL,
    original_carrier_guid character varying(32) DEFAULT ''::character varying,
    drop_time integer NOT NULL,
    return_delay_ms integer DEFAULT 0 NOT NULL,
    drop_x integer DEFAULT 0,
    drop_y integer DEFAULT 0,
    drop_z integer DEFAULT 0,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_carrier_return_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_carrier_return_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_carrier_return_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_carrier_return_id_seq OWNED BY public.proximity_carrier_return.id;


--
-- Name: proximity_combat_position; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_combat_position (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    event_time integer NOT NULL,
    event_type character varying(16) DEFAULT 'kill'::character varying NOT NULL,
    attacker_guid character varying(32) NOT NULL,
    attacker_name character varying(64),
    attacker_team character varying(10),
    attacker_class character varying(16),
    victim_guid character varying(32) NOT NULL,
    victim_name character varying(64),
    victim_team character varying(10),
    victim_class character varying(16),
    attacker_x integer NOT NULL,
    attacker_y integer NOT NULL,
    attacker_z integer NOT NULL,
    victim_x integer NOT NULL,
    victim_y integer NOT NULL,
    victim_z integer NOT NULL,
    weapon_id integer NOT NULL,
    means_of_death integer NOT NULL,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    killer_health integer DEFAULT 0,
    axis_alive integer DEFAULT 0,
    allies_alive integer DEFAULT 0,
    attacker_guid_canonical character varying(32)
);


--
-- Name: proximity_shot_fired; Type: TABLE; Schema: public; Owner: -
-- v9 true-aim (Lua 6.02 SHOT_FIRED). Created by migrations/055; DEFAULT-OFF
-- in Lua, so empty until the feature is enabled+deployed. Self-contained
-- block (table + sequence + PK + indexes) — mirrors migration 055 exactly.
--

CREATE TABLE IF NOT EXISTS public.proximity_shot_fired (
    id                  integer NOT NULL,
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

CREATE SEQUENCE IF NOT EXISTS public.proximity_shot_fired_id_seq
    AS integer START WITH 1 INCREMENT BY 1 NO MINVALUE NO MAXVALUE CACHE 1;
ALTER SEQUENCE public.proximity_shot_fired_id_seq OWNED BY public.proximity_shot_fired.id;
ALTER TABLE ONLY public.proximity_shot_fired
    ALTER COLUMN id SET DEFAULT nextval('public.proximity_shot_fired_id_seq'::regclass);
DO $$ BEGIN
    ALTER TABLE ONLY public.proximity_shot_fired
        ADD CONSTRAINT proximity_shot_fired_pkey PRIMARY KEY (id);
EXCEPTION WHEN duplicate_table OR duplicate_object THEN NULL; END $$;

CREATE UNIQUE INDEX IF NOT EXISTS uq_psf_identity
    ON public.proximity_shot_fired
    (session_date, round_number, round_start_unix, event_time, guid, weapon_id);
CREATE INDEX IF NOT EXISTS idx_psf_guid_map_date
    ON public.proximity_shot_fired (guid, map_name, session_date);
CREATE INDEX IF NOT EXISTS idx_psf_canonical
    ON public.proximity_shot_fired (guid_canonical);
CREATE INDEX IF NOT EXISTS idx_psf_map_date
    ON public.proximity_shot_fired (map_name, session_date);


--
-- Name: proximity v7 draft tables (Lua 6.10, dormant); Type: TABLE; Schema: public; Owner: -
-- Mirrors migrations/058_add_proximity_v7_tables.sql — empty until the
-- corresponding Lua feature flags are enabled (owner-gated deploy).
--

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


--
-- Name: proximity_combat_position_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_combat_position_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_combat_position_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_combat_position_id_seq OWNED BY public.proximity_combat_position.id;


--
-- Name: proximity_construction_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_construction_event (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    event_time integer NOT NULL,
    event_type character varying(32) NOT NULL,
    player_guid character varying(32) NOT NULL,
    player_name character varying(64) NOT NULL,
    player_team character varying(10) NOT NULL,
    track_name character varying(64) DEFAULT ''::character varying,
    player_x integer DEFAULT 0,
    player_y integer DEFAULT 0,
    player_z integer DEFAULT 0,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_construction_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_construction_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_construction_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_construction_event_id_seq OWNED BY public.proximity_construction_event.id;


--
-- Name: proximity_crossfire_opportunity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_crossfire_opportunity (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    event_time integer NOT NULL,
    target_guid character varying(32) NOT NULL,
    target_name character varying(64) NOT NULL,
    target_team character varying(10) NOT NULL,
    teammate1_guid character varying(32) NOT NULL,
    teammate2_guid character varying(32) NOT NULL,
    angular_separation real NOT NULL,
    was_executed boolean DEFAULT false NOT NULL,
    damage_within_window integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone
);


--
-- Name: proximity_crossfire_opportunity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_crossfire_opportunity_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_crossfire_opportunity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_crossfire_opportunity_id_seq OWNED BY public.proximity_crossfire_opportunity.id;


--
-- Name: proximity_escort_credit; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_escort_credit (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    player_guid character varying(32) NOT NULL,
    player_name character varying(64) NOT NULL,
    player_team character varying(10) NOT NULL,
    vehicle_name character varying(64) NOT NULL,
    mounted_time_ms integer DEFAULT 0,
    proximity_time_ms integer DEFAULT 0,
    total_escort_distance real DEFAULT 0,
    credit_distance real DEFAULT 0,
    samples integer DEFAULT 0,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_escort_credit_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_escort_credit_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_escort_credit_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_escort_credit_id_seq OWNED BY public.proximity_escort_credit.id;


--
-- Name: proximity_focus_fire; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_focus_fire (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    engagement_id integer NOT NULL,
    target_guid character varying(32) NOT NULL,
    target_name character varying(64) NOT NULL,
    attacker_count integer NOT NULL,
    attacker_guids text NOT NULL,
    total_damage integer NOT NULL,
    duration integer NOT NULL,
    focus_score real NOT NULL,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_focus_fire_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_focus_fire_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_focus_fire_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_focus_fire_id_seq OWNED BY public.proximity_focus_fire.id;


--
-- Name: proximity_hit_region; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_hit_region (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    event_time integer NOT NULL,
    attacker_guid character varying(32) NOT NULL,
    attacker_name character varying(64) NOT NULL,
    victim_guid character varying(32) NOT NULL,
    victim_name character varying(64) NOT NULL,
    weapon_id integer NOT NULL,
    hit_region integer NOT NULL,
    damage integer NOT NULL,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_hit_region_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_hit_region_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_hit_region_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_hit_region_id_seq OWNED BY public.proximity_hit_region.id;


--
-- Name: proximity_hit_region_summary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_hit_region_summary (
    id integer NOT NULL,
    player_guid character varying(32) NOT NULL,
    player_name character varying(64),
    weapon_id integer NOT NULL,
    head_hits integer DEFAULT 0,
    arms_hits integer DEFAULT 0,
    body_hits integer DEFAULT 0,
    legs_hits integer DEFAULT 0,
    head_damage integer DEFAULT 0,
    arms_damage integer DEFAULT 0,
    body_damage integer DEFAULT 0,
    legs_damage integer DEFAULT 0,
    total_hits integer DEFAULT 0,
    total_damage integer DEFAULT 0,
    headshot_pct real GENERATED ALWAYS AS (
CASE
    WHEN (total_hits > 0) THEN (((head_hits)::real / (total_hits)::double precision) * (100)::double precision)
    ELSE (0)::double precision
END) STORED,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_hit_region_summary_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_hit_region_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_hit_region_summary_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_hit_region_summary_id_seq OWNED BY public.proximity_hit_region_summary.id;


--
-- Name: proximity_kill_outcome; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_kill_outcome (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    kill_time integer NOT NULL,
    victim_guid character varying(32) NOT NULL,
    victim_name character varying(64) NOT NULL,
    killer_guid character varying(32) NOT NULL,
    killer_name character varying(64),
    kill_mod integer DEFAULT 0,
    outcome character varying(16) NOT NULL,
    outcome_time integer NOT NULL,
    delta_ms integer NOT NULL,
    effective_denied_ms integer NOT NULL,
    gibber_guid character varying(32) DEFAULT ''::character varying,
    gibber_name character varying(64) DEFAULT ''::character varying,
    reviver_guid character varying(32) DEFAULT ''::character varying,
    reviver_name character varying(64) DEFAULT ''::character varying,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    killer_guid_canonical character varying(32)
);


--
-- Name: proximity_kill_outcome_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_kill_outcome_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_kill_outcome_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_kill_outcome_id_seq OWNED BY public.proximity_kill_outcome.id;


--
-- Name: proximity_lua_trade_kill; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_lua_trade_kill (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    original_kill_time integer NOT NULL,
    traded_kill_time integer NOT NULL,
    delta_ms integer NOT NULL,
    original_victim_guid character varying(32) NOT NULL,
    original_victim_name character varying(64) NOT NULL,
    original_killer_guid character varying(32) NOT NULL,
    original_killer_name character varying(64) NOT NULL,
    trader_guid character varying(32) NOT NULL,
    trader_name character varying(64) NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone,
    trader_guid_canonical character varying(32)
);


--
-- Name: proximity_lua_trade_kill_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_lua_trade_kill_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_lua_trade_kill_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_lua_trade_kill_id_seq OWNED BY public.proximity_lua_trade_kill.id;


--
-- Name: proximity_objective_focus; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_objective_focus (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    map_name character varying(64) NOT NULL,
    player_guid character varying(32) NOT NULL,
    player_name character varying(64) NOT NULL,
    team character varying(10) NOT NULL,
    objective character varying(64),
    avg_distance real,
    time_within_radius_ms integer,
    samples integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone
);


--
-- Name: proximity_objective_focus_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_objective_focus_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_objective_focus_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_objective_focus_id_seq OWNED BY public.proximity_objective_focus.id;


--
-- Name: proximity_objective_run; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_objective_run (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    engineer_guid character varying(32) NOT NULL,
    engineer_name character varying(64) DEFAULT ''::character varying NOT NULL,
    engineer_team character varying(10) DEFAULT ''::character varying NOT NULL,
    action_type character varying(32) NOT NULL,
    track_name character varying(64) DEFAULT ''::character varying NOT NULL,
    action_time integer NOT NULL,
    approach_time_ms integer DEFAULT 0,
    approach_distance real DEFAULT 0,
    beeline_distance real DEFAULT 0,
    path_efficiency real DEFAULT 0,
    self_kills integer DEFAULT 0,
    team_kills integer DEFAULT 0,
    escort_guids text DEFAULT ''::text,
    enemies_nearby integer DEFAULT 0,
    nearby_teammates integer DEFAULT 0,
    run_type character varying(32) DEFAULT 'unknown'::character varying NOT NULL,
    obj_x integer DEFAULT 0,
    obj_y integer DEFAULT 0,
    obj_z integer DEFAULT 0,
    killer_guid character varying(32) DEFAULT ''::character varying,
    killer_name character varying(64) DEFAULT ''::character varying,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_objective_run_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_objective_run_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_objective_run_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_objective_run_id_seq OWNED BY public.proximity_objective_run.id;


--
-- Name: proximity_processed_files; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_processed_files (
    id integer NOT NULL,
    filename text NOT NULL,
    file_hash text,
    aggregates_applied boolean DEFAULT false,
    imported_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_processed_files_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_processed_files_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_processed_files_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_processed_files_id_seq OWNED BY public.proximity_processed_files.id;


--
-- Name: proximity_reaction_metric; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_reaction_metric (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    engagement_id integer NOT NULL,
    target_guid character varying(32) NOT NULL,
    target_name character varying(64) NOT NULL,
    target_team character varying(10) NOT NULL,
    target_class character varying(16) NOT NULL,
    outcome character varying(20) NOT NULL,
    num_attackers integer DEFAULT 0 NOT NULL,
    return_fire_ms integer,
    dodge_reaction_ms integer,
    support_reaction_ms integer,
    start_time_ms integer DEFAULT 0 NOT NULL,
    end_time_ms integer DEFAULT 0 NOT NULL,
    duration_ms integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone
);


--
-- Name: proximity_reaction_metric_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_reaction_metric_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_reaction_metric_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_reaction_metric_id_seq OWNED BY public.proximity_reaction_metric.id;


--
-- Name: proximity_revive; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_revive (
    id integer NOT NULL,
    round_id integer,
    map_name text,
    medic_guid text,
    medic_name text,
    revived_guid text NOT NULL,
    revived_name text,
    revive_time integer,
    revive_x real,
    revive_y real,
    revive_z real,
    distance_to_enemy real,
    under_fire boolean DEFAULT false,
    nearest_enemy_guid text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    session_date date
);


--
-- Name: proximity_revive_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_revive_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_revive_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_revive_id_seq OWNED BY public.proximity_revive.id;


--
-- Name: proximity_spawn_timing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_spawn_timing (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    killer_guid character varying(32) NOT NULL,
    killer_name character varying(64) NOT NULL,
    killer_team character varying(10) NOT NULL,
    victim_guid character varying(32) NOT NULL,
    victim_name character varying(64) NOT NULL,
    victim_team character varying(10) NOT NULL,
    kill_time integer NOT NULL,
    enemy_spawn_interval integer NOT NULL,
    time_to_next_spawn integer NOT NULL,
    spawn_timing_score real NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone,
    killer_reinf real DEFAULT 0,
    victim_reinf real DEFAULT 0,
    killer_guid_canonical character varying(32)
);


--
-- Name: proximity_spawn_timing_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_spawn_timing_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_spawn_timing_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_spawn_timing_id_seq OWNED BY public.proximity_spawn_timing.id;


--
-- Name: proximity_support_summary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_support_summary (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    support_samples integer DEFAULT 0 NOT NULL,
    total_samples integer DEFAULT 0 NOT NULL,
    support_uptime_pct real,
    computed_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone
);


--
-- Name: proximity_support_summary_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_support_summary_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_support_summary_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_support_summary_id_seq OWNED BY public.proximity_support_summary.id;


--
-- Name: proximity_team_cohesion; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_team_cohesion (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    sample_time integer NOT NULL,
    team character varying(10) NOT NULL,
    alive_count integer NOT NULL,
    centroid_x real NOT NULL,
    centroid_y real NOT NULL,
    dispersion real NOT NULL,
    max_spread real NOT NULL,
    straggler_count integer NOT NULL,
    buddy_pair_guids character varying(128),
    buddy_distance real,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone
);


--
-- Name: proximity_team_cohesion_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_team_cohesion_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_team_cohesion_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_team_cohesion_id_seq OWNED BY public.proximity_team_cohesion.id;


--
-- Name: proximity_team_push; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_team_push (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    start_time integer NOT NULL,
    end_time integer NOT NULL,
    team character varying(10) NOT NULL,
    avg_speed real NOT NULL,
    direction_x real NOT NULL,
    direction_y real NOT NULL,
    alignment_score real NOT NULL,
    push_quality real NOT NULL,
    participant_count integer NOT NULL,
    toward_objective character varying(64),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone
);


--
-- Name: proximity_team_push_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_team_push_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_team_push_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_team_push_id_seq OWNED BY public.proximity_team_push.id;


--
-- Name: proximity_trade_event; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_trade_event (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    victim_guid character varying(32) NOT NULL,
    victim_name character varying(64) NOT NULL,
    victim_team character varying(10) NOT NULL,
    killer_guid character varying(32),
    killer_name character varying(64),
    death_time_ms integer NOT NULL,
    trade_window_ms integer NOT NULL,
    opportunity_count integer DEFAULT 0,
    opportunities jsonb DEFAULT '[]'::jsonb NOT NULL,
    attempt_count integer DEFAULT 0,
    attempts jsonb DEFAULT '[]'::jsonb NOT NULL,
    success_count integer DEFAULT 0,
    successes jsonb DEFAULT '[]'::jsonb NOT NULL,
    missed_count integer DEFAULT 0,
    missed_candidates jsonb DEFAULT '[]'::jsonb NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    nearest_teammate_dist real,
    is_isolation_death boolean DEFAULT false,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp with time zone
);


--
-- Name: proximity_trade_event_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_trade_event_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_trade_event_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_trade_event_id_seq OWNED BY public.proximity_trade_event.id;


--
-- Name: proximity_vehicle_progress; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_vehicle_progress (
    id integer NOT NULL,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    round_end_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    vehicle_name character varying(64) NOT NULL,
    vehicle_type character varying(32) DEFAULT 'script_mover'::character varying NOT NULL,
    start_x integer DEFAULT 0,
    start_y integer DEFAULT 0,
    start_z integer DEFAULT 0,
    end_x integer DEFAULT 0,
    end_y integer DEFAULT 0,
    end_z integer DEFAULT 0,
    total_distance real DEFAULT 0 NOT NULL,
    max_health integer DEFAULT 0,
    final_health integer DEFAULT 0,
    destroyed_count integer DEFAULT 0,
    round_id integer,
    round_link_source character varying(32),
    round_link_reason character varying(64),
    round_linked_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: proximity_vehicle_progress_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_vehicle_progress_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_vehicle_progress_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_vehicle_progress_id_seq OWNED BY public.proximity_vehicle_progress.id;


--
-- Name: proximity_weapon_accuracy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.proximity_weapon_accuracy (
    id integer NOT NULL,
    round_id integer,
    map_name text,
    player_guid text NOT NULL,
    player_name text,
    team text,
    weapon_id integer NOT NULL,
    shots_fired integer DEFAULT 0,
    hits integer DEFAULT 0,
    kills integer DEFAULT 0,
    headshots integer DEFAULT 0,
    accuracy_pct real GENERATED ALWAYS AS (
CASE
    WHEN (shots_fired > 0) THEN (((hits)::real / (shots_fired)::double precision) * (100)::double precision)
    ELSE (0)::double precision
END) STORED,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    session_date date
);


--
-- Name: proximity_weapon_accuracy_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.proximity_weapon_accuracy_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proximity_weapon_accuracy_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.proximity_weapon_accuracy_id_seq OWNED BY public.proximity_weapon_accuracy.id;


--
-- Name: round_assemblies; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.round_assemblies (
    id integer NOT NULL,
    assembly_key character varying(128) NOT NULL,
    gaming_session_id integer NOT NULL,
    map_name character varying(64) NOT NULL,
    map_play_seq integer NOT NULL,
    r1_round_id integer,
    r2_round_id integer,
    summary_round_id integer,
    r1_lua_teams_id integer,
    r2_lua_teams_id integer,
    has_r1_stats boolean DEFAULT false,
    has_r2_stats boolean DEFAULT false,
    has_r1_lua_teams boolean DEFAULT false,
    has_r2_lua_teams boolean DEFAULT false,
    has_r1_gametime boolean DEFAULT false,
    has_r2_gametime boolean DEFAULT false,
    has_r1_endstats boolean DEFAULT false,
    has_r2_endstats boolean DEFAULT false,
    orphan_r2 boolean DEFAULT false,
    status character varying(20) DEFAULT 'pending'::character varying,
    completeness_pct integer DEFAULT 0,
    completed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: round_assemblies_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.round_assemblies_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: round_assemblies_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.round_assemblies_id_seq OWNED BY public.round_assemblies.id;


--
-- Name: round_assembly_events; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.round_assembly_events (
    id integer NOT NULL,
    event_key character varying(160) NOT NULL,
    source_type character varying(32) NOT NULL,
    match_id character varying(128),
    gaming_session_id integer,
    map_name character varying(64) NOT NULL,
    round_number integer NOT NULL,
    round_id integer,
    lua_teams_id integer,
    event_unix bigint,
    event_at timestamp without time zone,
    attachment_status character varying(20) DEFAULT 'pending'::character varying,
    assembly_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    attached_at timestamp without time zone
);


--
-- Name: round_assembly_events_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.round_assembly_events_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: round_assembly_events_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.round_assembly_events_id_seq OWNED BY public.round_assembly_events.id;


--
-- Name: round_awards; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.round_awards (
    id integer NOT NULL,
    round_id integer NOT NULL,
    round_date text NOT NULL,
    map_name text NOT NULL,
    round_number integer NOT NULL,
    award_name text NOT NULL,
    player_name text NOT NULL,
    player_guid text,
    award_value text NOT NULL,
    award_value_numeric real,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: round_awards_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.round_awards_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: round_awards_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.round_awards_id_seq OWNED BY public.round_awards.id;


--
-- Name: round_correlations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.round_correlations (
    id integer NOT NULL,
    correlation_id character varying(64) NOT NULL,
    match_id character varying(128) NOT NULL,
    map_name character varying(64) NOT NULL,
    r1_round_id integer,
    r2_round_id integer,
    summary_round_id integer,
    r1_lua_teams_id integer,
    r2_lua_teams_id integer,
    has_r1_stats boolean DEFAULT false,
    has_r2_stats boolean DEFAULT false,
    has_r1_lua_teams boolean DEFAULT false,
    has_r2_lua_teams boolean DEFAULT false,
    has_r1_gametime boolean DEFAULT false,
    has_r2_gametime boolean DEFAULT false,
    has_r1_endstats boolean DEFAULT false,
    has_r2_endstats boolean DEFAULT false,
    status character varying(20) DEFAULT 'pending'::character varying,
    completeness_pct integer DEFAULT 0,
    r1_arrived_at timestamp without time zone,
    r2_arrived_at timestamp without time zone,
    completed_at timestamp without time zone,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    has_r1_proximity boolean DEFAULT false,
    has_r2_proximity boolean DEFAULT false
);


--
-- Name: round_correlations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.round_correlations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: round_correlations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.round_correlations_id_seq OWNED BY public.round_correlations.id;


--
-- Name: round_vs_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.round_vs_stats (
    id integer NOT NULL,
    round_id integer NOT NULL,
    round_date text NOT NULL,
    map_name text NOT NULL,
    round_number integer NOT NULL,
    player_name text NOT NULL,
    player_guid text,
    kills integer DEFAULT 0 NOT NULL,
    deaths integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    subject_name text,
    subject_guid text
);


--
-- Name: round_vs_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.round_vs_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: round_vs_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.round_vs_stats_id_seq OWNED BY public.round_vs_stats.id;


--
-- Name: rounds; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.rounds (
    id integer NOT NULL,
    match_id text,
    round_number integer,
    round_date text,
    round_time text,
    map_name text,
    time_limit text,
    actual_time text,
    defender_team integer DEFAULT 0,
    winner_team integer DEFAULT 0,
    is_tied boolean DEFAULT false,
    round_outcome text,
    gaming_session_id integer,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    round_status character varying(20) DEFAULT 'completed'::character varying,
    round_start_unix bigint,
    round_end_unix bigint,
    actual_duration_seconds integer,
    total_pause_seconds integer DEFAULT 0,
    pause_count integer DEFAULT 0,
    end_reason character varying(20),
    is_bot_round boolean DEFAULT false,
    bot_player_count integer DEFAULT 0,
    human_player_count integer DEFAULT 0,
    score_confidence character varying(32),
    round_stopwatch_state character varying(16),
    time_to_beat_seconds integer,
    next_timelimit_minutes integer,
    map_play_seq integer,
    round_canonical_id character varying(64)
);


--
-- Name: COLUMN rounds.round_status; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rounds.round_status IS 'Round status: completed (normal), cancelled (restarted), substitution (roster changed), warmup (practice)';


--
-- Name: COLUMN rounds.score_confidence; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rounds.score_confidence IS 'WS0 confidence state: verified_header|time_fallback|ambiguous|missing';


--
-- Name: COLUMN rounds.round_stopwatch_state; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rounds.round_stopwatch_state IS 'WS0 stopwatch state: FULL_HOLD|TIME_SET';


--
-- Name: COLUMN rounds.time_to_beat_seconds; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rounds.time_to_beat_seconds IS 'WS0 stopwatch contract value for R1 TIME_SET rounds';


--
-- Name: COLUMN rounds.next_timelimit_minutes; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rounds.next_timelimit_minutes IS 'WS0 computed next timelimit for stopwatch rounds';


--
-- Name: COLUMN rounds.round_canonical_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.rounds.round_canonical_id IS 'SHA256(round_start_unix:map_name:round_number)[:16] — content-addressed stable id. See docs/ADR_round_canonical_id.md';


--
-- Name: rounds_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.rounds_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: rounds_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.rounds_id_seq OWNED BY public.rounds.id;


--
-- Name: schema_migrations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.schema_migrations (
    id integer NOT NULL,
    version text NOT NULL,
    filename text NOT NULL,
    checksum text,
    applied_at timestamp with time zone DEFAULT now() NOT NULL,
    applied_by text DEFAULT 'manual'::text,
    execution_ms integer,
    success boolean DEFAULT true NOT NULL
);


--
-- Name: schema_migrations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.schema_migrations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: schema_migrations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.schema_migrations_id_seq OWNED BY public.schema_migrations.id;


--
-- Name: server_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.server_status_history (
    id integer NOT NULL,
    recorded_at timestamp with time zone DEFAULT now(),
    player_count integer DEFAULT 0 NOT NULL,
    max_players integer DEFAULT 16 NOT NULL,
    map_name character varying(64),
    hostname character varying(128),
    players jsonb DEFAULT '[]'::jsonb,
    ping_ms integer,
    online boolean DEFAULT true
);


--
-- Name: TABLE server_status_history; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.server_status_history IS 'Server status snapshots for activity monitoring';


--
-- Name: server_status_history_backup_20260207; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.server_status_history_backup_20260207 (
    id integer,
    recorded_at timestamp with time zone,
    player_count integer,
    max_players integer,
    map_name character varying(64),
    hostname character varying(128),
    players jsonb,
    ping_ms integer,
    online boolean
);


--
-- Name: server_status_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.server_status_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: server_status_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.server_status_history_id_seq OWNED BY public.server_status_history.id;


--
-- Name: session_engagement_summary; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.session_engagement_summary AS
 SELECT combat_engagement.session_date,
    combat_engagement.map_name,
    count(*) AS total_engagements,
    sum(
        CASE
            WHEN ((combat_engagement.outcome)::text = 'killed'::text) THEN 1
            ELSE 0
        END) AS kills,
    sum(
        CASE
            WHEN ((combat_engagement.outcome)::text = 'escaped'::text) THEN 1
            ELSE 0
        END) AS escapes,
    sum(
        CASE
            WHEN combat_engagement.is_crossfire THEN 1
            ELSE 0
        END) AS crossfire_engagements,
    round(avg(combat_engagement.duration_ms), 0) AS avg_duration_ms,
    round(avg(combat_engagement.num_attackers), 2) AS avg_attackers
   FROM public.combat_engagement
  GROUP BY combat_engagement.session_date, combat_engagement.map_name
  ORDER BY combat_engagement.session_date DESC;


--
-- Name: session_results; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.session_results (
    id integer NOT NULL,
    session_date text NOT NULL,
    map_name text NOT NULL,
    gaming_session_id integer,
    team_1_guids text NOT NULL,
    team_2_guids text NOT NULL,
    team_1_names text NOT NULL,
    team_2_names text NOT NULL,
    format text NOT NULL,
    total_rounds integer NOT NULL,
    team_1_score integer DEFAULT 0 NOT NULL,
    team_2_score integer DEFAULT 0 NOT NULL,
    winning_team integer NOT NULL,
    round_details text,
    round_numbers text NOT NULL,
    session_start timestamp without time zone NOT NULL,
    session_end timestamp without time zone,
    duration_minutes integer,
    team_1_total_kills integer DEFAULT 0,
    team_1_total_deaths integer DEFAULT 0,
    team_1_total_damage integer DEFAULT 0,
    team_2_total_kills integer DEFAULT 0,
    team_2_total_deaths integer DEFAULT 0,
    team_2_total_damage integer DEFAULT 0,
    had_substitutions boolean DEFAULT false,
    substitution_details text,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    team_1_name text,
    team_2_name text
);


--
-- Name: TABLE session_results; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.session_results IS 'Aggregated match results for competitive analytics and prediction accuracy tracking (Phase 4)';


--
-- Name: COLUMN session_results.team_1_guids; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.session_results.team_1_guids IS 'JSON array of player GUIDs for Team 1';


--
-- Name: COLUMN session_results.team_2_guids; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.session_results.team_2_guids IS 'JSON array of player GUIDs for Team 2';


--
-- Name: COLUMN session_results.winning_team; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.session_results.winning_team IS '1 = Team 1 won, 2 = Team 2 won, 0 = draw';


--
-- Name: COLUMN session_results.round_details; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.session_results.round_details IS 'JSON array with round-by-round results including winner, time, scores';


--
-- Name: COLUMN session_results.had_substitutions; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.session_results.had_substitutions IS 'TRUE if players joined/left mid-session';


--
-- Name: COLUMN session_results.team_1_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.session_results.team_1_name IS 'Team name from pool (e.g., sWat, madDogz)';


--
-- Name: COLUMN session_results.team_2_name; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.session_results.team_2_name IS 'Team name from pool (e.g., sWat, madDogz)';


--
-- Name: session_results_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.session_results_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: session_results_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.session_results_id_seq OWNED BY public.session_results.id;


--
-- Name: session_round_scores; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.session_round_scores (
    id integer NOT NULL,
    gaming_session_id integer NOT NULL,
    round_number integer NOT NULL,
    map_name character varying(64) NOT NULL,
    round_date date,
    round_stopwatch_state character varying(16),
    actual_time_seconds integer,
    time_to_beat_seconds integer,
    team_a_name character varying(64),
    team_b_name character varying(64),
    team_a_round_points integer DEFAULT 0,
    team_b_round_points integer DEFAULT 0,
    round_winner character varying(64),
    team_a_map_points integer DEFAULT 0,
    team_b_map_points integer DEFAULT 0,
    map_winner character varying(64),
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: session_round_scores_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.session_round_scores_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: session_round_scores_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.session_round_scores_id_seq OWNED BY public.session_round_scores.id;


--
-- Name: session_teams; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.session_teams (
    id integer NOT NULL,
    session_start_date text NOT NULL,
    map_name text NOT NULL,
    team_name text NOT NULL,
    player_guids jsonb,
    player_names jsonb,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    color integer,
    gaming_session_id integer,
    session_identity text GENERATED ALWAYS AS (COALESCE((gaming_session_id)::text, session_start_date)) STORED
);


--
-- Name: COLUMN session_teams.color; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.session_teams.color IS 'Discord embed color for this team (from team_pool)';


--
-- Name: session_teams_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.session_teams_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: session_teams_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.session_teams_id_seq OWNED BY public.session_teams.id;


--
-- Name: storytelling_kill_impact; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.storytelling_kill_impact (
    id integer NOT NULL,
    kill_outcome_id integer,
    session_date date NOT NULL,
    round_number integer NOT NULL,
    round_start_unix integer DEFAULT 0,
    map_name character varying(64) NOT NULL,
    killer_guid character varying(32) NOT NULL,
    killer_name character varying(64) DEFAULT ''::character varying,
    victim_guid character varying(32) NOT NULL,
    victim_name character varying(64) DEFAULT ''::character varying,
    base_impact real DEFAULT 1.0 NOT NULL,
    carrier_multiplier real DEFAULT 1.0,
    push_multiplier real DEFAULT 1.0,
    crossfire_multiplier real DEFAULT 1.0,
    spawn_multiplier real DEFAULT 1.0,
    outcome_multiplier real DEFAULT 1.0,
    class_multiplier real DEFAULT 1.0,
    distance_multiplier real DEFAULT 1.0,
    total_impact real NOT NULL,
    is_carrier_kill boolean DEFAULT false,
    is_during_push boolean DEFAULT false,
    is_crossfire boolean DEFAULT false,
    is_objective_area boolean DEFAULT false,
    kill_time_ms integer DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    health_multiplier real DEFAULT 1.0,
    alive_multiplier real DEFAULT 1.0,
    reinf_multiplier real DEFAULT 1.0,
    killer_health integer DEFAULT 0,
    axis_alive integer DEFAULT 0,
    allies_alive integer DEFAULT 0,
    victim_reinf real DEFAULT 0,
    killer_guid_canonical character varying(32)
);


--
-- Name: storytelling_kill_impact_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.storytelling_kill_impact_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: storytelling_kill_impact_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.storytelling_kill_impact_id_seq OWNED BY public.storytelling_kill_impact.id;


--
-- Name: subscription_preferences; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.subscription_preferences (
    user_id bigint NOT NULL,
    allow_promotions boolean DEFAULT false NOT NULL,
    preferred_channel text DEFAULT 'any'::text NOT NULL,
    telegram_handle_encrypted text,
    signal_handle_encrypted text,
    quiet_hours jsonb DEFAULT '{}'::jsonb NOT NULL,
    timezone text DEFAULT 'Europe/Ljubljana'::text NOT NULL,
    notify_threshold integer DEFAULT 0 NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT subscription_preferences_preferred_channel_check CHECK ((preferred_channel = ANY (ARRAY['discord'::text, 'telegram'::text, 'signal'::text, 'any'::text])))
);


--
-- Name: team_pool; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.team_pool (
    id integer NOT NULL,
    name text NOT NULL,
    display_name text,
    color integer,
    active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: TABLE team_pool; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON TABLE public.team_pool IS 'Pool of team names for random session assignment';


--
-- Name: COLUMN team_pool.color; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_pool.color IS 'Discord embed color as integer (e.g., 0x3498DB = 3447003)';


--
-- Name: COLUMN team_pool.active; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON COLUMN public.team_pool.active IS 'FALSE to exclude from random pool without deleting';


--
-- Name: team_pool_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.team_pool_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: team_pool_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.team_pool_id_seq OWNED BY public.team_pool.id;


--
-- Name: teamplay_leaderboard; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.teamplay_leaderboard AS
 SELECT player_teamplay_stats.player_name,
    player_teamplay_stats.player_guid,
    player_teamplay_stats.crossfire_kills,
    player_teamplay_stats.crossfire_participations,
    round(((100.0 * (player_teamplay_stats.crossfire_kills)::numeric) / (NULLIF(player_teamplay_stats.crossfire_participations, 0))::numeric), 1) AS crossfire_kill_rate,
    round((player_teamplay_stats.avg_crossfire_delay_ms)::numeric, 0) AS avg_sync_ms,
    player_teamplay_stats.solo_kills,
    player_teamplay_stats.focus_escapes,
    player_teamplay_stats.times_focused,
    round(((100.0 * (player_teamplay_stats.focus_escapes)::numeric) / (NULLIF(player_teamplay_stats.times_focused, 0))::numeric), 1) AS focus_survival_rate
   FROM public.player_teamplay_stats
  WHERE (player_teamplay_stats.crossfire_participations > 0)
  ORDER BY player_teamplay_stats.crossfire_kills DESC;


--
-- Name: upload_tags; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.upload_tags (
    id integer NOT NULL,
    upload_id text NOT NULL,
    tag text NOT NULL
);


--
-- Name: upload_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.upload_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: upload_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.upload_tags_id_seq OWNED BY public.upload_tags.id;


--
-- Name: uploads; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.uploads (
    id text NOT NULL,
    uploader_discord_id bigint,
    uploader_name text DEFAULT 'Anonymous'::text NOT NULL,
    category text NOT NULL,
    title text NOT NULL,
    description text,
    original_filename text NOT NULL,
    stored_path text NOT NULL,
    extension text NOT NULL,
    file_size_bytes bigint NOT NULL,
    content_hash_sha256 text NOT NULL,
    mime_type text,
    download_count integer DEFAULT 0,
    status text DEFAULT 'active'::text NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT uploads_category_check CHECK ((category = ANY (ARRAY['config'::text, 'hud'::text, 'archive'::text, 'clip'::text]))),
    CONSTRAINT uploads_status_check CHECK ((status = ANY (ARRAY['active'::text, 'quarantined'::text, 'deleted'::text])))
);


--
-- Name: user_permissions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_permissions (
    id integer NOT NULL,
    discord_id bigint NOT NULL,
    username character varying(255),
    tier character varying(50) NOT NULL,
    added_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    added_by bigint,
    reason text,
    CONSTRAINT user_permissions_tier_check CHECK (((tier)::text = ANY ((ARRAY['root'::character varying, 'admin'::character varying, 'moderator'::character varying])::text[])))
);


--
-- Name: user_permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.user_permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: user_permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.user_permissions_id_seq OWNED BY public.user_permissions.id;


--
-- Name: user_player_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.user_player_links (
    user_id bigint NOT NULL,
    player_guid text NOT NULL,
    player_name text,
    linked_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: voice_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.voice_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: voice_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.voice_members_id_seq OWNED BY public.voice_members.id;


--
-- Name: voice_status_history; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voice_status_history (
    id integer NOT NULL,
    recorded_at timestamp with time zone DEFAULT now(),
    member_count integer DEFAULT 0 NOT NULL,
    channel_id bigint,
    channel_name character varying(255),
    members jsonb DEFAULT '[]'::jsonb,
    first_joiner_id bigint,
    first_joiner_name character varying(255)
);


--
-- Name: voice_status_history_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.voice_status_history_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: voice_status_history_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.voice_status_history_id_seq OWNED BY public.voice_status_history.id;


--
-- Name: weapon_comprehensive_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.weapon_comprehensive_stats (
    id integer NOT NULL,
    round_id integer NOT NULL,
    round_date text NOT NULL,
    map_name text NOT NULL,
    round_number integer NOT NULL,
    player_guid text NOT NULL,
    player_name text NOT NULL,
    weapon_name text NOT NULL,
    kills integer DEFAULT 0,
    deaths integer DEFAULT 0,
    headshots integer DEFAULT 0,
    shots integer DEFAULT 0,
    hits integer DEFAULT 0,
    accuracy real DEFAULT 0,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP
);


--
-- Name: weapon_comprehensive_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.weapon_comprehensive_stats_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: weapon_comprehensive_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.weapon_comprehensive_stats_id_seq OWNED BY public.weapon_comprehensive_stats.id;


--
-- Name: website_users; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.website_users (
    id bigint NOT NULL,
    created_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    updated_at timestamp without time zone DEFAULT CURRENT_TIMESTAMP,
    last_login_at timestamp without time zone
);


--
-- Name: account_link_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_link_audit_log ALTER COLUMN id SET DEFAULT nextval('public.account_link_audit_log_id_seq'::regclass);


--
-- Name: achievement_notification_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievement_notification_ledger ALTER COLUMN id SET DEFAULT nextval('public.achievement_notification_ledger_id_seq'::regclass);


--
-- Name: availability_channel_links id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_channel_links ALTER COLUMN id SET DEFAULT nextval('public.availability_channel_links_id_seq'::regclass);


--
-- Name: availability_entries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_entries ALTER COLUMN id SET DEFAULT nextval('public.availability_entries_id_seq'::regclass);


--
-- Name: availability_promotion_campaigns id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_campaigns ALTER COLUMN id SET DEFAULT nextval('public.availability_promotion_campaigns_id_seq'::regclass);


--
-- Name: availability_promotion_jobs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_jobs ALTER COLUMN id SET DEFAULT nextval('public.availability_promotion_jobs_id_seq'::regclass);


--
-- Name: availability_promotion_send_logs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_send_logs ALTER COLUMN id SET DEFAULT nextval('public.availability_promotion_send_logs_id_seq'::regclass);


--
-- Name: availability_subscriptions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_subscriptions ALTER COLUMN id SET DEFAULT nextval('public.availability_subscriptions_id_seq'::regclass);


--
-- Name: combat_engagement id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.combat_engagement ALTER COLUMN id SET DEFAULT nextval('public.combat_engagement_id_seq'::regclass);


--
-- Name: crossfire_pairs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crossfire_pairs ALTER COLUMN id SET DEFAULT nextval('public.crossfire_pairs_id_seq'::regclass);


--
-- Name: daily_polls id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_polls ALTER COLUMN id SET DEFAULT nextval('public.daily_polls_id_seq'::regclass);


--
-- Name: discord_accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discord_accounts ALTER COLUMN id SET DEFAULT nextval('public.discord_accounts_id_seq'::regclass);


--
-- Name: live_status id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_status ALTER COLUMN id SET DEFAULT nextval('public.live_status_id_seq'::regclass);


--
-- Name: lua_round_teams id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lua_round_teams ALTER COLUMN id SET DEFAULT nextval('public.lua_round_teams_id_seq'::regclass);


--
-- Name: lua_spawn_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lua_spawn_stats ALTER COLUMN id SET DEFAULT nextval('public.lua_spawn_stats_id_seq'::regclass);


--
-- Name: map_kill_heatmap id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_kill_heatmap ALTER COLUMN id SET DEFAULT nextval('public.map_kill_heatmap_id_seq'::regclass);


--
-- Name: map_movement_heatmap id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_movement_heatmap ALTER COLUMN id SET DEFAULT nextval('public.map_movement_heatmap_id_seq'::regclass);


--
-- Name: map_performance id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_performance ALTER COLUMN id SET DEFAULT nextval('public.map_performance_id_seq'::regclass);


--
-- Name: match_predictions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_predictions ALTER COLUMN id SET DEFAULT nextval('public.match_predictions_id_seq'::regclass);


--
-- Name: matchup_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matchup_history ALTER COLUMN id SET DEFAULT nextval('public.matchup_history_id_seq'::regclass);


--
-- Name: notifications_ledger id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications_ledger ALTER COLUMN id SET DEFAULT nextval('public.notifications_ledger_id_seq'::regclass);


--
-- Name: permission_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permission_audit_log ALTER COLUMN id SET DEFAULT nextval('public.permission_audit_log_id_seq'::regclass);


--
-- Name: planning_sessions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_sessions ALTER COLUMN id SET DEFAULT nextval('public.planning_sessions_id_seq'::regclass);


--
-- Name: planning_team_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_members ALTER COLUMN id SET DEFAULT nextval('public.planning_team_members_id_seq'::regclass);


--
-- Name: planning_team_names id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_names ALTER COLUMN id SET DEFAULT nextval('public.planning_team_names_id_seq'::regclass);


--
-- Name: planning_teams id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_teams ALTER COLUMN id SET DEFAULT nextval('public.planning_teams_id_seq'::regclass);


--
-- Name: planning_votes id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_votes ALTER COLUMN id SET DEFAULT nextval('public.planning_votes_id_seq'::regclass);


--
-- Name: player_aliases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_aliases ALTER COLUMN id SET DEFAULT nextval('public.player_aliases_id_seq'::regclass);


--
-- Name: player_comprehensive_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_comprehensive_stats ALTER COLUMN id SET DEFAULT nextval('public.player_comprehensive_stats_id_seq'::regclass);


--
-- Name: player_links id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_links ALTER COLUMN id SET DEFAULT nextval('public.player_links_id_seq'::regclass);


--
-- Name: player_skill_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_skill_history ALTER COLUMN id SET DEFAULT nextval('public.player_skill_history_id_seq'::regclass);


--
-- Name: player_teamplay_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_teamplay_stats ALTER COLUMN id SET DEFAULT nextval('public.player_teamplay_stats_id_seq'::regclass);


--
-- Name: player_track id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_track ALTER COLUMN id SET DEFAULT nextval('public.player_track_id_seq'::regclass);


--
-- Name: poll_responses id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_responses ALTER COLUMN id SET DEFAULT nextval('public.poll_responses_id_seq'::regclass);


--
-- Name: processed_endstats_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processed_endstats_files ALTER COLUMN id SET DEFAULT nextval('public.processed_endstats_files_id_seq'::regclass);


--
-- Name: processed_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processed_files ALTER COLUMN id SET DEFAULT nextval('public.processed_files_id_seq'::regclass);


--
-- Name: proximity_carrier_event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_event ALTER COLUMN id SET DEFAULT nextval('public.proximity_carrier_event_id_seq'::regclass);


--
-- Name: proximity_carrier_kill id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_kill ALTER COLUMN id SET DEFAULT nextval('public.proximity_carrier_kill_id_seq'::regclass);


--
-- Name: proximity_carrier_return id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_return ALTER COLUMN id SET DEFAULT nextval('public.proximity_carrier_return_id_seq'::regclass);


--
-- Name: proximity_combat_position id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_combat_position ALTER COLUMN id SET DEFAULT nextval('public.proximity_combat_position_id_seq'::regclass);


--
-- Name: proximity_construction_event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_construction_event ALTER COLUMN id SET DEFAULT nextval('public.proximity_construction_event_id_seq'::regclass);


--
-- Name: proximity_crossfire_opportunity id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_crossfire_opportunity ALTER COLUMN id SET DEFAULT nextval('public.proximity_crossfire_opportunity_id_seq'::regclass);


--
-- Name: proximity_escort_credit id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_escort_credit ALTER COLUMN id SET DEFAULT nextval('public.proximity_escort_credit_id_seq'::regclass);


--
-- Name: proximity_focus_fire id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_focus_fire ALTER COLUMN id SET DEFAULT nextval('public.proximity_focus_fire_id_seq'::regclass);


--
-- Name: proximity_hit_region id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_hit_region ALTER COLUMN id SET DEFAULT nextval('public.proximity_hit_region_id_seq'::regclass);


--
-- Name: proximity_hit_region_summary id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_hit_region_summary ALTER COLUMN id SET DEFAULT nextval('public.proximity_hit_region_summary_id_seq'::regclass);


--
-- Name: proximity_kill_outcome id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_kill_outcome ALTER COLUMN id SET DEFAULT nextval('public.proximity_kill_outcome_id_seq'::regclass);


--
-- Name: proximity_lua_trade_kill id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_lua_trade_kill ALTER COLUMN id SET DEFAULT nextval('public.proximity_lua_trade_kill_id_seq'::regclass);


--
-- Name: proximity_objective_focus id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_objective_focus ALTER COLUMN id SET DEFAULT nextval('public.proximity_objective_focus_id_seq'::regclass);


--
-- Name: proximity_objective_run id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_objective_run ALTER COLUMN id SET DEFAULT nextval('public.proximity_objective_run_id_seq'::regclass);


--
-- Name: proximity_processed_files id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_processed_files ALTER COLUMN id SET DEFAULT nextval('public.proximity_processed_files_id_seq'::regclass);


--
-- Name: proximity_reaction_metric id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_reaction_metric ALTER COLUMN id SET DEFAULT nextval('public.proximity_reaction_metric_id_seq'::regclass);


--
-- Name: proximity_revive id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_revive ALTER COLUMN id SET DEFAULT nextval('public.proximity_revive_id_seq'::regclass);


--
-- Name: proximity_spawn_timing id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_spawn_timing ALTER COLUMN id SET DEFAULT nextval('public.proximity_spawn_timing_id_seq'::regclass);


--
-- Name: proximity_support_summary id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_support_summary ALTER COLUMN id SET DEFAULT nextval('public.proximity_support_summary_id_seq'::regclass);


--
-- Name: proximity_team_cohesion id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_team_cohesion ALTER COLUMN id SET DEFAULT nextval('public.proximity_team_cohesion_id_seq'::regclass);


--
-- Name: proximity_team_push id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_team_push ALTER COLUMN id SET DEFAULT nextval('public.proximity_team_push_id_seq'::regclass);


--
-- Name: proximity_trade_event id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_trade_event ALTER COLUMN id SET DEFAULT nextval('public.proximity_trade_event_id_seq'::regclass);


--
-- Name: proximity_vehicle_progress id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_vehicle_progress ALTER COLUMN id SET DEFAULT nextval('public.proximity_vehicle_progress_id_seq'::regclass);


--
-- Name: proximity_weapon_accuracy id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_weapon_accuracy ALTER COLUMN id SET DEFAULT nextval('public.proximity_weapon_accuracy_id_seq'::regclass);


--
-- Name: round_assemblies id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assemblies ALTER COLUMN id SET DEFAULT nextval('public.round_assemblies_id_seq'::regclass);


--
-- Name: round_assembly_events id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assembly_events ALTER COLUMN id SET DEFAULT nextval('public.round_assembly_events_id_seq'::regclass);


--
-- Name: round_awards id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_awards ALTER COLUMN id SET DEFAULT nextval('public.round_awards_id_seq'::regclass);


--
-- Name: round_correlations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_correlations ALTER COLUMN id SET DEFAULT nextval('public.round_correlations_id_seq'::regclass);


--
-- Name: round_vs_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_vs_stats ALTER COLUMN id SET DEFAULT nextval('public.round_vs_stats_id_seq'::regclass);


--
-- Name: rounds id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rounds ALTER COLUMN id SET DEFAULT nextval('public.rounds_id_seq'::regclass);


--
-- Name: schema_migrations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations ALTER COLUMN id SET DEFAULT nextval('public.schema_migrations_id_seq'::regclass);


--
-- Name: server_status_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.server_status_history ALTER COLUMN id SET DEFAULT nextval('public.server_status_history_id_seq'::regclass);


--
-- Name: session_results id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_results ALTER COLUMN id SET DEFAULT nextval('public.session_results_id_seq'::regclass);


--
-- Name: session_round_scores id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_round_scores ALTER COLUMN id SET DEFAULT nextval('public.session_round_scores_id_seq'::regclass);


--
-- Name: session_teams id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_teams ALTER COLUMN id SET DEFAULT nextval('public.session_teams_id_seq'::regclass);


--
-- Name: storytelling_kill_impact id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storytelling_kill_impact ALTER COLUMN id SET DEFAULT nextval('public.storytelling_kill_impact_id_seq'::regclass);


--
-- Name: team_pool id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_pool ALTER COLUMN id SET DEFAULT nextval('public.team_pool_id_seq'::regclass);


--
-- Name: upload_tags id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.upload_tags ALTER COLUMN id SET DEFAULT nextval('public.upload_tags_id_seq'::regclass);


--
-- Name: user_permissions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_permissions ALTER COLUMN id SET DEFAULT nextval('public.user_permissions_id_seq'::regclass);


--
-- Name: voice_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_members ALTER COLUMN id SET DEFAULT nextval('public.voice_members_id_seq'::regclass);


--
-- Name: voice_status_history id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_status_history ALTER COLUMN id SET DEFAULT nextval('public.voice_status_history_id_seq'::regclass);


--
-- Name: weapon_comprehensive_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weapon_comprehensive_stats ALTER COLUMN id SET DEFAULT nextval('public.weapon_comprehensive_stats_id_seq'::regclass);


--
-- Name: account_link_audit_log account_link_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_link_audit_log
    ADD CONSTRAINT account_link_audit_log_pkey PRIMARY KEY (id);


--
-- Name: achievement_notification_ledger achievement_notification_ledger_achievement_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievement_notification_ledger
    ADD CONSTRAINT achievement_notification_ledger_achievement_id_key UNIQUE (achievement_id);


--
-- Name: achievement_notification_ledger achievement_notification_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.achievement_notification_ledger
    ADD CONSTRAINT achievement_notification_ledger_pkey PRIMARY KEY (id);


--
-- Name: availability_channel_links availability_channel_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_channel_links
    ADD CONSTRAINT availability_channel_links_pkey PRIMARY KEY (id);


--
-- Name: availability_channel_links availability_channel_links_user_id_channel_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_channel_links
    ADD CONSTRAINT availability_channel_links_user_id_channel_type_key UNIQUE (user_id, channel_type);


--
-- Name: availability_entries availability_entries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_entries
    ADD CONSTRAINT availability_entries_pkey PRIMARY KEY (id);


--
-- Name: availability_entries availability_entries_user_id_entry_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_entries
    ADD CONSTRAINT availability_entries_user_id_entry_date_key UNIQUE (user_id, entry_date);


--
-- Name: availability_promotion_campaigns availability_promotion_campai_campaign_date_idempotency_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_campaigns
    ADD CONSTRAINT availability_promotion_campai_campaign_date_idempotency_key_key UNIQUE (campaign_date, idempotency_key);


--
-- Name: availability_promotion_campaigns availability_promotion_campai_campaign_date_initiated_by_us_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_campaigns
    ADD CONSTRAINT availability_promotion_campai_campaign_date_initiated_by_us_key UNIQUE (campaign_date, initiated_by_user_id);


--
-- Name: availability_promotion_campaigns availability_promotion_campaigns_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_campaigns
    ADD CONSTRAINT availability_promotion_campaigns_pkey PRIMARY KEY (id);


--
-- Name: availability_promotion_jobs availability_promotion_jobs_campaign_id_job_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_jobs
    ADD CONSTRAINT availability_promotion_jobs_campaign_id_job_type_key UNIQUE (campaign_id, job_type);


--
-- Name: availability_promotion_jobs availability_promotion_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_jobs
    ADD CONSTRAINT availability_promotion_jobs_pkey PRIMARY KEY (id);


--
-- Name: availability_promotion_send_logs availability_promotion_send_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_send_logs
    ADD CONSTRAINT availability_promotion_send_logs_pkey PRIMARY KEY (id);


--
-- Name: availability_subscriptions availability_subscriptions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_subscriptions
    ADD CONSTRAINT availability_subscriptions_pkey PRIMARY KEY (id);


--
-- Name: availability_subscriptions availability_subscriptions_user_id_channel_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_subscriptions
    ADD CONSTRAINT availability_subscriptions_user_id_channel_type_key UNIQUE (user_id, channel_type);


--
-- Name: availability_user_settings availability_user_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_user_settings
    ADD CONSTRAINT availability_user_settings_pkey PRIMARY KEY (user_id);


--
-- Name: combat_engagement combat_engagement_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.combat_engagement
    ADD CONSTRAINT combat_engagement_pkey PRIMARY KEY (id);


--
-- Name: combat_engagement combat_engagement_session_date_round_number_round_start_unix_en; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.combat_engagement
    ADD CONSTRAINT combat_engagement_session_date_round_number_round_start_unix_en UNIQUE (session_date, round_number, round_start_unix, engagement_id);


--
-- Name: crossfire_pairs crossfire_pairs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crossfire_pairs
    ADD CONSTRAINT crossfire_pairs_pkey PRIMARY KEY (id);


--
-- Name: crossfire_pairs crossfire_pairs_player1_guid_player2_guid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.crossfire_pairs
    ADD CONSTRAINT crossfire_pairs_player1_guid_player2_guid_key UNIQUE (player1_guid, player2_guid);


--
-- Name: daily_polls daily_polls_message_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_polls
    ADD CONSTRAINT daily_polls_message_id_key UNIQUE (message_id);


--
-- Name: daily_polls daily_polls_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_polls
    ADD CONSTRAINT daily_polls_pkey PRIMARY KEY (id);


--
-- Name: daily_polls daily_polls_poll_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.daily_polls
    ADD CONSTRAINT daily_polls_poll_date_key UNIQUE (poll_date);


--
-- Name: discord_accounts discord_accounts_discord_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discord_accounts
    ADD CONSTRAINT discord_accounts_discord_user_id_key UNIQUE (discord_user_id);


--
-- Name: discord_accounts discord_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discord_accounts
    ADD CONSTRAINT discord_accounts_pkey PRIMARY KEY (id);


--
-- Name: discord_accounts discord_accounts_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discord_accounts
    ADD CONSTRAINT discord_accounts_user_id_key UNIQUE (user_id);


--
-- Name: greatshot_analysis greatshot_analysis_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.greatshot_analysis
    ADD CONSTRAINT greatshot_analysis_pkey PRIMARY KEY (demo_id);


--
-- Name: greatshot_demos greatshot_demos_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.greatshot_demos
    ADD CONSTRAINT greatshot_demos_pkey PRIMARY KEY (id);


--
-- Name: greatshot_highlights greatshot_highlights_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.greatshot_highlights
    ADD CONSTRAINT greatshot_highlights_pkey PRIMARY KEY (id);


--
-- Name: greatshot_renders greatshot_renders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.greatshot_renders
    ADD CONSTRAINT greatshot_renders_pkey PRIMARY KEY (id);


--
-- Name: live_status live_status_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_status
    ADD CONSTRAINT live_status_pkey PRIMARY KEY (id);


--
-- Name: live_status live_status_status_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.live_status
    ADD CONSTRAINT live_status_status_type_key UNIQUE (status_type);


--
-- Name: lua_round_teams lua_round_teams_match_id_round_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lua_round_teams
    ADD CONSTRAINT lua_round_teams_match_id_round_number_key UNIQUE (match_id, round_number);


--
-- Name: lua_round_teams lua_round_teams_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lua_round_teams
    ADD CONSTRAINT lua_round_teams_pkey PRIMARY KEY (id);


--
-- Name: lua_spawn_stats lua_spawn_stats_match_id_round_number_player_guid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lua_spawn_stats
    ADD CONSTRAINT lua_spawn_stats_match_id_round_number_player_guid_key UNIQUE (match_id, round_number, player_guid);


--
-- Name: lua_spawn_stats lua_spawn_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.lua_spawn_stats
    ADD CONSTRAINT lua_spawn_stats_pkey PRIMARY KEY (id);


--
-- Name: map_kill_heatmap map_kill_heatmap_map_name_grid_x_grid_y_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_kill_heatmap
    ADD CONSTRAINT map_kill_heatmap_map_name_grid_x_grid_y_key UNIQUE (map_name, grid_x, grid_y);


--
-- Name: map_kill_heatmap map_kill_heatmap_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_kill_heatmap
    ADD CONSTRAINT map_kill_heatmap_pkey PRIMARY KEY (id);


--
-- Name: map_movement_heatmap map_movement_heatmap_map_name_grid_x_grid_y_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_movement_heatmap
    ADD CONSTRAINT map_movement_heatmap_map_name_grid_x_grid_y_key UNIQUE (map_name, grid_x, grid_y);


--
-- Name: map_movement_heatmap map_movement_heatmap_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_movement_heatmap
    ADD CONSTRAINT map_movement_heatmap_pkey PRIMARY KEY (id);


--
-- Name: map_performance map_performance_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_performance
    ADD CONSTRAINT map_performance_pkey PRIMARY KEY (id);


--
-- Name: map_performance map_performance_player_guid_map_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.map_performance
    ADD CONSTRAINT map_performance_player_guid_map_name_key UNIQUE (player_guid, map_name);


--
-- Name: match_predictions match_predictions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.match_predictions
    ADD CONSTRAINT match_predictions_pkey PRIMARY KEY (id);


--
-- Name: matchup_history matchup_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matchup_history
    ADD CONSTRAINT matchup_history_pkey PRIMARY KEY (id);


--
-- Name: matchup_history matchup_history_session_date_gaming_session_id_matchup_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.matchup_history
    ADD CONSTRAINT matchup_history_session_date_gaming_session_id_matchup_id_key UNIQUE (session_date, gaming_session_id, matchup_id);


--
-- Name: notifications_ledger notifications_ledger_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications_ledger
    ADD CONSTRAINT notifications_ledger_pkey PRIMARY KEY (id);


--
-- Name: notifications_ledger notifications_ledger_user_id_event_key_channel_type_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.notifications_ledger
    ADD CONSTRAINT notifications_ledger_user_id_event_key_channel_type_key UNIQUE (user_id, event_key, channel_type);


--
-- Name: permission_audit_log permission_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.permission_audit_log
    ADD CONSTRAINT permission_audit_log_pkey PRIMARY KEY (id);


--
-- Name: planning_sessions planning_sessions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_sessions
    ADD CONSTRAINT planning_sessions_pkey PRIMARY KEY (id);


--
-- Name: planning_sessions planning_sessions_session_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_sessions
    ADD CONSTRAINT planning_sessions_session_date_key UNIQUE (session_date);


--
-- Name: planning_team_members planning_team_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_members
    ADD CONSTRAINT planning_team_members_pkey PRIMARY KEY (id);


--
-- Name: planning_team_members planning_team_members_session_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_members
    ADD CONSTRAINT planning_team_members_session_id_user_id_key UNIQUE (session_id, user_id);


--
-- Name: planning_team_members planning_team_members_team_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_members
    ADD CONSTRAINT planning_team_members_team_id_user_id_key UNIQUE (team_id, user_id);


--
-- Name: planning_team_names planning_team_names_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_names
    ADD CONSTRAINT planning_team_names_pkey PRIMARY KEY (id);


--
-- Name: planning_teams planning_teams_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_teams
    ADD CONSTRAINT planning_teams_pkey PRIMARY KEY (id);


--
-- Name: planning_teams planning_teams_session_id_side_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_teams
    ADD CONSTRAINT planning_teams_session_id_side_key UNIQUE (session_id, side);


--
-- Name: planning_votes planning_votes_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_votes
    ADD CONSTRAINT planning_votes_pkey PRIMARY KEY (id);


--
-- Name: planning_votes planning_votes_session_id_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_votes
    ADD CONSTRAINT planning_votes_session_id_user_id_key UNIQUE (session_id, user_id);


--
-- Name: player_aliases player_aliases_guid_alias_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_aliases
    ADD CONSTRAINT player_aliases_guid_alias_key UNIQUE (guid, alias);


--
-- Name: player_aliases player_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_aliases
    ADD CONSTRAINT player_aliases_pkey PRIMARY KEY (id);


--
-- Name: player_comprehensive_stats player_comprehensive_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_comprehensive_stats
    ADD CONSTRAINT player_comprehensive_stats_pkey PRIMARY KEY (id);


--
-- Name: player_comprehensive_stats player_comprehensive_stats_round_id_player_guid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_comprehensive_stats
    ADD CONSTRAINT player_comprehensive_stats_round_id_player_guid_key UNIQUE (round_id, player_guid);


--
-- Name: player_links player_links_discord_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_links
    ADD CONSTRAINT player_links_discord_id_key UNIQUE (discord_id);


--
-- Name: player_links player_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_links
    ADD CONSTRAINT player_links_pkey PRIMARY KEY (id);


--
-- Name: player_links player_links_player_guid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_links
    ADD CONSTRAINT player_links_player_guid_key UNIQUE (player_guid);


--
-- Name: player_skill_history player_skill_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_skill_history
    ADD CONSTRAINT player_skill_history_pkey PRIMARY KEY (id);


--
-- Name: player_skill_ratings player_skill_ratings_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_skill_ratings
    ADD CONSTRAINT player_skill_ratings_pkey PRIMARY KEY (player_guid);


--
-- Name: player_teamplay_stats player_teamplay_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_teamplay_stats
    ADD CONSTRAINT player_teamplay_stats_pkey PRIMARY KEY (id);


--
-- Name: player_teamplay_stats player_teamplay_stats_player_guid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_teamplay_stats
    ADD CONSTRAINT player_teamplay_stats_player_guid_key UNIQUE (player_guid);


--
-- Name: player_track player_track_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_track
    ADD CONSTRAINT player_track_pkey PRIMARY KEY (id);


--
-- Name: player_track player_track_session_date_round_number_round_start_unix_player_; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_track
    ADD CONSTRAINT player_track_session_date_round_number_round_start_unix_player_ UNIQUE (session_date, round_number, round_start_unix, player_guid, spawn_time_ms);


--
-- Name: poll_reminder_preferences poll_reminder_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_reminder_preferences
    ADD CONSTRAINT poll_reminder_preferences_pkey PRIMARY KEY (discord_user_id);


--
-- Name: poll_responses poll_responses_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_responses
    ADD CONSTRAINT poll_responses_pkey PRIMARY KEY (id);


--
-- Name: poll_responses poll_responses_poll_id_discord_user_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_responses
    ADD CONSTRAINT poll_responses_poll_id_discord_user_id_key UNIQUE (poll_id, discord_user_id);


--
-- Name: processed_endstats_files processed_endstats_files_filename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processed_endstats_files
    ADD CONSTRAINT processed_endstats_files_filename_key UNIQUE (filename);


--
-- Name: processed_endstats_files processed_endstats_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processed_endstats_files
    ADD CONSTRAINT processed_endstats_files_pkey PRIMARY KEY (id);


--
-- Name: processed_files processed_files_filename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processed_files
    ADD CONSTRAINT processed_files_filename_key UNIQUE (filename);


--
-- Name: processed_files processed_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processed_files
    ADD CONSTRAINT processed_files_pkey PRIMARY KEY (id);


--
-- Name: proximity_carrier_event proximity_carrier_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_event
    ADD CONSTRAINT proximity_carrier_event_pkey PRIMARY KEY (id);


--
-- Name: proximity_carrier_event proximity_carrier_event_session_date_round_number_round_sta_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_event
    ADD CONSTRAINT proximity_carrier_event_session_date_round_number_round_sta_key UNIQUE (session_date, round_number, round_start_unix, carrier_guid, pickup_time);


--
-- Name: proximity_carrier_kill proximity_carrier_kill_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_kill
    ADD CONSTRAINT proximity_carrier_kill_pkey PRIMARY KEY (id);


--
-- Name: proximity_carrier_kill proximity_carrier_kill_session_date_round_number_round_star_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_kill
    ADD CONSTRAINT proximity_carrier_kill_session_date_round_number_round_star_key UNIQUE (session_date, round_number, round_start_unix, carrier_guid, kill_time);


--
-- Name: proximity_carrier_return proximity_carrier_return_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_return
    ADD CONSTRAINT proximity_carrier_return_pkey PRIMARY KEY (id);


--
-- Name: proximity_carrier_return proximity_carrier_return_session_date_round_number_round_st_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_return
    ADD CONSTRAINT proximity_carrier_return_session_date_round_number_round_st_key UNIQUE (session_date, round_number, round_start_unix, returner_guid, return_time);


--
-- Name: proximity_combat_position proximity_combat_position_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_combat_position
    ADD CONSTRAINT proximity_combat_position_pkey PRIMARY KEY (id);


--
-- Name: proximity_combat_position proximity_combat_position_session_date_round_number_round_s_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_combat_position
    ADD CONSTRAINT proximity_combat_position_session_date_round_number_round_s_key UNIQUE (session_date, round_number, round_start_unix, event_time, attacker_guid, victim_guid);


--
-- Name: proximity_construction_event proximity_construction_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_construction_event
    ADD CONSTRAINT proximity_construction_event_pkey PRIMARY KEY (id);


--
-- Name: proximity_construction_event proximity_construction_event_session_date_round_number_roun_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_construction_event
    ADD CONSTRAINT proximity_construction_event_session_date_round_number_roun_key UNIQUE (session_date, round_number, round_start_unix, player_guid, event_time, event_type);


--
-- Name: proximity_crossfire_opportunity proximity_crossfire_opportuni_session_date_round_number_rou_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_crossfire_opportunity
    ADD CONSTRAINT proximity_crossfire_opportuni_session_date_round_number_rou_key UNIQUE (session_date, round_number, round_start_unix, target_guid, event_time, teammate1_guid, teammate2_guid);


--
-- Name: proximity_crossfire_opportunity proximity_crossfire_opportunity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_crossfire_opportunity
    ADD CONSTRAINT proximity_crossfire_opportunity_pkey PRIMARY KEY (id);


--
-- Name: proximity_escort_credit proximity_escort_credit_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_escort_credit
    ADD CONSTRAINT proximity_escort_credit_pkey PRIMARY KEY (id);


--
-- Name: proximity_escort_credit proximity_escort_credit_session_date_round_number_round_sta_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_escort_credit
    ADD CONSTRAINT proximity_escort_credit_session_date_round_number_round_sta_key UNIQUE (session_date, round_number, round_start_unix, player_guid, vehicle_name);


--
-- Name: proximity_focus_fire proximity_focus_fire_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_focus_fire
    ADD CONSTRAINT proximity_focus_fire_pkey PRIMARY KEY (id);


--
-- Name: proximity_focus_fire proximity_focus_fire_session_date_round_number_round_start__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_focus_fire
    ADD CONSTRAINT proximity_focus_fire_session_date_round_number_round_start__key UNIQUE (session_date, round_number, round_start_unix, engagement_id);


--
-- Name: proximity_hit_region proximity_hit_region_natural_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_hit_region
    ADD CONSTRAINT proximity_hit_region_natural_key UNIQUE (session_date, round_number, round_start_unix, attacker_guid, victim_guid, event_time, weapon_id);


--
-- Name: proximity_hit_region proximity_hit_region_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_hit_region
    ADD CONSTRAINT proximity_hit_region_pkey PRIMARY KEY (id);


--
-- Name: proximity_hit_region_summary proximity_hit_region_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_hit_region_summary
    ADD CONSTRAINT proximity_hit_region_summary_pkey PRIMARY KEY (id);


--
-- Name: proximity_hit_region_summary proximity_hit_region_summary_player_guid_weapon_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_hit_region_summary
    ADD CONSTRAINT proximity_hit_region_summary_player_guid_weapon_id_key UNIQUE (player_guid, weapon_id);


--
-- Name: proximity_kill_outcome proximity_kill_outcome_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_kill_outcome
    ADD CONSTRAINT proximity_kill_outcome_pkey PRIMARY KEY (id);


--
-- Name: proximity_kill_outcome proximity_kill_outcome_session_date_round_number_round_star_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_kill_outcome
    ADD CONSTRAINT proximity_kill_outcome_session_date_round_number_round_star_key UNIQUE (session_date, round_number, round_start_unix, kill_time, victim_guid);


--
-- Name: proximity_lua_trade_kill proximity_lua_trade_kill_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_lua_trade_kill
    ADD CONSTRAINT proximity_lua_trade_kill_pkey PRIMARY KEY (id);


--
-- Name: proximity_lua_trade_kill proximity_lua_trade_kill_session_date_round_number_round_st_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_lua_trade_kill
    ADD CONSTRAINT proximity_lua_trade_kill_session_date_round_number_round_st_key UNIQUE (session_date, round_number, round_start_unix, original_victim_guid, original_kill_time, trader_guid);


--
-- Name: proximity_objective_focus proximity_objective_focus_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_objective_focus
    ADD CONSTRAINT proximity_objective_focus_pkey PRIMARY KEY (id);


--
-- Name: proximity_objective_focus proximity_objective_focus_round_scope_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_objective_focus
    ADD CONSTRAINT proximity_objective_focus_round_scope_unique UNIQUE (session_date, round_number, round_start_unix, player_guid);


--
-- Name: proximity_objective_focus proximity_objective_focus_session_date_round_number_round_start; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_objective_focus
    ADD CONSTRAINT proximity_objective_focus_session_date_round_number_round_start UNIQUE (session_date, round_number, round_start_unix, player_guid);


--
-- Name: proximity_objective_run proximity_objective_run_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_objective_run
    ADD CONSTRAINT proximity_objective_run_pkey PRIMARY KEY (id);


--
-- Name: proximity_objective_run proximity_objective_run_session_date_round_number_round_sta_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_objective_run
    ADD CONSTRAINT proximity_objective_run_session_date_round_number_round_sta_key UNIQUE (session_date, round_number, round_start_unix, engineer_guid, action_time, action_type);


--
-- Name: proximity_processed_files proximity_processed_files_filename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_processed_files
    ADD CONSTRAINT proximity_processed_files_filename_key UNIQUE (filename);


--
-- Name: proximity_processed_files proximity_processed_files_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_processed_files
    ADD CONSTRAINT proximity_processed_files_pkey PRIMARY KEY (id);


--
-- Name: proximity_reaction_metric proximity_reaction_metric_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_reaction_metric
    ADD CONSTRAINT proximity_reaction_metric_pkey PRIMARY KEY (id);


--
-- Name: proximity_reaction_metric proximity_reaction_metric_session_date_round_number_round_s_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_reaction_metric
    ADD CONSTRAINT proximity_reaction_metric_session_date_round_number_round_s_key UNIQUE (session_date, round_number, round_start_unix, engagement_id, target_guid);


--
-- Name: proximity_revive proximity_revive_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_revive
    ADD CONSTRAINT proximity_revive_pkey PRIMARY KEY (id);


--
-- Name: proximity_spawn_timing proximity_spawn_timing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_spawn_timing
    ADD CONSTRAINT proximity_spawn_timing_pkey PRIMARY KEY (id);


--
-- Name: proximity_spawn_timing proximity_spawn_timing_session_date_round_number_round_star_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_spawn_timing
    ADD CONSTRAINT proximity_spawn_timing_session_date_round_number_round_star_key UNIQUE (session_date, round_number, round_start_unix, killer_guid, victim_guid, kill_time);


--
-- Name: proximity_support_summary proximity_support_summary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_support_summary
    ADD CONSTRAINT proximity_support_summary_pkey PRIMARY KEY (id);


--
-- Name: proximity_support_summary proximity_support_summary_session_date_round_number_round_s_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_support_summary
    ADD CONSTRAINT proximity_support_summary_session_date_round_number_round_s_key UNIQUE (session_date, round_number, round_start_unix);


--
-- Name: proximity_team_cohesion proximity_team_cohesion_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_team_cohesion
    ADD CONSTRAINT proximity_team_cohesion_pkey PRIMARY KEY (id);


--
-- Name: proximity_team_cohesion proximity_team_cohesion_session_date_round_number_round_sta_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_team_cohesion
    ADD CONSTRAINT proximity_team_cohesion_session_date_round_number_round_sta_key UNIQUE (session_date, round_number, round_start_unix, team, sample_time);


--
-- Name: proximity_team_push proximity_team_push_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_team_push
    ADD CONSTRAINT proximity_team_push_pkey PRIMARY KEY (id);


--
-- Name: proximity_team_push proximity_team_push_session_date_round_number_round_start_u_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_team_push
    ADD CONSTRAINT proximity_team_push_session_date_round_number_round_start_u_key UNIQUE (session_date, round_number, round_start_unix, team, start_time);


--
-- Name: proximity_trade_event proximity_trade_event_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_trade_event
    ADD CONSTRAINT proximity_trade_event_pkey PRIMARY KEY (id);


--
-- Name: proximity_trade_event proximity_trade_event_session_date_round_number_round_start_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_trade_event
    ADD CONSTRAINT proximity_trade_event_session_date_round_number_round_start_key UNIQUE (session_date, round_number, round_start_unix, victim_guid, death_time_ms);


--
-- Name: proximity_vehicle_progress proximity_vehicle_progress_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_vehicle_progress
    ADD CONSTRAINT proximity_vehicle_progress_pkey PRIMARY KEY (id);


--
-- Name: proximity_vehicle_progress proximity_vehicle_progress_session_date_round_number_round__key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_vehicle_progress
    ADD CONSTRAINT proximity_vehicle_progress_session_date_round_number_round__key UNIQUE (session_date, round_number, round_start_unix, vehicle_name);


--
-- Name: proximity_weapon_accuracy proximity_weapon_accuracy_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_weapon_accuracy
    ADD CONSTRAINT proximity_weapon_accuracy_pkey PRIMARY KEY (id);


--
-- Name: round_assemblies round_assemblies_assembly_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assemblies
    ADD CONSTRAINT round_assemblies_assembly_key_key UNIQUE (assembly_key);


--
-- Name: round_assemblies round_assemblies_gaming_session_id_map_name_map_play_seq_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assemblies
    ADD CONSTRAINT round_assemblies_gaming_session_id_map_name_map_play_seq_key UNIQUE (gaming_session_id, map_name, map_play_seq);


--
-- Name: round_assemblies round_assemblies_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assemblies
    ADD CONSTRAINT round_assemblies_pkey PRIMARY KEY (id);


--
-- Name: round_assembly_events round_assembly_events_event_key_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assembly_events
    ADD CONSTRAINT round_assembly_events_event_key_key UNIQUE (event_key);


--
-- Name: round_assembly_events round_assembly_events_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assembly_events
    ADD CONSTRAINT round_assembly_events_pkey PRIMARY KEY (id);


--
-- Name: round_awards round_awards_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_awards
    ADD CONSTRAINT round_awards_pkey PRIMARY KEY (id);


--
-- Name: round_correlations round_correlations_correlation_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_correlations
    ADD CONSTRAINT round_correlations_correlation_id_key UNIQUE (correlation_id);


--
-- Name: round_correlations round_correlations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_correlations
    ADD CONSTRAINT round_correlations_pkey PRIMARY KEY (id);


--
-- Name: round_vs_stats round_vs_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_vs_stats
    ADD CONSTRAINT round_vs_stats_pkey PRIMARY KEY (id);


--
-- Name: rounds rounds_match_id_round_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rounds
    ADD CONSTRAINT rounds_match_id_round_number_key UNIQUE (match_id, round_number);


--
-- Name: rounds rounds_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.rounds
    ADD CONSTRAINT rounds_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_filename_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_filename_key UNIQUE (filename);


--
-- Name: schema_migrations schema_migrations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_pkey PRIMARY KEY (id);


--
-- Name: schema_migrations schema_migrations_version_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.schema_migrations
    ADD CONSTRAINT schema_migrations_version_key UNIQUE (version);


--
-- Name: server_status_history server_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.server_status_history
    ADD CONSTRAINT server_status_history_pkey PRIMARY KEY (id);


--
-- Name: session_results session_results_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_results
    ADD CONSTRAINT session_results_pkey PRIMARY KEY (id);


--
-- Name: session_results session_results_session_date_map_name_gaming_session_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_results
    ADD CONSTRAINT session_results_session_date_map_name_gaming_session_id_key UNIQUE (session_date, map_name, gaming_session_id);


--
-- Name: session_round_scores session_round_scores_gaming_session_id_round_number_map_nam_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_round_scores
    ADD CONSTRAINT session_round_scores_gaming_session_id_round_number_map_nam_key UNIQUE (gaming_session_id, round_number, map_name);


--
-- Name: session_round_scores session_round_scores_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_round_scores
    ADD CONSTRAINT session_round_scores_pkey PRIMARY KEY (id);


--
-- Name: session_teams session_teams_identity_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_teams
    ADD CONSTRAINT session_teams_identity_unique UNIQUE (session_identity, map_name, team_name);


--
-- Name: session_teams session_teams_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.session_teams
    ADD CONSTRAINT session_teams_pkey PRIMARY KEY (id);


--
-- Name: storytelling_kill_impact storytelling_kill_impact_kill_outcome_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storytelling_kill_impact
    ADD CONSTRAINT storytelling_kill_impact_kill_outcome_id_key UNIQUE (kill_outcome_id);


--
-- Name: storytelling_kill_impact storytelling_kill_impact_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storytelling_kill_impact
    ADD CONSTRAINT storytelling_kill_impact_pkey PRIMARY KEY (id);


--
-- Name: subscription_preferences subscription_preferences_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.subscription_preferences
    ADD CONSTRAINT subscription_preferences_pkey PRIMARY KEY (user_id);


--
-- Name: team_pool team_pool_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_pool
    ADD CONSTRAINT team_pool_name_key UNIQUE (name);


--
-- Name: team_pool team_pool_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.team_pool
    ADD CONSTRAINT team_pool_pkey PRIMARY KEY (id);


--
-- Name: voice_members unique_active_member; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_members
    ADD CONSTRAINT unique_active_member UNIQUE (discord_id, left_at);


--
-- Name: upload_tags upload_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.upload_tags
    ADD CONSTRAINT upload_tags_pkey PRIMARY KEY (id);


--
-- Name: upload_tags upload_tags_upload_id_tag_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.upload_tags
    ADD CONSTRAINT upload_tags_upload_id_tag_key UNIQUE (upload_id, tag);


--
-- Name: uploads uploads_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.uploads
    ADD CONSTRAINT uploads_pkey PRIMARY KEY (id);


--
-- Name: user_permissions user_permissions_discord_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_permissions
    ADD CONSTRAINT user_permissions_discord_id_key UNIQUE (discord_id);


--
-- Name: user_permissions user_permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_permissions
    ADD CONSTRAINT user_permissions_pkey PRIMARY KEY (id);


--
-- Name: user_player_links user_player_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_player_links
    ADD CONSTRAINT user_player_links_pkey PRIMARY KEY (user_id);


--
-- Name: user_player_links user_player_links_player_guid_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_player_links
    ADD CONSTRAINT user_player_links_player_guid_key UNIQUE (player_guid);


--
-- Name: voice_members voice_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_members
    ADD CONSTRAINT voice_members_pkey PRIMARY KEY (id);


--
-- Name: voice_status_history voice_status_history_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voice_status_history
    ADD CONSTRAINT voice_status_history_pkey PRIMARY KEY (id);


--
-- Name: weapon_comprehensive_stats weapon_comprehensive_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weapon_comprehensive_stats
    ADD CONSTRAINT weapon_comprehensive_stats_pkey PRIMARY KEY (id);


--
-- Name: weapon_comprehensive_stats weapon_comprehensive_stats_round_id_player_guid_weapon_name_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weapon_comprehensive_stats
    ADD CONSTRAINT weapon_comprehensive_stats_round_id_player_guid_weapon_name_key UNIQUE (round_id, player_guid, weapon_name);


--
-- Name: website_users website_users_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.website_users
    ADD CONSTRAINT website_users_pkey PRIMARY KEY (id);


--
-- Name: idx_account_link_audit_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_account_link_audit_user ON public.account_link_audit_log USING btree (user_id, created_at DESC);


--
-- Name: idx_achievement_ledger_player_guid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_achievement_ledger_player_guid ON public.achievement_notification_ledger USING btree (player_guid);


--
-- Name: idx_audit_changed_by; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_changed_by ON public.permission_audit_log USING btree (changed_by);


--
-- Name: idx_audit_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_audit_target ON public.permission_audit_log USING btree (target_discord_id);


--
-- Name: idx_availability_channel_links_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_availability_channel_links_user ON public.availability_channel_links USING btree (user_id);


--
-- Name: idx_availability_entries_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_availability_entries_date ON public.availability_entries USING btree (entry_date);


--
-- Name: idx_availability_entries_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_availability_entries_status ON public.availability_entries USING btree (status);


--
-- Name: idx_availability_promotion_jobs_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_availability_promotion_jobs_due ON public.availability_promotion_jobs USING btree (status, run_at);


--
-- Name: idx_availability_subscriptions_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_availability_subscriptions_user ON public.availability_subscriptions USING btree (user_id);


--
-- Name: idx_carrier_event_carrier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_event_carrier ON public.proximity_carrier_event USING btree (carrier_guid);


--
-- Name: idx_carrier_event_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_event_map ON public.proximity_carrier_event USING btree (map_name);


--
-- Name: idx_carrier_event_outcome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_event_outcome ON public.proximity_carrier_event USING btree (outcome);


--
-- Name: idx_carrier_event_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_event_round_id ON public.proximity_carrier_event USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_carrier_event_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_event_session ON public.proximity_carrier_event USING btree (session_date, round_number);


--
-- Name: idx_carrier_kill_carrier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_kill_carrier ON public.proximity_carrier_kill USING btree (carrier_guid);


--
-- Name: idx_carrier_kill_killer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_kill_killer ON public.proximity_carrier_kill USING btree (killer_guid);


--
-- Name: idx_carrier_kill_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_kill_map ON public.proximity_carrier_kill USING btree (map_name);


--
-- Name: idx_carrier_kill_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_kill_round_id ON public.proximity_carrier_kill USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_carrier_kill_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_kill_session ON public.proximity_carrier_kill USING btree (session_date, round_number);


--
-- Name: idx_carrier_return_flag_team; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_return_flag_team ON public.proximity_carrier_return USING btree (flag_team);


--
-- Name: idx_carrier_return_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_return_map ON public.proximity_carrier_return USING btree (map_name);


--
-- Name: idx_carrier_return_returner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_return_returner ON public.proximity_carrier_return USING btree (returner_guid);


--
-- Name: idx_carrier_return_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_return_round_id ON public.proximity_carrier_return USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_carrier_return_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_carrier_return_session ON public.proximity_carrier_return USING btree (session_date, round_number, round_start_unix);


--
-- Name: idx_combat_engagement_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_combat_engagement_round_id ON public.combat_engagement USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_combat_engagement_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_combat_engagement_round_lookup_unlinked ON public.combat_engagement USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_combat_pos_attacker; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_combat_pos_attacker ON public.proximity_combat_position USING btree (attacker_guid);


--
-- Name: idx_combat_pos_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_combat_pos_class ON public.proximity_combat_position USING btree (victim_class);


--
-- Name: idx_combat_pos_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_combat_pos_map ON public.proximity_combat_position USING btree (map_name);


--
-- Name: idx_combat_pos_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_combat_pos_round ON public.proximity_combat_position USING btree (round_id);


--
-- Name: idx_combat_pos_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_combat_pos_session ON public.proximity_combat_position USING btree (session_date, round_number);


--
-- Name: idx_combat_pos_victim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_combat_pos_victim ON public.proximity_combat_position USING btree (victim_guid);


--
-- Name: idx_combat_pos_weapon; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_combat_pos_weapon ON public.proximity_combat_position USING btree (weapon_id);


--
-- Name: idx_construction_event_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_construction_event_map ON public.proximity_construction_event USING btree (map_name);


--
-- Name: idx_construction_event_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_construction_event_player ON public.proximity_construction_event USING btree (player_guid);


--
-- Name: idx_construction_event_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_construction_event_round_id ON public.proximity_construction_event USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_construction_event_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_construction_event_session ON public.proximity_construction_event USING btree (session_date, round_number, round_start_unix);


--
-- Name: idx_construction_event_track; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_construction_event_track ON public.proximity_construction_event USING btree (track_name);


--
-- Name: idx_construction_event_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_construction_event_type ON public.proximity_construction_event USING btree (event_type);


--
-- Name: idx_cp_attacker_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_cp_attacker_canonical ON public.proximity_combat_position USING btree (attacker_guid_canonical);


--
-- Name: idx_crossfire_opp_executed; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crossfire_opp_executed ON public.proximity_crossfire_opportunity USING btree (was_executed);


--
-- Name: idx_crossfire_opp_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crossfire_opp_session ON public.proximity_crossfire_opportunity USING btree (session_date, round_number);


--
-- Name: idx_crossfire_pairs_player1; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crossfire_pairs_player1 ON public.crossfire_pairs USING btree (player1_guid);


--
-- Name: idx_crossfire_pairs_player2; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_crossfire_pairs_player2 ON public.crossfire_pairs USING btree (player2_guid);


--
-- Name: idx_daily_polls_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_daily_polls_date ON public.daily_polls USING btree (poll_date DESC);


--
-- Name: idx_discord_accounts_discord_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_discord_accounts_discord_id ON public.discord_accounts USING btree (discord_user_id);


--
-- Name: idx_engagement_crossfire; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_engagement_crossfire ON public.combat_engagement USING btree (is_crossfire) WHERE (is_crossfire = true);


--
-- Name: idx_engagement_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_engagement_map ON public.combat_engagement USING btree (map_name);


--
-- Name: idx_engagement_outcome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_engagement_outcome ON public.combat_engagement USING btree (outcome);


--
-- Name: idx_engagement_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_engagement_session ON public.combat_engagement USING btree (session_date, round_number);


--
-- Name: idx_engagement_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_engagement_target ON public.combat_engagement USING btree (target_guid);


--
-- Name: idx_escort_credit_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_escort_credit_map ON public.proximity_escort_credit USING btree (map_name);


--
-- Name: idx_escort_credit_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_escort_credit_player ON public.proximity_escort_credit USING btree (player_guid);


--
-- Name: idx_escort_credit_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_escort_credit_round_id ON public.proximity_escort_credit USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_escort_credit_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_escort_credit_session ON public.proximity_escort_credit USING btree (session_date, round_number, round_start_unix);


--
-- Name: idx_escort_credit_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_escort_credit_vehicle ON public.proximity_escort_credit USING btree (vehicle_name);


--
-- Name: idx_focus_fire_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_focus_fire_map ON public.proximity_focus_fire USING btree (map_name);


--
-- Name: idx_focus_fire_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_focus_fire_round ON public.proximity_focus_fire USING btree (round_id);


--
-- Name: idx_focus_fire_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_focus_fire_score ON public.proximity_focus_fire USING btree (focus_score DESC);


--
-- Name: idx_focus_fire_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_focus_fire_target ON public.proximity_focus_fire USING btree (target_guid);


--
-- Name: idx_greatshot_demos_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_greatshot_demos_status ON public.greatshot_demos USING btree (status);


--
-- Name: idx_greatshot_demos_user_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_greatshot_demos_user_created_at ON public.greatshot_demos USING btree (user_id, created_at DESC);


--
-- Name: idx_greatshot_highlights_demo_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_greatshot_highlights_demo_id ON public.greatshot_highlights USING btree (demo_id);


--
-- Name: idx_greatshot_renders_highlight; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_greatshot_renders_highlight ON public.greatshot_renders USING btree (highlight_id);


--
-- Name: idx_hit_region_attacker; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hit_region_attacker ON public.proximity_hit_region USING btree (attacker_guid);


--
-- Name: idx_hit_region_region; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hit_region_region ON public.proximity_hit_region USING btree (hit_region);


--
-- Name: idx_hit_region_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hit_region_round ON public.proximity_hit_region USING btree (round_id);


--
-- Name: idx_hit_region_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hit_region_session ON public.proximity_hit_region USING btree (session_date, round_number);


--
-- Name: idx_hit_region_victim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hit_region_victim ON public.proximity_hit_region USING btree (victim_guid);


--
-- Name: idx_hit_region_weapon; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hit_region_weapon ON public.proximity_hit_region USING btree (weapon_id);


--
-- Name: idx_hr_summary_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_hr_summary_player ON public.proximity_hit_region_summary USING btree (player_guid);


--
-- Name: idx_kill_heatmap_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kill_heatmap_map ON public.map_kill_heatmap USING btree (map_name);


--
-- Name: idx_kill_outcome_killer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kill_outcome_killer ON public.proximity_kill_outcome USING btree (killer_guid);


--
-- Name: idx_kill_outcome_outcome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kill_outcome_outcome ON public.proximity_kill_outcome USING btree (outcome);


--
-- Name: idx_kill_outcome_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kill_outcome_round ON public.proximity_kill_outcome USING btree (round_id);


--
-- Name: idx_kill_outcome_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kill_outcome_session ON public.proximity_kill_outcome USING btree (session_date);


--
-- Name: idx_kill_outcome_victim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kill_outcome_victim ON public.proximity_kill_outcome USING btree (victim_guid);


--
-- Name: idx_kis_killer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kis_killer ON public.storytelling_kill_impact USING btree (killer_guid);


--
-- Name: idx_kis_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kis_map ON public.storytelling_kill_impact USING btree (map_name);


--
-- Name: idx_kis_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kis_session ON public.storytelling_kill_impact USING btree (session_date);


--
-- Name: idx_kis_session_killer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_kis_session_killer ON public.storytelling_kill_impact USING btree (session_date, killer_guid);


--
-- Name: idx_ko_killer_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ko_killer_canonical ON public.proximity_kill_outcome USING btree (killer_guid_canonical);


--
-- Name: idx_lua_round_teams_captured_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lua_round_teams_captured_at ON public.lua_round_teams USING btree (captured_at);


--
-- Name: idx_lua_round_teams_match_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lua_round_teams_match_id ON public.lua_round_teams USING btree (match_id);


--
-- Name: idx_lua_round_teams_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lua_round_teams_round_id ON public.lua_round_teams USING btree (round_id);


--
-- Name: idx_lua_round_teams_surrender; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lua_round_teams_surrender ON public.lua_round_teams USING btree (surrender_team) WHERE (surrender_team > 0);


--
-- Name: idx_lua_spawn_stats_match_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lua_spawn_stats_match_id ON public.lua_spawn_stats USING btree (match_id);


--
-- Name: idx_lua_spawn_stats_round_end; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lua_spawn_stats_round_end ON public.lua_spawn_stats USING btree (round_end_unix);


--
-- Name: idx_lua_spawn_stats_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lua_spawn_stats_round_id ON public.lua_spawn_stats USING btree (round_id);


--
-- Name: idx_lua_trade_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lua_trade_session ON public.proximity_lua_trade_kill USING btree (session_date, round_number);


--
-- Name: idx_lua_trade_trader; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_lua_trade_trader ON public.proximity_lua_trade_kill USING btree (trader_guid);


--
-- Name: idx_map_performance_guid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_map_performance_guid ON public.map_performance USING btree (player_guid);


--
-- Name: idx_map_performance_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_map_performance_map ON public.map_performance USING btree (map_name);


--
-- Name: idx_map_performance_winrate; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_map_performance_winrate ON public.map_performance USING btree (win_rate DESC);


--
-- Name: idx_matchup_history_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matchup_history_map ON public.matchup_history USING btree (map_name);


--
-- Name: idx_matchup_history_matchup_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matchup_history_matchup_id ON public.matchup_history USING btree (matchup_id);


--
-- Name: idx_matchup_history_session_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_matchup_history_session_date ON public.matchup_history USING btree (session_date);


--
-- Name: idx_movement_heatmap_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_movement_heatmap_map ON public.map_movement_heatmap USING btree (map_name);


--
-- Name: idx_notifications_ledger_event; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_ledger_event ON public.notifications_ledger USING btree (event_key);


--
-- Name: idx_notifications_ledger_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_ledger_user ON public.notifications_ledger USING btree (user_id);


--
-- Name: idx_notifications_ledger_user_event; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_notifications_ledger_user_event ON public.notifications_ledger USING btree (user_id, event_key);


--
-- Name: idx_pcp_session_attacker_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pcp_session_attacker_canonical ON public.proximity_combat_position USING btree (session_date, attacker_guid_canonical) WHERE (attacker_guid_canonical IS NOT NULL);


--
-- Name: idx_pko_session_killer_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pko_session_killer_canonical ON public.proximity_kill_outcome USING btree (session_date, killer_guid_canonical) WHERE (killer_guid_canonical IS NOT NULL);


--
-- Name: idx_planning_sessions_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planning_sessions_date ON public.planning_sessions USING btree (session_date DESC);


--
-- Name: idx_planning_team_members_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planning_team_members_session ON public.planning_team_members USING btree (session_id, team_id);


--
-- Name: idx_planning_team_names_unique_lower; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_planning_team_names_unique_lower ON public.planning_team_names USING btree (session_id, lower(name));


--
-- Name: idx_planning_votes_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_planning_votes_session ON public.planning_votes USING btree (session_id, suggestion_id);


--
-- Name: idx_player_aliases_alias_lower; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_aliases_alias_lower ON public.player_aliases USING btree (lower(alias));


--
-- Name: idx_player_links_display_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_links_display_name ON public.player_links USING btree (display_name);


--
-- Name: idx_player_stats_guid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_stats_guid ON public.player_comprehensive_stats USING btree (player_guid);


--
-- Name: idx_player_stats_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_stats_round ON public.player_comprehensive_stats USING btree (round_id);


--
-- Name: idx_player_track_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_track_round_id ON public.player_track USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_player_track_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_player_track_round_lookup_unlinked ON public.player_track USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_poll_responses_poll; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_poll_responses_poll ON public.poll_responses USING btree (poll_id);


--
-- Name: idx_poll_responses_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_poll_responses_type ON public.poll_responses USING btree (response_type);


--
-- Name: idx_poll_responses_user; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_poll_responses_user ON public.poll_responses USING btree (discord_user_id);


--
-- Name: idx_predictions_confidence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_predictions_confidence ON public.match_predictions USING btree (confidence);


--
-- Name: idx_predictions_discord_msg; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_predictions_discord_msg ON public.match_predictions USING btree (discord_message_id);


--
-- Name: idx_predictions_event_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_predictions_event_key ON public.match_predictions USING btree (prediction_event_key) WHERE (prediction_event_key IS NOT NULL);


--
-- Name: idx_predictions_publish_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_predictions_publish_state ON public.match_predictions USING btree (publish_state);


--
-- Name: idx_predictions_format; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_predictions_format ON public.match_predictions USING btree (format);


--
-- Name: idx_predictions_outcome; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_predictions_outcome ON public.match_predictions USING btree (actual_winner) WHERE (actual_winner IS NOT NULL);


--
-- Name: idx_predictions_prediction_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_predictions_prediction_time ON public.match_predictions USING btree (prediction_time DESC);


--
-- Name: idx_predictions_session_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_predictions_session_date ON public.match_predictions USING btree (session_date);


--
-- Name: idx_processed_endstats_filename; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processed_endstats_filename ON public.processed_endstats_files USING btree (filename);


--
-- Name: idx_processed_files_filename; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processed_files_filename ON public.processed_files USING btree (filename);


--
-- Name: idx_processed_files_success; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processed_files_success ON public.processed_files USING btree (success) WHERE (success = true);


--
-- Name: idx_processed_files_success_processed_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_processed_files_success_processed_at ON public.processed_files USING btree (processed_at) WHERE (success = true);


--
-- Name: idx_promotion_campaigns_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_promotion_campaigns_date ON public.availability_promotion_campaigns USING btree (campaign_date DESC);


--
-- Name: idx_promotion_campaigns_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_promotion_campaigns_status ON public.availability_promotion_campaigns USING btree (status);


--
-- Name: idx_promotion_jobs_due; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_promotion_jobs_due ON public.availability_promotion_jobs USING btree (status, run_at);


--
-- Name: idx_promotion_send_logs_campaign; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_promotion_send_logs_campaign ON public.availability_promotion_send_logs USING btree (campaign_id, created_at DESC);


--
-- Name: idx_prox_obj_run_action; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prox_obj_run_action ON public.proximity_objective_run USING btree (action_type);


--
-- Name: idx_prox_obj_run_engineer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prox_obj_run_engineer ON public.proximity_objective_run USING btree (engineer_guid);


--
-- Name: idx_prox_obj_run_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prox_obj_run_map ON public.proximity_objective_run USING btree (map_name);


--
-- Name: idx_prox_obj_run_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prox_obj_run_session ON public.proximity_objective_run USING btree (session_date);


--
-- Name: idx_prox_obj_run_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_prox_obj_run_type ON public.proximity_objective_run USING btree (run_type);


--
-- Name: idx_proximity_crossfire_opportunity_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_crossfire_opportunity_round_id ON public.proximity_crossfire_opportunity USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_proximity_crossfire_opportunity_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_crossfire_opportunity_round_lookup_unlinked ON public.proximity_crossfire_opportunity USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_proximity_lua_trade_kill_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_lua_trade_kill_round_id ON public.proximity_lua_trade_kill USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_proximity_lua_trade_kill_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_lua_trade_kill_round_lookup_unlinked ON public.proximity_lua_trade_kill USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_proximity_objective_focus_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_objective_focus_round_id ON public.proximity_objective_focus USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_proximity_objective_focus_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_objective_focus_round_lookup_unlinked ON public.proximity_objective_focus USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_proximity_reaction_metric_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_reaction_metric_round_id ON public.proximity_reaction_metric USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_proximity_reaction_metric_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_reaction_metric_round_lookup_unlinked ON public.proximity_reaction_metric USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_proximity_revive_session_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_revive_session_date ON public.proximity_revive USING btree (session_date);


--
-- Name: idx_proximity_spawn_timing_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_spawn_timing_round_id ON public.proximity_spawn_timing USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_proximity_spawn_timing_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_spawn_timing_round_lookup_unlinked ON public.proximity_spawn_timing USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_proximity_support_summary_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_support_summary_round_id ON public.proximity_support_summary USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_proximity_support_summary_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_support_summary_round_lookup_unlinked ON public.proximity_support_summary USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_proximity_team_cohesion_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_team_cohesion_round_id ON public.proximity_team_cohesion USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_proximity_team_cohesion_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_team_cohesion_round_lookup_unlinked ON public.proximity_team_cohesion USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_proximity_team_push_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_team_push_round_id ON public.proximity_team_push USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_proximity_team_push_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_team_push_round_lookup_unlinked ON public.proximity_team_push USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_proximity_trade_event_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_trade_event_round_id ON public.proximity_trade_event USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_proximity_trade_event_round_lookup_unlinked; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_trade_event_round_lookup_unlinked ON public.proximity_trade_event USING btree (map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE (round_id IS NULL);


--
-- Name: idx_proximity_weapon_accuracy_session_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_proximity_weapon_accuracy_session_date ON public.proximity_weapon_accuracy USING btree (session_date);


--
-- Name: idx_pst_session_killer_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pst_session_killer_canonical ON public.proximity_spawn_timing USING btree (session_date, killer_guid_canonical) WHERE (killer_guid_canonical IS NOT NULL);


--
-- Name: idx_pts_player_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_pts_player_canonical ON public.player_teamplay_stats USING btree (player_guid_canonical);


--
-- Name: idx_reaction_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reaction_class ON public.proximity_reaction_metric USING btree (target_class);


--
-- Name: idx_reaction_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reaction_session ON public.proximity_reaction_metric USING btree (session_date, round_number);


--
-- Name: idx_reaction_target; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_reaction_target ON public.proximity_reaction_metric USING btree (target_guid);


--
-- Name: idx_revive_medic; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revive_medic ON public.proximity_revive USING btree (medic_guid);


--
-- Name: idx_revive_revived; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revive_revived ON public.proximity_revive USING btree (revived_guid);


--
-- Name: idx_revive_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_revive_round ON public.proximity_revive USING btree (round_id);


--
-- Name: idx_round_assemblies_session_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_assemblies_session_map ON public.round_assemblies USING btree (gaming_session_id, map_name, map_play_seq);


--
-- Name: idx_round_assemblies_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_assemblies_status ON public.round_assemblies USING btree (status);


--
-- Name: idx_round_assembly_events_pending; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_assembly_events_pending ON public.round_assembly_events USING btree (attachment_status, source_type, map_name, round_number, event_at, id);


--
-- Name: idx_round_assembly_events_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_assembly_events_round_id ON public.round_assembly_events USING btree (round_id);


--
-- Name: idx_round_awards_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_awards_name ON public.round_awards USING btree (award_name);


--
-- Name: idx_round_awards_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_awards_player ON public.round_awards USING btree (player_guid);


--
-- Name: idx_round_awards_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_awards_round ON public.round_awards USING btree (round_id);


--
-- Name: idx_round_corr_match_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_corr_match_id ON public.round_correlations USING btree (match_id);


--
-- Name: idx_round_corr_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_corr_status ON public.round_correlations USING btree (status);


--
-- Name: idx_round_vs_stats_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_vs_stats_player ON public.round_vs_stats USING btree (player_guid);


--
-- Name: idx_round_vs_stats_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_vs_stats_round ON public.round_vs_stats USING btree (round_id);


--
-- Name: idx_round_vs_stats_subject; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_vs_stats_subject ON public.round_vs_stats USING btree (subject_guid);


--
-- Name: idx_round_vs_stats_subject_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_round_vs_stats_subject_round ON public.round_vs_stats USING btree (subject_guid, round_id);


--
-- Name: idx_rounds_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_date ON public.rounds USING btree (round_date);


--
-- Name: idx_rounds_end_reason; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_end_reason ON public.rounds USING btree (end_reason);


--
-- Name: idx_rounds_gaming_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_gaming_session ON public.rounds USING btree (gaming_session_id, map_name, round_number, round_status);


--
-- Name: idx_rounds_is_bot_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_is_bot_round ON public.rounds USING btree (is_bot_round);


--
-- Name: idx_rounds_map_round_date_time; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_map_round_date_time ON public.rounds USING btree (map_name, round_number, round_date, round_time);


--
-- Name: idx_rounds_map_round_end; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_map_round_end ON public.rounds USING btree (map_name, round_number, round_end_unix);


--
-- Name: idx_rounds_map_round_start; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_map_round_start ON public.rounds USING btree (map_name, round_number, round_start_unix);


--
-- Name: idx_rounds_score_confidence; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_score_confidence ON public.rounds USING btree (score_confidence);


--
-- Name: idx_rounds_session_map_seq; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_session_map_seq ON public.rounds USING btree (gaming_session_id, map_name, map_play_seq);


--
-- Name: idx_rounds_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_status ON public.rounds USING btree (round_status);


--
-- Name: idx_rounds_stopwatch_state; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_rounds_stopwatch_state ON public.rounds USING btree (round_stopwatch_state);


--
-- Name: idx_server_status_history_player_count; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_server_status_history_player_count ON public.server_status_history USING btree (player_count DESC) WHERE (online = true);


--
-- Name: idx_server_status_history_recorded_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_server_status_history_recorded_at ON public.server_status_history USING btree (recorded_at DESC);


--
-- Name: idx_session_results_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_results_date ON public.session_results USING btree (session_date DESC);


--
-- Name: idx_session_results_format; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_results_format ON public.session_results USING btree (format);


--
-- Name: idx_session_results_gaming_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_results_gaming_session ON public.session_results USING btree (gaming_session_id);


--
-- Name: idx_session_results_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_results_map ON public.session_results USING btree (map_name);


--
-- Name: idx_session_results_team1_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_results_team1_name ON public.session_results USING btree (team_1_name);


--
-- Name: idx_session_results_team2_name; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_results_team2_name ON public.session_results USING btree (team_2_name);


--
-- Name: idx_session_results_teams; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_results_teams ON public.session_results USING btree (team_1_guids, team_2_guids);


--
-- Name: idx_session_results_winner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_results_winner ON public.session_results USING btree (winning_team);


--
-- Name: idx_session_teams_gaming_session_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_session_teams_gaming_session_id ON public.session_teams USING btree (gaming_session_id);


--
-- Name: idx_ski_killer_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ski_killer_canonical ON public.storytelling_kill_impact USING btree (killer_guid_canonical);


--
-- Name: idx_ski_session_killer_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_ski_session_killer_canonical ON public.storytelling_kill_impact USING btree (session_date, killer_guid_canonical) WHERE (killer_guid_canonical IS NOT NULL);


--
-- Name: idx_skill_history_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_skill_history_date ON public.player_skill_history USING btree (calculated_at DESC);


--
-- Name: idx_skill_history_guid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_skill_history_guid ON public.player_skill_history USING btree (player_guid);


--
-- Name: idx_skill_history_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_skill_history_map ON public.player_skill_history USING btree (player_guid, session_date, map_name) WHERE (scope = 'map'::text);


--
-- Name: idx_skill_history_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_skill_history_session ON public.player_skill_history USING btree (player_guid, session_date DESC) WHERE (scope = 'session'::text);


--
-- Name: idx_skill_ratings_rating; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_skill_ratings_rating ON public.player_skill_ratings USING btree (et_rating DESC);


--
-- Name: idx_spawn_timing_killer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_spawn_timing_killer ON public.proximity_spawn_timing USING btree (killer_guid);


--
-- Name: idx_spawn_timing_score; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_spawn_timing_score ON public.proximity_spawn_timing USING btree (spawn_timing_score DESC);


--
-- Name: idx_spawn_timing_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_spawn_timing_session ON public.proximity_spawn_timing USING btree (session_date, round_number);


--
-- Name: idx_srs_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_srs_date ON public.session_round_scores USING btree (round_date);


--
-- Name: idx_srs_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_srs_session ON public.session_round_scores USING btree (gaming_session_id);


--
-- Name: idx_st_killer_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_st_killer_canonical ON public.proximity_spawn_timing USING btree (killer_guid_canonical);


--
-- Name: idx_subscription_preferences_allow_promotions; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_subscription_preferences_allow_promotions ON public.subscription_preferences USING btree (allow_promotions);


--
-- Name: idx_support_summary_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_support_summary_session ON public.proximity_support_summary USING btree (session_date, round_number);


--
-- Name: idx_team_cohesion_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_cohesion_session ON public.proximity_team_cohesion USING btree (session_date, round_number);


--
-- Name: idx_team_pool_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_pool_active ON public.team_pool USING btree (active) WHERE (active = true);


--
-- Name: idx_team_push_quality; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_push_quality ON public.proximity_team_push USING btree (push_quality DESC);


--
-- Name: idx_team_push_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_team_push_session ON public.proximity_team_push USING btree (session_date, round_number);


--
-- Name: idx_teamplay_crossfire; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teamplay_crossfire ON public.player_teamplay_stats USING btree (crossfire_kills DESC);


--
-- Name: idx_teamplay_guid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_teamplay_guid ON public.player_teamplay_stats USING btree (player_guid);


--
-- Name: idx_tk_trader_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_tk_trader_canonical ON public.proximity_lua_trade_kill USING btree (trader_guid_canonical);


--
-- Name: idx_track_class; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_track_class ON public.player_track USING btree (player_class);


--
-- Name: idx_track_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_track_map ON public.player_track USING btree (map_name);


--
-- Name: idx_track_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_track_player ON public.player_track USING btree (player_guid);


--
-- Name: idx_track_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_track_session ON public.player_track USING btree (session_date, round_number);


--
-- Name: idx_trade_event_killer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trade_event_killer ON public.proximity_trade_event USING btree (killer_guid);


--
-- Name: idx_trade_event_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trade_event_session ON public.proximity_trade_event USING btree (session_date, round_number);


--
-- Name: idx_trade_event_victim; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_trade_event_victim ON public.proximity_trade_event USING btree (victim_guid);


--
-- Name: idx_upload_tags_tag; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_upload_tags_tag ON public.upload_tags USING btree (tag);


--
-- Name: idx_upload_tags_upload; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_upload_tags_upload ON public.upload_tags USING btree (upload_id);


--
-- Name: idx_uploads_category; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_uploads_category ON public.uploads USING btree (category);


--
-- Name: idx_uploads_created_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_uploads_created_at ON public.uploads USING btree (created_at DESC);


--
-- Name: idx_uploads_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_uploads_hash ON public.uploads USING btree (content_hash_sha256);


--
-- Name: idx_uploads_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_uploads_status ON public.uploads USING btree (status);


--
-- Name: idx_uploads_uploader; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_uploads_uploader ON public.uploads USING btree (uploader_discord_id);


--
-- Name: idx_user_permissions_discord_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_permissions_discord_id ON public.user_permissions USING btree (discord_id);


--
-- Name: idx_user_permissions_tier; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_permissions_tier ON public.user_permissions USING btree (tier);


--
-- Name: idx_user_player_links_player_guid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_user_player_links_player_guid ON public.user_player_links USING btree (player_guid);


--
-- Name: idx_vehicle_progress_map; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_progress_map ON public.proximity_vehicle_progress USING btree (map_name);


--
-- Name: idx_vehicle_progress_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_progress_round_id ON public.proximity_vehicle_progress USING btree (round_id) WHERE (round_id IS NOT NULL);


--
-- Name: idx_vehicle_progress_session; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_progress_session ON public.proximity_vehicle_progress USING btree (session_date, round_number, round_start_unix);


--
-- Name: idx_vehicle_progress_vehicle; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vehicle_progress_vehicle ON public.proximity_vehicle_progress USING btree (vehicle_name);


--
-- Name: idx_voice_members_active; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voice_members_active ON public.voice_members USING btree (discord_id) WHERE (left_at IS NULL);


--
-- Name: idx_voice_members_joined_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voice_members_joined_at ON public.voice_members USING btree (joined_at DESC);


--
-- Name: idx_voice_status_history_first_joiner; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voice_status_history_first_joiner ON public.voice_status_history USING btree (first_joiner_id);


--
-- Name: idx_voice_status_history_recorded_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voice_status_history_recorded_at ON public.voice_status_history USING btree (recorded_at DESC);


--
-- Name: idx_weapon_accuracy_map_weapon; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weapon_accuracy_map_weapon ON public.proximity_weapon_accuracy USING btree (map_name, weapon_id);


--
-- Name: idx_weapon_accuracy_player; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weapon_accuracy_player ON public.proximity_weapon_accuracy USING btree (player_guid);


--
-- Name: idx_weapon_accuracy_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weapon_accuracy_round ON public.proximity_weapon_accuracy USING btree (round_id);


--
-- Name: idx_weapon_stats_round; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_weapon_stats_round ON public.weapon_comprehensive_stats USING btree (round_id);


--
-- Name: round_correlations_r1_r2_unique; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX round_correlations_r1_r2_unique ON public.round_correlations USING btree (r1_round_id, r2_round_id) WHERE ((r1_round_id IS NOT NULL) AND (r2_round_id IS NOT NULL));


--
-- Name: uniq_rounds_canonical_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uniq_rounds_canonical_id ON public.rounds USING btree (round_canonical_id) WHERE (round_canonical_id IS NOT NULL);


--
-- Name: INDEX uniq_rounds_canonical_id; Type: COMMENT; Schema: public; Owner: -
--

COMMENT ON INDEX public.uniq_rounds_canonical_id IS 'UNIQUE partial index on round_canonical_id (NULL rows excluded). Enables INSERT ... ON CONFLICT (round_canonical_id) DO UPDATE pattern in Phase 3 layer B. See docs/ADR_round_canonical_id.md.';


--
-- Name: uq_processed_endstats_round_id; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX uq_processed_endstats_round_id ON public.processed_endstats_files USING btree (round_id) WHERE ((round_id IS NOT NULL) AND (success = true));


--
-- Name: proximity_combat_position trg_cp_canonical; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_cp_canonical BEFORE INSERT OR UPDATE ON public.proximity_combat_position FOR EACH ROW EXECUTE FUNCTION public.trg_cp_canonical();


--
-- Name: proximity_kill_outcome trg_ko_canonical; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ko_canonical BEFORE INSERT OR UPDATE ON public.proximity_kill_outcome FOR EACH ROW EXECUTE FUNCTION public.trg_ko_canonical();


--
-- Name: player_teamplay_stats trg_pts_canonical; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_pts_canonical BEFORE INSERT OR UPDATE ON public.player_teamplay_stats FOR EACH ROW EXECUTE FUNCTION public.trg_pts_canonical();


--
-- Name: storytelling_kill_impact trg_ski_canonical; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_ski_canonical BEFORE INSERT OR UPDATE ON public.storytelling_kill_impact FOR EACH ROW EXECUTE FUNCTION public.trg_ski_canonical();


--
-- Name: proximity_spawn_timing trg_st_canonical; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_st_canonical BEFORE INSERT OR UPDATE ON public.proximity_spawn_timing FOR EACH ROW EXECUTE FUNCTION public.trg_st_canonical();


--
-- Name: proximity_lua_trade_kill trg_tk_canonical; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_tk_canonical BEFORE INSERT OR UPDATE ON public.proximity_lua_trade_kill FOR EACH ROW EXECUTE FUNCTION public.trg_tk_canonical();


--
-- Name: availability_promotion_jobs availability_promotion_jobs_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_jobs
    ADD CONSTRAINT availability_promotion_jobs_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.availability_promotion_campaigns(id) ON DELETE CASCADE;


--
-- Name: availability_promotion_send_logs availability_promotion_send_logs_campaign_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_send_logs
    ADD CONSTRAINT availability_promotion_send_logs_campaign_id_fkey FOREIGN KEY (campaign_id) REFERENCES public.availability_promotion_campaigns(id) ON DELETE CASCADE;


--
-- Name: availability_promotion_send_logs availability_promotion_send_logs_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.availability_promotion_send_logs
    ADD CONSTRAINT availability_promotion_send_logs_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.availability_promotion_jobs(id) ON DELETE SET NULL;


--
-- Name: discord_accounts discord_accounts_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.discord_accounts
    ADD CONSTRAINT discord_accounts_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.website_users(id) ON DELETE CASCADE;


--
-- Name: combat_engagement fk_combat_engagement_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.combat_engagement
    ADD CONSTRAINT fk_combat_engagement_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: player_track fk_player_track_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_track
    ADD CONSTRAINT fk_player_track_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_crossfire_opportunity fk_proximity_crossfire_opportunity_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_crossfire_opportunity
    ADD CONSTRAINT fk_proximity_crossfire_opportunity_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_lua_trade_kill fk_proximity_lua_trade_kill_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_lua_trade_kill
    ADD CONSTRAINT fk_proximity_lua_trade_kill_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_objective_focus fk_proximity_objective_focus_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_objective_focus
    ADD CONSTRAINT fk_proximity_objective_focus_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_reaction_metric fk_proximity_reaction_metric_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_reaction_metric
    ADD CONSTRAINT fk_proximity_reaction_metric_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL NOT VALID;


--
-- Name: proximity_spawn_timing fk_proximity_spawn_timing_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_spawn_timing
    ADD CONSTRAINT fk_proximity_spawn_timing_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_support_summary fk_proximity_support_summary_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_support_summary
    ADD CONSTRAINT fk_proximity_support_summary_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_team_cohesion fk_proximity_team_cohesion_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_team_cohesion
    ADD CONSTRAINT fk_proximity_team_cohesion_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_team_push fk_proximity_team_push_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_team_push
    ADD CONSTRAINT fk_proximity_team_push_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_trade_event fk_proximity_trade_event_round_id; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_trade_event
    ADD CONSTRAINT fk_proximity_trade_event_round_id FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: greatshot_analysis greatshot_analysis_demo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.greatshot_analysis
    ADD CONSTRAINT greatshot_analysis_demo_id_fkey FOREIGN KEY (demo_id) REFERENCES public.greatshot_demos(id) ON DELETE CASCADE;


--
-- Name: greatshot_highlights greatshot_highlights_demo_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.greatshot_highlights
    ADD CONSTRAINT greatshot_highlights_demo_id_fkey FOREIGN KEY (demo_id) REFERENCES public.greatshot_demos(id) ON DELETE CASCADE;


--
-- Name: greatshot_renders greatshot_renders_highlight_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.greatshot_renders
    ADD CONSTRAINT greatshot_renders_highlight_id_fkey FOREIGN KEY (highlight_id) REFERENCES public.greatshot_highlights(id) ON DELETE CASCADE;


--
-- Name: planning_sessions planning_sessions_created_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_sessions
    ADD CONSTRAINT planning_sessions_created_by_user_id_fkey FOREIGN KEY (created_by_user_id) REFERENCES public.website_users(id) ON DELETE RESTRICT;


--
-- Name: planning_team_members planning_team_members_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_members
    ADD CONSTRAINT planning_team_members_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.planning_sessions(id) ON DELETE CASCADE;


--
-- Name: planning_team_members planning_team_members_team_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_members
    ADD CONSTRAINT planning_team_members_team_id_fkey FOREIGN KEY (team_id) REFERENCES public.planning_teams(id) ON DELETE CASCADE;


--
-- Name: planning_team_members planning_team_members_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_members
    ADD CONSTRAINT planning_team_members_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.website_users(id) ON DELETE CASCADE;


--
-- Name: planning_team_names planning_team_names_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_names
    ADD CONSTRAINT planning_team_names_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.planning_sessions(id) ON DELETE CASCADE;


--
-- Name: planning_team_names planning_team_names_suggested_by_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_team_names
    ADD CONSTRAINT planning_team_names_suggested_by_user_id_fkey FOREIGN KEY (suggested_by_user_id) REFERENCES public.website_users(id) ON DELETE RESTRICT;


--
-- Name: planning_teams planning_teams_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_teams
    ADD CONSTRAINT planning_teams_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.planning_sessions(id) ON DELETE CASCADE;


--
-- Name: planning_votes planning_votes_session_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_votes
    ADD CONSTRAINT planning_votes_session_id_fkey FOREIGN KEY (session_id) REFERENCES public.planning_sessions(id) ON DELETE CASCADE;


--
-- Name: planning_votes planning_votes_suggestion_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_votes
    ADD CONSTRAINT planning_votes_suggestion_id_fkey FOREIGN KEY (suggestion_id) REFERENCES public.planning_team_names(id) ON DELETE CASCADE;


--
-- Name: planning_votes planning_votes_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.planning_votes
    ADD CONSTRAINT planning_votes_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.website_users(id) ON DELETE CASCADE;


--
-- Name: player_comprehensive_stats player_comprehensive_stats_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.player_comprehensive_stats
    ADD CONSTRAINT player_comprehensive_stats_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id);


--
-- Name: poll_responses poll_responses_poll_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.poll_responses
    ADD CONSTRAINT poll_responses_poll_id_fkey FOREIGN KEY (poll_id) REFERENCES public.daily_polls(id) ON DELETE CASCADE;


--
-- Name: processed_endstats_files processed_endstats_files_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.processed_endstats_files
    ADD CONSTRAINT processed_endstats_files_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_carrier_event proximity_carrier_event_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_event
    ADD CONSTRAINT proximity_carrier_event_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_carrier_kill proximity_carrier_kill_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_kill
    ADD CONSTRAINT proximity_carrier_kill_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_carrier_return proximity_carrier_return_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_carrier_return
    ADD CONSTRAINT proximity_carrier_return_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_combat_position proximity_combat_position_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_combat_position
    ADD CONSTRAINT proximity_combat_position_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_construction_event proximity_construction_event_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_construction_event
    ADD CONSTRAINT proximity_construction_event_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_escort_credit proximity_escort_credit_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_escort_credit
    ADD CONSTRAINT proximity_escort_credit_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_focus_fire proximity_focus_fire_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_focus_fire
    ADD CONSTRAINT proximity_focus_fire_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id);


--
-- Name: proximity_hit_region proximity_hit_region_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_hit_region
    ADD CONSTRAINT proximity_hit_region_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_kill_outcome proximity_kill_outcome_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_kill_outcome
    ADD CONSTRAINT proximity_kill_outcome_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id);


--
-- Name: proximity_objective_run proximity_objective_run_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_objective_run
    ADD CONSTRAINT proximity_objective_run_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: proximity_vehicle_progress proximity_vehicle_progress_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.proximity_vehicle_progress
    ADD CONSTRAINT proximity_vehicle_progress_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: round_assemblies round_assemblies_r1_lua_teams_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assemblies
    ADD CONSTRAINT round_assemblies_r1_lua_teams_id_fkey FOREIGN KEY (r1_lua_teams_id) REFERENCES public.lua_round_teams(id) ON DELETE SET NULL;


--
-- Name: round_assemblies round_assemblies_r1_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assemblies
    ADD CONSTRAINT round_assemblies_r1_round_id_fkey FOREIGN KEY (r1_round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: round_assemblies round_assemblies_r2_lua_teams_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assemblies
    ADD CONSTRAINT round_assemblies_r2_lua_teams_id_fkey FOREIGN KEY (r2_lua_teams_id) REFERENCES public.lua_round_teams(id) ON DELETE SET NULL;


--
-- Name: round_assemblies round_assemblies_r2_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assemblies
    ADD CONSTRAINT round_assemblies_r2_round_id_fkey FOREIGN KEY (r2_round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: round_assemblies round_assemblies_summary_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assemblies
    ADD CONSTRAINT round_assemblies_summary_round_id_fkey FOREIGN KEY (summary_round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: round_assembly_events round_assembly_events_assembly_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assembly_events
    ADD CONSTRAINT round_assembly_events_assembly_id_fkey FOREIGN KEY (assembly_id) REFERENCES public.round_assemblies(id) ON DELETE SET NULL;


--
-- Name: round_assembly_events round_assembly_events_lua_teams_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assembly_events
    ADD CONSTRAINT round_assembly_events_lua_teams_id_fkey FOREIGN KEY (lua_teams_id) REFERENCES public.lua_round_teams(id) ON DELETE SET NULL;


--
-- Name: round_assembly_events round_assembly_events_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_assembly_events
    ADD CONSTRAINT round_assembly_events_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL;


--
-- Name: round_awards round_awards_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_awards
    ADD CONSTRAINT round_awards_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE CASCADE;


--
-- Name: round_correlations round_correlations_r1_lua_teams_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_correlations
    ADD CONSTRAINT round_correlations_r1_lua_teams_id_fkey FOREIGN KEY (r1_lua_teams_id) REFERENCES public.lua_round_teams(id);


--
-- Name: round_correlations round_correlations_r1_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_correlations
    ADD CONSTRAINT round_correlations_r1_round_id_fkey FOREIGN KEY (r1_round_id) REFERENCES public.rounds(id);


--
-- Name: round_correlations round_correlations_r2_lua_teams_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_correlations
    ADD CONSTRAINT round_correlations_r2_lua_teams_id_fkey FOREIGN KEY (r2_lua_teams_id) REFERENCES public.lua_round_teams(id);


--
-- Name: round_correlations round_correlations_r2_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_correlations
    ADD CONSTRAINT round_correlations_r2_round_id_fkey FOREIGN KEY (r2_round_id) REFERENCES public.rounds(id);


--
-- Name: round_correlations round_correlations_summary_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_correlations
    ADD CONSTRAINT round_correlations_summary_round_id_fkey FOREIGN KEY (summary_round_id) REFERENCES public.rounds(id);


--
-- Name: round_vs_stats round_vs_stats_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.round_vs_stats
    ADD CONSTRAINT round_vs_stats_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE CASCADE;


--
-- Name: storytelling_kill_impact storytelling_kill_impact_kill_outcome_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.storytelling_kill_impact
    ADD CONSTRAINT storytelling_kill_impact_kill_outcome_id_fkey FOREIGN KEY (kill_outcome_id) REFERENCES public.proximity_kill_outcome(id) ON DELETE CASCADE;


--
-- Name: upload_tags upload_tags_upload_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.upload_tags
    ADD CONSTRAINT upload_tags_upload_id_fkey FOREIGN KEY (upload_id) REFERENCES public.uploads(id) ON DELETE CASCADE;


--
-- Name: user_player_links user_player_links_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.user_player_links
    ADD CONSTRAINT user_player_links_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.website_users(id) ON DELETE CASCADE;


--
-- Name: weapon_comprehensive_stats weapon_comprehensive_stats_round_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.weapon_comprehensive_stats
    ADD CONSTRAINT weapon_comprehensive_stats_round_id_fkey FOREIGN KEY (round_id) REFERENCES public.rounds(id);


--
-- PostgreSQL database dump complete
--



-- ===== VISION_2026 Sprint S3 (migration website/009) =====
CREATE TABLE IF NOT EXISTS session_mvp_votes (
    id BIGSERIAL PRIMARY KEY,
    gaming_session_id INTEGER NOT NULL,
    voter_user_id BIGINT NOT NULL REFERENCES website_users(id) ON DELETE CASCADE,
    nominated_guid TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (gaming_session_id, voter_user_id)
);
CREATE INDEX IF NOT EXISTS idx_session_mvp_votes_session ON session_mvp_votes (gaming_session_id);
CREATE INDEX IF NOT EXISTS idx_session_mvp_votes_nominee ON session_mvp_votes (gaming_session_id, nominated_guid);
CREATE TABLE IF NOT EXISTS weekly_challenges (
    id BIGSERIAL PRIMARY KEY,
    week_start_date DATE NOT NULL UNIQUE,
    title TEXT NOT NULL,
    description TEXT,
    created_by_user_id BIGINT REFERENCES website_users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_weekly_challenges_week ON weekly_challenges (week_start_date DESC);

-- ===== VISION_2026 Sprint S4 (migration website/010) =====
CREATE TABLE IF NOT EXISTS season_awards (
    id BIGSERIAL PRIMARY KEY,
    season_id TEXT NOT NULL,
    award_key TEXT NOT NULL,
    player_guid TEXT NOT NULL,
    player_name TEXT,
    value_text TEXT,
    value_num REAL,
    source JSONB DEFAULT '{}'::jsonb,
    created_by_user_id BIGINT REFERENCES website_users(id) ON DELETE SET NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (season_id, award_key, player_guid)
);
CREATE INDEX IF NOT EXISTS idx_season_awards_season ON season_awards (season_id, award_key);
CREATE TABLE IF NOT EXISTS user_points (
    user_id BIGINT PRIMARY KEY REFERENCES website_users(id) ON DELETE CASCADE,
    balance INTEGER NOT NULL DEFAULT 100,
    lifetime_earned INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE IF NOT EXISTS parimutuel_markets (
    id BIGSERIAL PRIMARY KEY,
    gaming_session_id INTEGER,
    session_date DATE,
    market_type TEXT NOT NULL DEFAULT 'session_winner',
    team_a_label TEXT NOT NULL DEFAULT 'Team A',
    team_b_label TEXT NOT NULL DEFAULT 'Team B',
    status TEXT NOT NULL DEFAULT 'open',
    outcome TEXT,
    total_pool INTEGER NOT NULL DEFAULT 0,
    created_by_user_id BIGINT REFERENCES website_users(id) ON DELETE SET NULL,
    opens_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    closes_at TIMESTAMP,
    settled_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_parimutuel_markets_status ON parimutuel_markets (status, id DESC);
CREATE TABLE IF NOT EXISTS parimutuel_bets (
    id BIGSERIAL PRIMARY KEY,
    market_id BIGINT NOT NULL REFERENCES parimutuel_markets(id) ON DELETE CASCADE,
    user_id BIGINT NOT NULL REFERENCES website_users(id) ON DELETE CASCADE,
    choice TEXT NOT NULL,
    amount INTEGER NOT NULL,
    payout INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'open',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE (market_id, user_id)
);
CREATE INDEX IF NOT EXISTS idx_parimutuel_bets_market ON parimutuel_bets (market_id, choice);
