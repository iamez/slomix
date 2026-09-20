-- R02c4: canonical endstats storage changes, not Discord delivery receipts.
ALTER TABLE runtime_events DROP CONSTRAINT IF EXISTS runtime_events_event_type_check;
ALTER TABLE runtime_events ADD CONSTRAINT runtime_events_event_type_check
    CHECK (event_type IN ('round_stats_imported', 'round_timing_reconciled', 'round_status_changed', 'round_endstats_changed'));
ALTER TABLE runtime_events DROP CONSTRAINT IF EXISTS runtime_events_details_check;
ALTER TABLE runtime_events ADD CONSTRAINT runtime_events_details_check CHECK (
    (event_type = 'round_stats_imported' AND source_filename IS NOT NULL
        AND validation_passed IS NOT NULL AND event_details IS NULL)
    OR (event_type IN ('round_timing_reconciled', 'round_status_changed', 'round_endstats_changed')
        AND event_details IS NOT NULL AND jsonb_typeof(event_details) = 'object')
);
