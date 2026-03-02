-- Backfill round_id for proximity tables.
-- Rerunnable and non-destructive: only touches rows where round_id IS NULL.
-- Tables that were skipped in migration 014 due to insufficient privilege
-- (e.g. proximity_reaction_metric owned by website_app) are silently skipped here too.

DO $$
DECLARE
    t TEXT;
    window_seconds INTEGER := 2700; -- 45 minutes
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

        -- Skip tables that don't yet have the round_id column (e.g. 014 was skipped for that table).
        IF NOT EXISTS (
            SELECT 1 FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = t AND column_name = 'round_id'
        ) THEN
            RAISE NOTICE 'Skipping backfill for % — round_id column not present (re-run migration 014 as table owner)', t;
            CONTINUE;
        END IF;

        -- Pass 1: exact round_start_unix (single-candidate rows only)
        EXECUTE format($sql$
            WITH c AS (
                SELECT
                    p.id AS prox_id,
                    r.id AS round_id,
                    COUNT(*) OVER (PARTITION BY p.id) AS candidate_count,
                    ROW_NUMBER() OVER (
                        PARTITION BY p.id
                        ORDER BY r.created_at DESC, r.id DESC
                    ) AS rn
                FROM public.%I p
                JOIN public.rounds r
                  ON r.map_name = p.map_name
                 AND r.round_number = p.round_number
                 AND p.round_start_unix > 0
                 AND r.round_start_unix = p.round_start_unix
                WHERE p.round_id IS NULL
            )
            UPDATE public.%I p
               SET round_id = c.round_id,
                   round_link_source = 'exact_round_start',
                   round_link_reason = NULL,
                   round_linked_at = NOW()
            FROM c
            WHERE p.id = c.prox_id
              AND c.rn = 1
              AND c.candidate_count = 1
        $sql$, t, t);

        -- Pass 2: exact round_end_unix fallback (single-candidate rows only)
        EXECUTE format($sql$
            WITH c AS (
                SELECT
                    p.id AS prox_id,
                    r.id AS round_id,
                    COUNT(*) OVER (PARTITION BY p.id) AS candidate_count,
                    ROW_NUMBER() OVER (
                        PARTITION BY p.id
                        ORDER BY r.created_at DESC, r.id DESC
                    ) AS rn
                FROM public.%I p
                JOIN public.rounds r
                  ON r.map_name = p.map_name
                 AND r.round_number = p.round_number
                 AND p.round_end_unix > 0
                 AND r.round_end_unix = p.round_end_unix
                WHERE p.round_id IS NULL
            )
            UPDATE public.%I p
               SET round_id = c.round_id,
                   round_link_source = 'exact_round_end',
                   round_link_reason = NULL,
                   round_linked_at = NOW()
            FROM c
            WHERE p.id = c.prox_id
              AND c.rn = 1
              AND c.candidate_count = 1
        $sql$, t, t);

        -- Pass 3: nearest round time in same map+round within window (single-candidate rows only)
        EXECUTE format($sql$
            WITH ranked AS (
                SELECT
                    p.id AS prox_id,
                    r.id AS round_id,
                    ABS(
                        COALESCE(NULLIF(r.round_end_unix, 0), NULLIF(r.round_start_unix, 0))
                        - COALESCE(NULLIF(p.round_end_unix, 0), NULLIF(p.round_start_unix, 0))
                    ) AS diff_seconds,
                    COUNT(*) OVER (PARTITION BY p.id) AS candidate_count,
                    ROW_NUMBER() OVER (
                        PARTITION BY p.id
                        ORDER BY
                            ABS(
                                COALESCE(NULLIF(r.round_end_unix, 0), NULLIF(r.round_start_unix, 0))
                                - COALESCE(NULLIF(p.round_end_unix, 0), NULLIF(p.round_start_unix, 0))
                            ),
                            r.created_at DESC,
                            r.id DESC
                    ) AS rn
                FROM public.%I p
                JOIN public.rounds r
                  ON r.map_name = p.map_name
                 AND r.round_number = p.round_number
                WHERE p.round_id IS NULL
                  AND COALESCE(NULLIF(p.round_end_unix, 0), NULLIF(p.round_start_unix, 0)) IS NOT NULL
                  AND COALESCE(NULLIF(r.round_end_unix, 0), NULLIF(r.round_start_unix, 0)) IS NOT NULL
                  AND ABS(
                        COALESCE(NULLIF(r.round_end_unix, 0), NULLIF(r.round_start_unix, 0))
                        - COALESCE(NULLIF(p.round_end_unix, 0), NULLIF(p.round_start_unix, 0))
                  ) <= %s
                  AND (
                        r.round_date IS NULL
                     OR r.round_date = p.session_date::text
                     OR r.round_date = (p.session_date - INTERVAL '1 day')::date::text
                     OR r.round_date = (p.session_date + INTERVAL '1 day')::date::text
                  )
            )
            UPDATE public.%I p
               SET round_id = r.round_id,
                   round_link_source = 'nearest_round_time',
                   round_link_reason = NULL,
                   round_linked_at = NOW()
            FROM ranked r
            WHERE p.id = r.prox_id
              AND r.rn = 1
              AND r.candidate_count = 1
        $sql$, t, window_seconds, t);

        -- Pass 4: leave unresolved rows with explicit reason metadata
        EXECUTE format($sql$
            UPDATE public.%I p
               SET round_link_source = COALESCE(p.round_link_source, 'unresolved'),
                   round_link_reason = COALESCE(
                       p.round_link_reason,
                       CASE
                           WHEN p.map_name IS NULL OR p.round_number IS NULL THEN 'invalid_input'
                           WHEN NOT EXISTS (
                               SELECT 1
                               FROM public.rounds r0
                               WHERE r0.map_name = p.map_name
                                 AND r0.round_number = p.round_number
                           ) THEN 'no_rows_for_map_round'
                           WHEN COALESCE(NULLIF(p.round_end_unix, 0), NULLIF(p.round_start_unix, 0)) IS NULL THEN 'missing_event_timestamp'
                           WHEN (
                               SELECT COUNT(*)
                               FROM public.rounds r1
                               WHERE r1.map_name = p.map_name
                                 AND r1.round_number = p.round_number
                                 AND COALESCE(NULLIF(r1.round_end_unix, 0), NULLIF(r1.round_start_unix, 0)) IS NOT NULL
                                 AND ABS(
                                       COALESCE(NULLIF(r1.round_end_unix, 0), NULLIF(r1.round_start_unix, 0))
                                       - COALESCE(NULLIF(p.round_end_unix, 0), NULLIF(p.round_start_unix, 0))
                                 ) <= %s
                           ) > 1 THEN 'ambiguous_candidates'
                           ELSE 'all_candidates_outside_window'
                       END
                   ),
                   round_linked_at = COALESCE(p.round_linked_at, NOW())
            WHERE p.round_id IS NULL
        $sql$, t, window_seconds);
    END LOOP;
END $$;
