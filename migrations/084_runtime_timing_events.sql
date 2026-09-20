-- R02a: append-only timing-fill events; initial-import uniqueness stays intact.
-- No backfill/consumers. Runtime activation requires BOTH event flags.
ALTER TABLE runtime_events DROP CONSTRAINT IF EXISTS runtime_events_event_type_check;
ALTER TABLE runtime_events ADD CONSTRAINT runtime_events_event_type_check
    CHECK (event_type IN ('round_stats_imported', 'round_timing_reconciled'));
ALTER TABLE runtime_events ALTER COLUMN source_filename DROP NOT NULL;
ALTER TABLE runtime_events ALTER COLUMN validation_passed DROP NOT NULL;
ALTER TABLE runtime_events ADD COLUMN IF NOT EXISTS event_details JSONB;
ALTER TABLE runtime_events DROP CONSTRAINT IF EXISTS runtime_events_details_check;
ALTER TABLE runtime_events ADD CONSTRAINT runtime_events_details_check CHECK (
    (event_type = 'round_stats_imported' AND source_filename IS NOT NULL
        AND validation_passed IS NOT NULL AND event_details IS NULL)
    OR (event_type = 'round_timing_reconciled' AND event_details IS NOT NULL
        AND jsonb_typeof(event_details) = 'object')
);
ALTER TABLE runtime_events DROP CONSTRAINT IF EXISTS runtime_events_round_id_event_type_key;
CREATE UNIQUE INDEX IF NOT EXISTS runtime_events_initial_import_unique
    ON runtime_events (round_id, event_type) WHERE event_type = 'round_stats_imported';

COMMENT ON COLUMN runtime_events.event_details IS
    'Versioned event-specific metadata, not raw player stats. Timing seconds and Unix timestamps retain source units.';
