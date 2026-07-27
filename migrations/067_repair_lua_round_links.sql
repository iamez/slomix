-- Enforce the postconditions of the guarded Lua round-link repair and the
-- one-Lua-row-per-round contract. Historical data mutation is deliberately
-- not owned by this migration: scripts/repair_lua_round_links.py must first
-- preview, fingerprint and apply the action set with a verified backup.
--
-- Safe policy:
--   * exactly one round matching source-native
--     (round_start_unix, normalized map_name, round_number) -> rebind;
--   * zero or multiple exact targets -> set round_id NULL, never guess;
--   * abort before mutation if this projection would retain duplicate
--     non-NULL round_id values.
--   * spawn rows inherit only a repaired team row with the same
--     (match_id, round_number, normalized map_name); otherwise they unlink.
--
-- `scripts/repair_lua_round_links.py` previews and fingerprints this action
-- set before an owner runs its guarded --apply mode. This migration refuses
-- dirty historical state, so a normal deploy cannot bypass that guard.

BEGIN;

DO $$
DECLARE
    pending_team_actions integer;
    pending_spawn_actions integer;
    projected_duplicate_groups integer;
BEGIN
    -- Keep the lock in a transaction-bearing statement even when the fresh-
    -- bootstrap parity test replays the unwrapped migration statement-wise.
    LOCK TABLE rounds IN SHARE MODE;
    LOCK TABLE lua_round_teams, lua_spawn_stats IN SHARE ROW EXCLUSIVE MODE;

    SELECT COUNT(*) INTO pending_team_actions
    FROM lua_round_teams l
    LEFT JOIN rounds linked ON linked.id = l.round_id
    WHERE l.round_id IS NOT NULL
      AND (
          l.round_start_unix IS NULL
          OR l.round_start_unix <= 0
          OR linked.id IS NULL
          OR linked.round_start_unix IS DISTINCT FROM l.round_start_unix
          OR LOWER(BTRIM(linked.map_name))
                IS DISTINCT FROM LOWER(BTRIM(l.map_name))
          OR linked.round_number IS DISTINCT FROM l.round_number
      );

    SELECT COUNT(*) INTO pending_spawn_actions
    FROM lua_spawn_stats s
    WHERE s.round_id IS DISTINCT FROM (
        SELECT CASE WHEN COUNT(*) = 1 THEN MIN(l.round_id) ELSE NULL END
        FROM lua_round_teams l
        WHERE l.match_id = s.match_id
          AND l.round_number = s.round_number
          AND LOWER(BTRIM(l.map_name))
                IS NOT DISTINCT FROM LOWER(BTRIM(s.map_name))
    );

    IF pending_team_actions > 0 OR pending_spawn_actions > 0 THEN
        RAISE EXCEPTION
            '067 refused: guarded Lua repair still has team_actions=% and spawn_actions=%; run scripts/repair_lua_round_links.py --apply first',
            pending_team_actions,
            pending_spawn_actions;
    END IF;

    WITH wrong AS (
        SELECT
            l.id,
            l.round_id AS old_round_id,
            COUNT(target.id) AS candidate_count,
            MIN(target.id) AS target_round_id
        FROM lua_round_teams l
        LEFT JOIN rounds linked ON linked.id = l.round_id
        LEFT JOIN rounds target
          ON target.round_start_unix = l.round_start_unix
         AND LOWER(BTRIM(target.map_name)) = LOWER(BTRIM(l.map_name))
         AND target.round_number = l.round_number
        WHERE l.round_id IS NOT NULL
          AND (
              l.round_start_unix IS NULL
              OR l.round_start_unix <= 0
              OR linked.id IS NULL
              OR linked.round_start_unix IS DISTINCT FROM l.round_start_unix
              OR LOWER(BTRIM(linked.map_name))
                    IS DISTINCT FROM LOWER(BTRIM(l.map_name))
              OR linked.round_number IS DISTINCT FROM l.round_number
          )
        GROUP BY l.id, l.round_id
    ),
    projected AS (
        SELECT
            l.id,
            CASE
                WHEN wrong.id IS NULL THEN l.round_id
                WHEN wrong.candidate_count = 1 THEN wrong.target_round_id
                ELSE NULL
            END AS round_id
        FROM lua_round_teams l
        LEFT JOIN wrong ON wrong.id = l.id
    )
    SELECT COUNT(*) INTO projected_duplicate_groups
    FROM (
        SELECT round_id
        FROM projected
        WHERE round_id IS NOT NULL
        GROUP BY round_id
        HAVING COUNT(*) > 1
    ) duplicates;

    IF projected_duplicate_groups > 0 THEN
        RAISE EXCEPTION
            '067 refused: repair projection retains % duplicate lua round_id group(s)',
            projected_duplicate_groups;
    END IF;
END $$;

