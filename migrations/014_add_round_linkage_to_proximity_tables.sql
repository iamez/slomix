-- Add canonical round linkage columns to proximity tables.
-- This enables exact cross-source linking via rounds.id while preserving
-- source-native round timestamps (R1/R2 remain physically distinct rounds).
--
-- NOTE: Tables owned by a different DB role (e.g. proximity_reaction_metric
-- owned by website_app) will be skipped with a NOTICE when run as etlegacy_user.
-- Re-run as that table's owner or as a superuser to complete linkage for those tables.

BEGIN;

CREATE INDEX IF NOT EXISTS idx_rounds_map_round_start
    ON rounds(map_name, round_number, round_start_unix);

CREATE INDEX IF NOT EXISTS idx_rounds_map_round_end
    ON rounds(map_name, round_number, round_end_unix);

CREATE INDEX IF NOT EXISTS idx_rounds_map_round_date_time
    ON rounds(map_name, round_number, round_date, round_time);

DO $$
DECLARE
    t TEXT;
    fk_name TEXT;
    idx_round_id TEXT;
    idx_lookup_unlinked TEXT;
    prox_tables TEXT[] := ARRAY[
        'combat_engagement',
        'player_track',
        'proximity_trade_event',
        'proximity_support_summary',
        'proximity_objective_focus',
        'proximity_reaction_metric',
        'proximity_spawn_timing',
        'proximity_team_cohesion',
        'proximity_crossfire_opportunity',
        'proximity_team_push',
        'proximity_lua_trade_kill'
    ];
BEGIN
    FOREACH t IN ARRAY prox_tables LOOP
        IF to_regclass('public.' || t) IS NULL THEN
            CONTINUE;
        END IF;

        -- Wrap each table in its own savepoint so a permission failure on one
        -- table does not roll back progress on all others.
        BEGIN
            EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS round_id INTEGER', t);
            EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS round_link_source VARCHAR(32)', t);
            EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS round_link_reason VARCHAR(64)', t);
            EXECUTE format('ALTER TABLE public.%I ADD COLUMN IF NOT EXISTS round_linked_at TIMESTAMPTZ', t);

            idx_round_id := format('idx_%s_round_id', t);
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS %I ON public.%I(round_id) WHERE round_id IS NOT NULL',
                idx_round_id,
                t
            );

            idx_lookup_unlinked := format('idx_%s_round_lookup_unlinked', t);
            EXECUTE format(
                'CREATE INDEX IF NOT EXISTS %I ON public.%I(map_name, round_number, round_start_unix, round_end_unix, session_date) WHERE round_id IS NULL',
                idx_lookup_unlinked,
                t
            );

            fk_name := format('fk_%s_round_id', t);
            IF NOT EXISTS (
                SELECT 1
                FROM pg_constraint c
                JOIN pg_class r ON r.oid = c.conrelid
                JOIN pg_namespace n ON n.oid = r.relnamespace
                WHERE n.nspname = 'public'
                  AND r.relname = t
                  AND c.conname = fk_name
            ) THEN
                EXECUTE format(
                    'ALTER TABLE public.%I ADD CONSTRAINT %I FOREIGN KEY (round_id) REFERENCES public.rounds(id) ON DELETE SET NULL NOT VALID',
                    t,
                    fk_name
                );
            END IF;

        EXCEPTION WHEN insufficient_privilege THEN
            RAISE NOTICE 'Skipping % — insufficient privilege (run as table owner or superuser to complete)', t;
        END;

    END LOOP;
END $$;

-- Keep schema aligned with parser conflict target.
DO $$
BEGIN
    IF to_regclass('public.proximity_objective_focus') IS NOT NULL THEN
        ALTER TABLE public.proximity_objective_focus
            DROP CONSTRAINT IF EXISTS proximity_objective_focus_session_date_round_number_player_guid_key;
        ALTER TABLE public.proximity_objective_focus
            DROP CONSTRAINT IF EXISTS proximity_objective_focus_round_scope_unique;
        ALTER TABLE public.proximity_objective_focus
            ADD CONSTRAINT proximity_objective_focus_round_scope_unique
            UNIQUE (session_date, round_number, round_start_unix, player_guid);
    END IF;
END $$;

COMMIT;

DO $$
DECLARE
    t TEXT;
    fk_name TEXT;
    prox_tables TEXT[] := ARRAY[
        'combat_engagement',
        'player_track',
        'proximity_trade_event',
        'proximity_support_summary',
        'proximity_objective_focus',
        'proximity_reaction_metric',
        'proximity_spawn_timing',
        'proximity_team_cohesion',
        'proximity_crossfire_opportunity',
        'proximity_team_push',
        'proximity_lua_trade_kill'
    ];
BEGIN
    FOREACH t IN ARRAY prox_tables LOOP
        IF to_regclass('public.' || t) IS NULL THEN
            CONTINUE;
        END IF;
        fk_name := format('fk_%s_round_id', t);
        IF EXISTS (
            SELECT 1
            FROM pg_constraint c
            JOIN pg_class r ON r.oid = c.conrelid
            JOIN pg_namespace n ON n.oid = r.relnamespace
            WHERE n.nspname = 'public'
              AND r.relname = t
              AND c.conname = fk_name
        ) THEN
            BEGIN
                EXECUTE format('ALTER TABLE public.%I VALIDATE CONSTRAINT %I', t, fk_name);
            EXCEPTION WHEN insufficient_privilege THEN
                RAISE NOTICE 'Skipping VALIDATE CONSTRAINT on % — insufficient privilege', t;
            END;
        END IF;
    END LOOP;
END $$;
