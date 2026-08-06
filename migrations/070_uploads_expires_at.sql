-- Uploads currently live forever. The owner asked for two things the library
-- has never had: a retention choice at upload time, and a way for an admin to
-- remove someone else's file.
--
-- This migration covers the first. `expires_at IS NULL` means "keep forever"
-- and is the DEFAULT, so every existing row keeps exactly the semantics it was
-- uploaded under -- no backfill, no behaviour change for anything already
-- there. A non-null value is a hard deadline: reads filter on it immediately,
-- so an expired upload disappears from the library the moment it lapses,
-- without waiting for any sweep to run.
--
-- The physical delete is a separate, admin-triggered step
-- (POST /api/uploads/sweep-expired), deliberately NOT a side effect of a GET:
-- public read endpoints in this codebase must not write.
--
-- OWNERSHIP NOTE: the uploads table is owned by etlegacy_user, while
-- scripts/apply_migrations.py loads website/.env, which sets
-- POSTGRES_USER=website_app. Migration 069 failed for exactly this reason.
-- Apply with POSTGRES_USER=etlegacy_user.

ALTER TABLE uploads ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP NULL;

COMMENT ON COLUMN uploads.expires_at IS
    'Hard expiry for this upload. NULL = keep forever (the default). Reads '
    'filter expired rows out immediately; the file is removed by the '
    'admin-triggered sweep.';

-- Serves both the read filter and the sweep. Partial, because the only rows
-- either one cares about are active ones that actually have a deadline --
-- which, with lifetime as the default, is expected to stay a small minority.
CREATE INDEX IF NOT EXISTS idx_uploads_active_expires_at
    ON uploads (expires_at)
    WHERE status = 'active' AND expires_at IS NOT NULL;