WITH exact_targets AS (
    SELECT l.id, MIN(target.id) AS target_round_id
    FROM lua_round_teams l
    LEFT JOIN rounds linked ON linked.id = l.round_id
    JOIN rounds target
      ON target.round_start_unix = l.round_start_unix
     AND LOWER(BTRIM(target.map_name)) = LOWER(BTRIM(l.map_name))
     AND target.round_number = l.round_number
    WHERE l.round_id IS NOT NULL
      AND (
          l.round_start_unix IS NULL
          OR l.round_start_unix <= 0
          OR linked.id IS NULL
          OR linked.round_start_unix IS DISTINCT FROM l.round_start_unix
          OR LOWER(BTRIM(linked.map_name))
                IS DISTINCT FROM LOWER(BTRIM(l.map_name))
          OR linked.round_number IS DISTINCT FROM l.round_number
      )
    GROUP BY l.id
    HAVING COUNT(target.id) = 1
)
UPDATE lua_round_teams l
SET round_id = exact_targets.target_round_id
FROM exact_targets
WHERE l.id = exact_targets.id
  AND l.round_id IS DISTINCT FROM exact_targets.target_round_id;

-- Any mismatch left after the exact rebind has no unique provable target.
-- Unlinking preserves the source row while removing false attribution.
UPDATE lua_round_teams l
SET round_id = NULL
WHERE l.round_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM rounds linked
      WHERE linked.id = l.round_id
        AND l.round_start_unix IS NOT NULL
        AND l.round_start_unix > 0
        AND linked.round_start_unix IS NOT DISTINCT FROM l.round_start_unix
        AND LOWER(BTRIM(linked.map_name))
              IS NOT DISTINCT FROM LOWER(BTRIM(l.map_name))
        AND linked.round_number IS NOT DISTINCT FROM l.round_number
  );

-- Spawn rows do not carry the source-native start timestamp. Their only
-- provable identity is the repaired team row emitted by the same payload.
UPDATE lua_spawn_stats s
SET round_id = l.round_id
FROM lua_round_teams l
WHERE l.match_id = s.match_id
  AND l.round_number = s.round_number
  AND LOWER(BTRIM(l.map_name)) IS NOT DISTINCT FROM LOWER(BTRIM(s.map_name))
  AND s.round_id IS DISTINCT FROM l.round_id;

UPDATE lua_spawn_stats s
SET round_id = NULL
WHERE s.round_id IS NOT NULL
  AND NOT EXISTS (
      SELECT 1
      FROM lua_round_teams l
      WHERE l.match_id = s.match_id
        AND l.round_number = s.round_number
        AND LOWER(BTRIM(l.map_name))
              IS NOT DISTINCT FROM LOWER(BTRIM(s.map_name))
  );

DO $$
DECLARE
    wrong_rows integer;
    duplicate_groups integer;
    divergent_spawn_rows integer;
BEGIN
    SELECT COUNT(*) INTO wrong_rows
    FROM lua_round_teams l
    LEFT JOIN rounds r ON r.id = l.round_id
    WHERE l.round_id IS NOT NULL
      AND (
          l.round_start_unix IS NULL
          OR l.round_start_unix <= 0
          OR r.id IS NULL
          OR r.round_start_unix IS DISTINCT FROM l.round_start_unix
          OR LOWER(BTRIM(r.map_name)) IS DISTINCT FROM LOWER(BTRIM(l.map_name))
          OR r.round_number IS DISTINCT FROM l.round_number
      );

    SELECT COUNT(*) INTO duplicate_groups
    FROM (
        SELECT round_id
        FROM lua_round_teams
        WHERE round_id IS NOT NULL
        GROUP BY round_id
        HAVING COUNT(*) > 1
    ) duplicates;

    SELECT COUNT(*) INTO divergent_spawn_rows
    FROM lua_spawn_stats s
    WHERE s.round_id IS DISTINCT FROM (
        SELECT CASE WHEN COUNT(*) = 1 THEN MIN(l.round_id) ELSE NULL END
        FROM lua_round_teams l
        WHERE l.match_id = s.match_id
          AND l.round_number = s.round_number
          AND LOWER(BTRIM(l.map_name))
                IS NOT DISTINCT FROM LOWER(BTRIM(s.map_name))
    );

    IF wrong_rows <> 0 OR duplicate_groups <> 0 OR divergent_spawn_rows <> 0 THEN
        RAISE EXCEPTION
            '067 postcondition failed: wrong_rows=%, duplicate_groups=%, divergent_spawn_rows=%',
            wrong_rows,
            duplicate_groups,
            divergent_spawn_rows;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conrelid = 'lua_round_teams'::regclass
          AND conname = 'lua_round_teams_round_id_key'
    ) THEN
        ALTER TABLE lua_round_teams
            ADD CONSTRAINT lua_round_teams_round_id_key UNIQUE (round_id);
    END IF;
END $$;

COMMIT;
