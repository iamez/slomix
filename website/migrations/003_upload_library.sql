-- ============================================================================
-- Migration 003: Upload Library (Configs, HUDs, Clips)
-- ============================================================================
-- Adds tables for community file uploads: configs, HUDs, archives, and clips.
-- Follows existing schema conventions from schema_postgresql.sql.
-- ============================================================================

-- Uploads: Main file metadata table
CREATE TABLE IF NOT EXISTS uploads (
    id TEXT PRIMARY KEY,                          -- UUID hex (matches greatshot pattern)
    uploader_discord_id BIGINT,                   -- NULL if anonymous
    uploader_name TEXT NOT NULL DEFAULT 'Anonymous',
    category TEXT NOT NULL CHECK (category IN ('config', 'hud', 'archive', 'clip')),
    title TEXT NOT NULL,
    description TEXT,
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,                     -- Relative to storage root
    extension TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    content_hash_sha256 TEXT NOT NULL,
    mime_type TEXT,
    download_count INTEGER DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'quarantined', 'deleted')),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Upload tags: Flexible tagging for search/filter
CREATE TABLE IF NOT EXISTS upload_tags (
    id SERIAL PRIMARY KEY,
    upload_id TEXT NOT NULL REFERENCES uploads(id) ON DELETE CASCADE,
    tag TEXT NOT NULL,
    UNIQUE(upload_id, tag)
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_uploads_category ON uploads(category);
CREATE INDEX IF NOT EXISTS idx_uploads_status ON uploads(status);
CREATE INDEX IF NOT EXISTS idx_uploads_created_at ON uploads(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_uploads_uploader ON uploads(uploader_discord_id);
CREATE INDEX IF NOT EXISTS idx_uploads_hash ON uploads(content_hash_sha256);
CREATE INDEX IF NOT EXISTS idx_upload_tags_tag ON upload_tags(tag);
CREATE INDEX IF NOT EXISTS idx_upload_tags_upload ON upload_tags(upload_id);
