-- Uploads gallery modernisation (Faza 2): store an optional poster thumbnail so
-- the library shows a real frame from each clip instead of a generic category
-- icon. The poster is a small JPEG captured client-side from the first second of
-- the .mp4 at upload time (no server ffmpeg), written next to the original as
-- poster.jpg; this column holds its path relative to the storage root.
--
-- poster_path IS NULL means "no poster" — the default, and exactly what every
-- existing row keeps, so cards fall back to the category icon with no backfill
-- and no behaviour change for anything already uploaded.
--
-- OWNERSHIP NOTE: the uploads table is owned by etlegacy_user, while
-- scripts/apply_migrations.py loads website/.env (POSTGRES_USER=website_app).
-- Apply with POSTGRES_USER=etlegacy_user (same as migration 070).

ALTER TABLE uploads ADD COLUMN IF NOT EXISTS poster_path TEXT NULL;

COMMENT ON COLUMN uploads.poster_path IS
    'Relative path to a client-captured JPEG poster thumbnail for a video '
    'upload. NULL = no poster (the default); the card falls back to the '
    'category icon. Served at GET /api/uploads/{id}/poster.';
