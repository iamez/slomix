-- migrations/045_drop_orphan_monitoring_tables.sql
-- Drop two orphan monitoring tables identified during the session
-- audit sweep (2026-04-21).
--
-- Tables dropped:
--   * voice_members
--       - Created by migrations/002_voice_activity_tracking.sql.
--       - Dev row count: 0. Never written to by any live code.
--       - Superseded by `voice_status_history` which stores periodic
--         JSONB snapshots of the channel and is actively populated.
--       - Only remaining reference is a diagnostic READ in
--         `website/backend/routers/diagnostics_router.py` (fallback
--         chain that gracefully handles absence).
--
--   * server_status_history_backup_20260207
--       - Manual date-suffixed backup, never in any migration chain.
--       - Dev row count: 79. Main table `server_status_history`
--         (8 833 rows) is the live source of truth; the backup is a
--         cold snapshot now superseded by the 30-day retention cleanup
--         in `bot/services/monitoring_service.py`.
--       - Zero code references.
--
-- Safe to DROP (Explore-agent audit run prior to this migration):
--   * no INSERT/UPDATE/DELETE paths in any .py file reach either table
--   * production parity: both are safe to drop there too — they were
--     never scoped by the main migration chain and have no FK deps.
--
-- Idempotent: `DROP TABLE IF EXISTS`. Safe to re-run.
--
-- HISTORICAL NOTE (superseded 2026-07-26 by the ownership-tolerant DO block
-- below, which lets any role run this):
-- RUN AS postgres SUPERUSER:
--   Dev / prod: `voice_members` is owned by `postgres` (historic
--   bot-install artefact), so `etlegacy_user` can't DROP it. Apply via
--     sudo -u postgres psql -d etlegacy -f /tmp/045_*.sql
--   or (on the sandbox host):
--     su -s /bin/bash postgres -c 'psql -d etlegacy -f /tmp/045_*.sql'

BEGIN;

-- Ownership-tolerant drops (2026-07-26). `voice_members` is owned by
-- `postgres` on both dev and prod (a historic bot-install artefact), so a
-- plain DROP fails for `etlegacy_user` and this migration stayed PENDING
-- forever. That is not cosmetic: `apply_migrations.py --only` refuses to
-- run while ANY unrelated migration is pending, so a permanently-pending
-- 045 blocked every future targeted deploy.
--
-- Each table is dropped only if the current role can actually drop it
-- (owner or superuser). Anything it cannot drop is left in place with a
-- NOTICE instead of aborting — these are orphan tables with no readers and
-- no FK dependencies, so leaving one behind is harmless, whereas blocking
-- every deploy is not. Re-running as postgres later still removes them.
DO $$
DECLARE
    t text;
    tbl_owner text;
BEGIN
    FOREACH t IN ARRAY ARRAY['voice_members', 'server_status_history_backup_20260207']
    LOOP
        SELECT tableowner INTO tbl_owner FROM pg_tables
        WHERE schemaname = 'public' AND tablename = t;

        IF tbl_owner IS NULL THEN
            RAISE NOTICE '045: % already absent', t;
        ELSIF pg_has_role(current_user, tbl_owner, 'USAGE') THEN
            EXECUTE format('DROP TABLE IF EXISTS %I CASCADE', t);
            RAISE NOTICE '045: dropped %', t;
        ELSE
            RAISE NOTICE '045: skipping % (owned by %, current role % cannot drop it) '
                         '— re-run this migration as postgres to remove it',
                         t, tbl_owner, current_user;
        END IF;
    END LOOP;
END $$;

INSERT INTO schema_migrations (version, filename, applied_by)
VALUES ('045_drop_orphan_monitoring_tables',
        '045_drop_orphan_monitoring_tables.sql',
        'self')
ON CONFLICT (version) DO NOTHING;

COMMIT;

-- Verification:
--   SELECT table_name FROM information_schema.tables
--   WHERE table_name IN ('voice_members', 'server_status_history_backup_20260207');
--   -- Expected: 0 rows (both gone)
--
--   SELECT COUNT(*) FROM server_status_history;
--   -- Expected: still populated, unchanged.
