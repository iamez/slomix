-- WS1C-003: Remove legacy UNIQUE constraints that conflict with round_start_unix keys.
-- Safe to run multiple times.

-- 1) Drop legacy player_track unique key:
--    (session_date, round_number, player_guid, spawn_time_ms)
DO $$
DECLARE
    c RECORD;
BEGIN
    IF to_regclass('public.player_track') IS NULL THEN
        RETURN;
    END IF;

    FOR c IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS ord(attnum, ord_pos) ON TRUE
        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ord.attnum
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'player_track'
          AND con.contype = 'u'
        GROUP BY con.conname
        HAVING array_agg(att.attname::text ORDER BY ord.ord_pos) = ARRAY[
            'session_date',
            'round_number',
            'player_guid',
            'spawn_time_ms'
        ]
    LOOP
        EXECUTE format(
            'ALTER TABLE public.player_track DROP CONSTRAINT IF EXISTS %I',
            c.conname
        );
    END LOOP;
END $$;

-- 2) Drop legacy proximity_objective_focus unique key:
--    (session_date, round_number, player_guid)
DO $$
DECLARE
    c RECORD;
BEGIN
    IF to_regclass('public.proximity_objective_focus') IS NULL THEN
        RETURN;
    END IF;

    FOR c IN
        SELECT con.conname
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS ord(attnum, ord_pos) ON TRUE
        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ord.attnum
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'proximity_objective_focus'
          AND con.contype = 'u'
        GROUP BY con.conname
        HAVING array_agg(att.attname::text ORDER BY ord.ord_pos) = ARRAY[
            'session_date',
            'round_number',
            'player_guid'
        ]
    LOOP
        EXECUTE format(
            'ALTER TABLE public.proximity_objective_focus DROP CONSTRAINT IF EXISTS %I',
            c.conname
        );
    END LOOP;
END $$;

-- 3) Ensure canonical round_start_unix unique key exists for player_track.
DO $$
BEGIN
    IF to_regclass('public.player_track') IS NULL THEN
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS ord(attnum, ord_pos) ON TRUE
        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ord.attnum
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'player_track'
          AND con.contype = 'u'
        GROUP BY con.oid
        HAVING array_agg(att.attname::text ORDER BY ord.ord_pos) = ARRAY[
            'session_date',
            'round_number',
            'round_start_unix',
            'player_guid',
            'spawn_time_ms'
        ]
    ) THEN
        ALTER TABLE public.player_track
            ADD CONSTRAINT uq_player_track_round_start
            UNIQUE (session_date, round_number, round_start_unix, player_guid, spawn_time_ms);
    END IF;
END $$;

-- 4) Ensure canonical round_start_unix unique key exists for proximity_objective_focus.
DO $$
BEGIN
    IF to_regclass('public.proximity_objective_focus') IS NULL THEN
        RETURN;
    END IF;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint con
        JOIN pg_class rel ON rel.oid = con.conrelid
        JOIN pg_namespace nsp ON nsp.oid = rel.relnamespace
        JOIN LATERAL unnest(con.conkey) WITH ORDINALITY AS ord(attnum, ord_pos) ON TRUE
        JOIN pg_attribute att ON att.attrelid = rel.oid AND att.attnum = ord.attnum
        WHERE nsp.nspname = 'public'
          AND rel.relname = 'proximity_objective_focus'
          AND con.contype = 'u'
        GROUP BY con.oid
        HAVING array_agg(att.attname::text ORDER BY ord.ord_pos) = ARRAY[
            'session_date',
            'round_number',
            'round_start_unix',
            'player_guid'
        ]
    ) THEN
        ALTER TABLE public.proximity_objective_focus
            ADD CONSTRAINT uq_prox_objective_focus_round_start
            UNIQUE (session_date, round_number, round_start_unix, player_guid);
    END IF;
END $$;
