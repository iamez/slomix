-- 066: ownership-tolerant retry of the 045 orphan-table cleanup.
--
-- WHY A NEW MIGRATION INSTEAD OF FIXING 045
--
-- 045 drops `voice_members` and `server_status_history_backup_20260207`.
-- `voice_members` is owned by `postgres` (a historic bot-install artefact),
-- so `etlegacy_user` cannot drop it and 045 fails under the runner. 045
-- therefore documents "RUN AS postgres SUPERUSER" and expects a manual psql
-- application — which is easy to forget, and a forgotten 045 sits PENDING
-- forever. That matters more than it sounds: `apply_migrations.py --only`
-- refuses to run while ANY migration outside the named set is un-applied, so
-- one stuck row blocks every targeted deploy the release configs perform.
--
-- Editing 045 in place is not an option. Any installation that recorded it
-- successfully stores that file's checksum in `schema_migrations`, and
-- `get_checksum_mismatches` makes the runner refuse EVERY subsequent apply
-- and validate run on a changed file. `--mark` cannot repair it either: it
-- skips filenames already recorded `success = TRUE`. Such a target would need
-- manual ledger surgery to ever deploy again, so 045 stays byte-for-byte as
-- it was and the tolerant behaviour lands here instead.
--
-- WHAT THIS DOES
--
-- Drops each orphan table the current role is actually allowed to drop, and
-- records a NOTICE for anything it may not touch instead of failing. Running
-- it as `postgres` removes everything; running it as `etlegacy_user` removes
-- what it owns and leaves `voice_members` in place, harmlessly — it is an
-- unreferenced orphan, not something the bot reads.
--
-- The DROP is schema-qualified to `public` because the ownership lookup below
-- is pinned to `schemaname = 'public'`. An unqualified DROP resolves through
-- search_path (commonly `"$user", public`), so a same-named table in an
-- earlier schema could be CASCADE-dropped while the intended orphan survived
-- and the migration still reported success.
--
-- Idempotent: DROP TABLE IF EXISTS, and absent tables are reported, not
-- treated as errors. Safe to re-run, and safe to run after 045 succeeded.

BEGIN;

DO $$
DECLARE
    t text;
    tbl_owner text;
BEGIN
    FOREACH t IN ARRAY ARRAY['voice_members',
                             'server_status_history_backup_20260207']
    LOOP
        SELECT tableowner INTO tbl_owner
        FROM pg_tables
        WHERE schemaname = 'public' AND tablename = t;

        IF tbl_owner IS NULL THEN
            RAISE NOTICE '066: % already absent', t;
        ELSIF pg_has_role(current_user, tbl_owner, 'USAGE') THEN
            -- pg_has_role short-circuits to true for superusers, so running
            -- this migration as postgres takes this branch for every table.
            EXECUTE format('DROP TABLE IF EXISTS public.%I CASCADE', t);
            RAISE NOTICE '066: dropped public.%', t;
        ELSE
            RAISE NOTICE '066: skipping % (owned by %, current role % may not '
                         'drop it) — re-run this migration as postgres to '
                         'remove it', t, tbl_owner, current_user;
        END IF;
    END LOOP;
END $$;

COMMIT;
