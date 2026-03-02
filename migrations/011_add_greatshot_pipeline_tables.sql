-- Greatshot feature tables (website upload + analysis pipeline)

DO $$
BEGIN
    IF to_regclass('public.greatshot_demos') IS NULL AND to_regclass('public.demos') IS NOT NULL THEN
        ALTER TABLE demos RENAME TO greatshot_demos;
    END IF;
    IF to_regclass('public.greatshot_analysis') IS NULL AND to_regclass('public.demo_analysis') IS NOT NULL THEN
        ALTER TABLE demo_analysis RENAME TO greatshot_analysis;
    END IF;
    IF to_regclass('public.greatshot_highlights') IS NULL AND to_regclass('public.demo_highlights') IS NOT NULL THEN
        ALTER TABLE demo_highlights RENAME TO greatshot_highlights;
    END IF;
    IF to_regclass('public.greatshot_renders') IS NULL AND to_regclass('public.demo_renders') IS NOT NULL THEN
        ALTER TABLE demo_renders RENAME TO greatshot_renders;
    END IF;
END
$$;

CREATE TABLE IF NOT EXISTS greatshot_demos (
    id TEXT PRIMARY KEY,
    user_id BIGINT NOT NULL,
    original_filename TEXT NOT NULL,
    stored_path TEXT NOT NULL,
    extension TEXT NOT NULL,
    file_size_bytes BIGINT NOT NULL,
    content_hash_sha256 TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'uploaded',
    error TEXT,
    metadata_json JSONB,
    warnings_json JSONB,
    analysis_json_path TEXT,
    report_txt_path TEXT,
    processing_started_at TIMESTAMP,
    processing_finished_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS greatshot_analysis (
    demo_id TEXT PRIMARY KEY REFERENCES greatshot_demos(id) ON DELETE CASCADE,
    metadata_json JSONB NOT NULL,
    stats_json JSONB NOT NULL,
    events_json JSONB NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS greatshot_highlights (
    id TEXT PRIMARY KEY,
    demo_id TEXT NOT NULL REFERENCES greatshot_demos(id) ON DELETE CASCADE,
    type TEXT NOT NULL,
    player TEXT,
    start_ms INTEGER NOT NULL,
    end_ms INTEGER NOT NULL,
    score DOUBLE PRECISION NOT NULL,
    meta_json JSONB,
    clip_demo_path TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS greatshot_renders (
    id TEXT PRIMARY KEY,
    highlight_id TEXT NOT NULL REFERENCES greatshot_highlights(id) ON DELETE CASCADE,
    status TEXT NOT NULL DEFAULT 'queued',
    mp4_path TEXT,
    error TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_greatshot_demos_user_created_at ON greatshot_demos(user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_greatshot_demos_status ON greatshot_demos(status);
CREATE INDEX IF NOT EXISTS idx_greatshot_highlights_demo_id ON greatshot_highlights(demo_id);
CREATE INDEX IF NOT EXISTS idx_greatshot_renders_highlight ON greatshot_renders(highlight_id);
