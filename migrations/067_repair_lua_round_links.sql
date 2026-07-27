-- Repair lua_round_teams links created by the historical nearest-neighbour
-- race, then enforce the one-Lua-row-per-round contract.
--
-- Safe policy:
--   * exactly one round matching source-native
--     (round_start_unix, normalized map_name, round_number) -> rebind;
--   * zero or multiple exact targets -> set round_id NULL, never guess;
--   * abort before mutation if this projection would retain duplicate
--     non-NULL round_id values.
--
-- `scripts/repair_lua_round_links.py` previews and fingerprints this same
-- action set before an owner runs its guarded --apply mode. This migration is
-- idempotent so it may subsequently run through the normal ledger runner.

BEGIN;

DO $$
DECLARE
    projected_duplicate_groups integer;
BEGIN
    -- Keep the lock in a transaction-bearing statement even when the fresh-
    -- bootstrap parity test replays the unwrapped migration statement-wise.
    LOCK TABLE lua_round_teams IN SHARE ROW EXCLUSIVE MODE;

    WITH wrong AS (
        SELECT
            l.id,
            l.round_id AS old_round_id,
            COUNT(target.id) AS candidate_count,
            MIN(target.id) AS target_round_id
        FROM lua_round_teams l
        JOIN rounds linked ON linked.id = l.round_id
        LEFT JOIN rounds target
          ON target.round_start_unix = l.round_start_unix
         AND LOWER(BTRIM(target.map_name)) = LOWER(BTRIM(l.map_name))
         AND target.round_number = l.round_number
        WHERE l.round_start_unix IS NOT NULL
          AND l.round_start_unix > 0
          AND linked.round_start_unix IS NOT NULL
          AND l.round_start_unix <> linked.round_start_unix
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
    JOIN rounds linked ON linked.id = l.round_id
    JOIN rounds target
      ON target.round_start_unix = l.round_start_unix
     AND LOWER(BTRIM(target.map_name)) = LOWER(BTRIM(l.map_name))
     AND target.round_number = l.round_number
    WHERE l.round_start_unix IS NOT NULL
      AND l.round_start_unix > 0
      AND linked.round_start_unix IS NOT NULL
      AND l.round_start_unix <> linked.round_start_unix
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
FROM rounds linked
WHERE linked.id = l.round_id
  AND l.round_start_unix IS NOT NULL
  AND l.round_start_unix > 0
  AND linked.round_start_unix IS NOT NULL
  AND l.round_start_unix <> linked.round_start_unix;

DO $$
DECLARE
    wrong_rows integer;
    duplicate_groups integer;
BEGIN
    SELECT COUNT(*) INTO wrong_rows
    FROM lua_round_teams l
    JOIN rounds r ON r.id = l.round_id
    WHERE l.round_start_unix IS NOT NULL
      AND r.round_start_unix IS NOT NULL
      AND l.round_start_unix <> r.round_start_unix;

    SELECT COUNT(*) INTO duplicate_groups
    FROM (
        SELECT round_id
        FROM lua_round_teams
        WHERE round_id IS NOT NULL
        GROUP BY round_id
        HAVING COUNT(*) > 1
    ) duplicates;

    IF wrong_rows <> 0 OR duplicate_groups <> 0 THEN
        RAISE EXCEPTION
            '067 postcondition failed: wrong_rows=%, duplicate_groups=%',
            wrong_rows,
            duplicate_groups;
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
