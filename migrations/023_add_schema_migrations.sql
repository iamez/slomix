-- Migration 023: Add schema_migrations tracking table
-- Date: 2026-03-22
-- Description: Tracks which migration files have been applied to the database.
--   This enables automated migration runners and prevents double-application.
--   On first run, existing migrations are recorded as 'baseline' entries.

BEGIN;

CREATE TABLE IF NOT EXISTS schema_migrations (
    id              SERIAL PRIMARY KEY,
    version         TEXT NOT NULL UNIQUE,
    filename        TEXT NOT NULL UNIQUE,
    checksum        TEXT,
    applied_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    applied_by      TEXT DEFAULT 'manual',
    execution_ms    INTEGER,
    success         BOOLEAN NOT NULL DEFAULT TRUE
);

COMMENT ON TABLE schema_migrations IS 'Tracks applied database migration files';

COMMIT;
